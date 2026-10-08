import { MongoClient } from 'mongodb';
import { jwtVerify, createRemoteJWKSet } from 'jose';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { loadEngine } from './lib/engine.mjs';
import { ClubError, token, digest, text, email, passwordHash, passwordMatches, publicUser, safeProfile } from './lib/club-security.mjs';

let databasePromise;
const oidcKeys = createRemoteJWKSet(new URL('https://www.googleapis.com/oauth2/v3/certs'));
const origin = () => (process.env.SITE_URL || 'https://cinecasphile.netlify.app').replace(/\/$/, '');
const configured = () => Boolean(process.env.MONGODB_URI);
const providers = () => ({google: Boolean(configured() && process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET), facebook: Boolean(configured() && process.env.FACEBOOK_APP_ID && process.env.FACEBOOK_APP_SECRET && process.env.FACEBOOK_LOGIN_ENABLED==='true')});
const cookie = (name, value, age) => `${name}=${value}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${age}`;
const cookies = event => Object.fromEntries((event.headers?.cookie || '').split(';').map(s => s.trim().split('=')));
const clean = doc => { if (!doc) return null; const {_id, ...rest} = doc; return rest; };
const reply = (status, data, extra = {}) => ({statusCode:status, headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',...extra}, body:JSON.stringify(data)});
const redirect = (url, values = []) => ({statusCode:302, headers:{Location:url,'Cache-Control':'no-store'}, multiValueHeaders:{'Set-Cookie':values}, body:''});
async function database() {
  if (!configured()) throw new ClubError(503, 'Tài khoản và cộng đồng đang chuẩn bị mở cửa. Bạn vẫn có thể dùng chế độ khách trên thiết bị.');
  databasePromise ??= (async () => {
    const client = new MongoClient(process.env.MONGODB_URI, {maxPoolSize:5, serverSelectionTimeoutMS:7000});
    await client.connect();
    const db = client.db(process.env.MONGODB_DB || 'cinecasphile');
    const root=process.env.LAMBDA_TASK_ROOT || process.cwd();
    const schemaFile=[join(root,'netlify/functions/data/club-schema.json'),join(root,'data/club-schema.json')].find(existsSync);
    const schemas = JSON.parse(readFileSync(schemaFile,'utf8'));
    for (const [name, validator] of Object.entries(schemas)) {
      try { await db.createCollection(name,{validator:{$jsonSchema:validator}}); }
      catch(error) { if(error.code !== 48) throw error; }
    }
    await Promise.all([
      db.collection('users').createIndex({id:1},{unique:true}),
      db.collection('users').createIndex({loginKey:1},{unique:true}),
      db.collection('sessions').createIndex({hash:1},{unique:true}),
      db.collection('sessions').createIndex({expires:1},{expireAfterSeconds:0}),
      db.collection('oauth').createIndex({hash:1},{unique:true}),
      db.collection('oauth').createIndex({expires:1},{expireAfterSeconds:0}),
      db.collection('profiles').createIndex({userId:1},{unique:true}),
      db.collection('posts').createIndex({id:1},{unique:true}),
      db.collection('posts').createIndex({kind:1,status:1,createdAt:-1}),
      db.collection('posts').createIndex({userId:1,movieId:1},{unique:true,partialFilterExpression:{kind:'review'}}),
      db.collection('likes').createIndex({postId:1,userId:1},{unique:true}),
      db.collection('limits').createIndex({expires:1},{expireAfterSeconds:0}),
      db.collection('reports').createIndex({postId:1,userId:1},{unique:true}),
    ]);
    return db;
  })().catch(error => { databasePromise = null; throw error; });
  return databasePromise;
}
async function rate(db, key, maximum, seconds) {
  const window = Math.floor(Date.now() / (seconds * 1000));
  const doc = await db.collection('limits').findOneAndUpdate({_id:digest(key+':'+window)},{$inc:{count:1},$setOnInsert:{expires:new Date(Date.now()+seconds*2000)}},{upsert:true,returnDocument:'after'});
  if (doc.count > maximum) throw new ClubError(429,'Bạn thao tác hơi nhanh. Hãy thử lại sau ít phút.');
}
async function session(db, event, required = true) {
  const value = cookies(event).cine_session;
  const record = value && await db.collection('sessions').findOne({hash:digest(value),expires:{$gt:new Date()}});
  const user = record && await db.collection('users').findOne({id:record.userId});
  if (!user && required) throw new ClubError(401,'Hãy đăng nhập hoặc tham gia bằng biệt danh khách.');
  return user || null;
}
async function createSession(db, user) {
  const value = token();
  await db.collection('sessions').insertOne({hash:digest(value),userId:user.id,expires:new Date(Date.now()+30*86400000)});
  return cookie('cine_session',value,30*86400);
}
async function profile(db,user) {
  return clean(await db.collection('profiles').findOne({userId:user.id})) || {watchlist:[],seen:[],ratings:{},genres:[],survey:{}};
}
export async function handler(event) {
  try {
    const path = (event.path || '').replace(/^\/(?:\.netlify\/functions\/)?club\/?/,'/');
    const method = event.httpMethod || 'GET';
    if (path === '/config' && method === 'GET') return reply(200,{online:configured(),providers:providers(),blog_policy:'publish-with-reporting',version:'1.0'});
    const requestOrigin = event.headers?.origin || event.headers?.Origin;
    if (method !== 'GET' && requestOrigin && requestOrigin !== origin()) throw new ClubError(403,'Nguồn yêu cầu không hợp lệ.');
    if (event.body?.length > 50000) throw new ClubError(413,'Nội dung quá dài.');
    const body = event.body ? JSON.parse(event.isBase64Encoded ? Buffer.from(event.body,'base64').toString() : event.body) : {};
    if (!body || typeof body !== 'object' || Array.isArray(body)) throw new ClubError(422,'Dữ liệu không hợp lệ.');
    const db = await database();
    const ip = event.headers?.['x-nf-client-connection-ip'] || event.headers?.['client-ip'] || 'local';
    if (method !== 'GET') await rate(db,'ip:'+ip,120,600);
    if (path === '/auth/me' && method === 'GET') {
      const user = await session(db,event,false);
      return reply(200,{user:user && publicUser(user),profile:user && await profile(db,user)});
    }
    if (['/auth/register','/auth/login','/auth/guest'].includes(path) && method === 'POST') {
      await rate(db,'auth:'+ip,15,900);
      let user;
      if (path === '/auth/login') {
        user = await db.collection('users').findOne({loginKey:'email:'+email(body.email)});
        // Use the same costly hash for unknown accounts to reduce account enumeration.
        const stored = user?.password || passwordHash('unknown-account-password');
        if (!passwordMatches(body.password,stored) || !user) throw new ClubError(401,'Email hoặc mật khẩu chưa đúng.');
      } else {
        const guest = path.endsWith('/guest');
        const id = token();
        user = {id,name:body.anonymous ? 'Ẩn danh' : text(body.name || 'Ẩn danh',2,40,'Biệt danh'),provider:guest?'guest':'email',loginKey:guest?'guest:'+id:'email:'+email(body.email),role:'member',createdAt:new Date()};
        if (!guest) {user.email=email(body.email);user.password=passwordHash(body.password);}
        try { await db.collection('users').insertOne(user); }
        catch(error) {if(error.code===11000) throw new ClubError(409,'Không thể tạo tài khoản này. Thử đăng nhập hoặc một email khác.'); throw error;}
      }
      const value = await createSession(db,user);
      return {...reply(200,{user:publicUser(user),profile:await profile(db,user)}),multiValueHeaders:{'Set-Cookie':[value]}};
    }
    if (path === '/auth/logout' && method === 'POST') {
      if(cookies(event).cine_session) await db.collection('sessions').deleteOne({hash:digest(cookies(event).cine_session)});
      return {...reply(200,{ok:true}),multiValueHeaders:{'Set-Cookie':[cookie('cine_session','',0)]}};
    }
    const oauth = path.match(/^\/auth\/(google|facebook)(\/callback)?$/);
    if (oauth && method === 'GET') {
      const provider = oauth[1];
      if(!providers()[provider]) throw new ClubError(503,'Phương thức đăng nhập này chưa sẵn sàng.');
      const callback = origin()+'/club/auth/'+provider+'/callback';
      const query = event.queryStringParameters || {};
      const facebookVersion = process.env.FACEBOOK_API_VERSION || 'v24.0';
      if(!oauth[2]) {
        const state=token(),nonce=token(),verifier=token();
        await db.collection('oauth').insertOne({hash:digest(state),provider,nonce,verifier,expires:new Date(Date.now()+600000)});
        const params = new URLSearchParams({client_id:provider==='google'?process.env.GOOGLE_CLIENT_ID:process.env.FACEBOOK_APP_ID,redirect_uri:callback,response_type:'code',scope:provider==='google'?'openid email profile':'public_profile,email',state});
        if(provider==='google'){params.set('nonce',nonce);params.set('code_challenge',Buffer.from(digest(verifier),'hex').toString('base64url'));params.set('code_challenge_method','S256');}
        return redirect((provider==='google'?'https://accounts.google.com/o/oauth2/v2/auth':'https://www.facebook.com/'+facebookVersion+'/dialog/oauth')+'?'+params,[cookie('cine_oauth',state,600)]);
      }
      if(!query.state || cookies(event).cine_oauth!==query.state) throw new ClubError(403,'Phiên đăng nhập hết hạn. Hãy thử lại.');
      const flow=await db.collection('oauth').findOneAndDelete({hash:digest(query.state),provider,expires:{$gt:new Date()}});
      if(!flow || !query.code) return redirect(origin()+'/?auth=cancelled',[cookie('cine_oauth','',0)]);
      const params = new URLSearchParams({code:query.code,client_id:provider==='google'?process.env.GOOGLE_CLIENT_ID:process.env.FACEBOOK_APP_ID,client_secret:provider==='google'?process.env.GOOGLE_CLIENT_SECRET:process.env.FACEBOOK_APP_SECRET,redirect_uri:callback});
      let identity;
      if(provider==='google') {
        params.set('grant_type','authorization_code');params.set('code_verifier',flow.verifier);
        const response=await fetch('https://oauth2.googleapis.com/token',{method:'POST',body:params,signal:AbortSignal.timeout(10000)});
        const tokens=await response.json();
        if(!response.ok || !tokens.id_token) throw new ClubError(401,'Không thể xác nhận tài khoản Google.');
        const {payload}=await jwtVerify(tokens.id_token,oidcKeys,{audience:process.env.GOOGLE_CLIENT_ID,issuer:['https://accounts.google.com','accounts.google.com']});
        if(payload.nonce!==flow.nonce || !payload.email_verified) throw new ClubError(401,'Google chưa xác nhận email.');
        identity={sub:payload.sub,name:payload.name || 'Người yêu phim',email:payload.email,verified:true};
      } else {
        const response=await fetch('https://graph.facebook.com/'+facebookVersion+'/oauth/access_token',{method:'POST',body:params,signal:AbortSignal.timeout(10000)});
        const tokens=await response.json();
        if(!response.ok || !tokens.access_token) throw new ClubError(401,'Không thể xác nhận tài khoản Facebook.');
        const proof = (await import('node:crypto')).createHmac('sha256',process.env.FACEBOOK_APP_SECRET).update(tokens.access_token).digest('hex');
        const info=await fetch('https://graph.facebook.com/'+facebookVersion+'/me?fields=id,name,email&appsecret_proof='+proof,{headers:{Authorization:'Bearer '+tokens.access_token},signal:AbortSignal.timeout(10000)});
        const data=await info.json();
        if(!info.ok || !data.id) throw new ClubError(401,'Facebook chưa xác nhận tài khoản.');
        identity={sub:data.id,name:data.name || 'Người yêu phim',email:data.email};
      }
      const loginKey=provider+':'+identity.sub;
      let user=await db.collection('users').findOne({loginKey});
      if(!user){user={id:token(),loginKey,provider,name:identity.name.slice(0,40),role:identity.verified && identity.email?.toLowerCase()===process.env.ADMIN_EMAIL?.toLowerCase()?'admin':'member',createdAt:new Date()};if(identity.email)user.email=identity.email;try{await db.collection('users').insertOne(user);}catch(error){if(error.code!==11000)throw error;user=await db.collection('users').findOne({loginKey});}}
      return redirect(origin()+'/?auth=success',[await createSession(db,user),cookie('cine_oauth','',0)]);
    }
    if(path==='/posts' && method==='GET') {
      const kind=['chat','review','blog'].includes(event.queryStringParameters?.kind)?event.queryStringParameters.kind:'chat';
      const filter={kind,status:'published'};
      if(event.queryStringParameters?.movieId) filter.movieId=Number(event.queryStringParameters.movieId);
      const rows=await db.collection('posts').find(filter).sort({createdAt:-1}).limit(50).toArray();
      const user=await session(db,event,false);
      const liked=user?new Set((await db.collection('likes').find({userId:user.id,postId:{$in:rows.map(p=>p.id)}}).toArray()).map(p=>p.postId)):new Set();
      return reply(200,{posts:rows.map(({_id,userId,...post})=>({...post,liked:liked.has(post.id),canRemove:user?.id===userId || user?.role==='admin'}))});
    }
    const user = await session(db,event);
    if(path==='/auth/delete' && method==='POST') {
      if(user.provider==='email' && !passwordMatches(body.password,user.password))throw new ClubError(401,'Nhập lại mật khẩu để xóa tài khoản.');
      if(['google','facebook'].includes(user.provider)){
        const recent=await db.collection('sessions').findOne({hash:digest(cookies(event).cine_session),expires:{$gt:new Date(Date.now()+30*86400000-10*60000)}});
        if(!recent)throw new ClubError(401,'Đăng nhập lại bằng Google/Facebook rồi xóa tài khoản trong vòng 10 phút.');
      }
      const ownPosts=(await db.collection('posts').find({userId:user.id},{projection:{id:1}}).toArray()).map(p=>p.id);
      await Promise.all(['profiles','sessions','posts','likes','reports','feedback'].map(name=>db.collection(name).deleteMany({userId:user.id})));
      if(ownPosts.length)await Promise.all(['likes','reports'].map(name=>db.collection(name).deleteMany({postId:{$in:ownPosts}})));
      await db.collection('users').deleteOne({id:user.id});
      return {...reply(200,{ok:true}),multiValueHeaders:{'Set-Cookie':[cookie('cine_session','',0)]}};
    }
    if(path==='/profile' && method==='GET') return reply(200,await profile(db,user));
    if(path==='/profile' && method==='PUT') {
      const next=safeProfile(body,loadEngine());
      await db.collection('profiles').updateOne({userId:user.id},{$set:{...next,updatedAt:new Date()}},{upsert:true});
      return reply(200,next);
    }
    if(path==='/posts' && method==='POST') {
      await rate(db,'post:'+user.id,10,300);
      const kind=['chat','review','blog'].includes(body.kind)?body.kind:null;
      if(!kind) throw new ClubError(422,'Loại bài viết chưa đúng.');
      const post={id:token(),userId:user.id,author:body.anonymous?'Ẩn danh':user.name,kind,status:'published',title:kind==='blog'?text(body.title,3,150,'Tiêu đề'):'',content:text(body.content,kind==='blog'?30:1,kind==='blog'?15000:2000),spoiler:Boolean(body.spoiler),createdAt:new Date(),likes:0};
      if(body.movieId!=null){const movie=loadEngine().movie(body.movieId);post.movieId=movie.movie_id;post.movieTitle=movie.title;}
      if(kind==='review'){if(!post.movieId)throw new ClubError(422,'Hãy chọn phim để đánh giá.');post.rating=Number(body.rating);if(post.rating<.5 || post.rating>5 || post.rating*2%1 || !Number.isFinite(post.rating))throw new ClubError(422,'Điểm chưa đúng.');}
      if(kind==='review'){
        const {id,createdAt,likes,...editable}=post;
        const saved=await db.collection('posts').findOneAndUpdate({userId:user.id,movieId:post.movieId,kind:'review'},{$set:editable,$setOnInsert:{id,createdAt,likes}},{upsert:true,returnDocument:'after'});
        post.id=saved.id;
      }else await db.collection('posts').insertOne(post);
      return reply(201,{id:post.id,status:post.status});
    }
    const action=path.match(/^\/posts\/([\w-]+)\/(like|report|delete)$/);
    if(action && method==='POST') {
      const post=await db.collection('posts').findOne({id:action[1],status:'published'});
      if(!post)throw new ClubError(404,'Bài viết không còn hiển thị.');
      if(action[2]==='delete') {if(user.id!==post.userId && user.role!=='admin')throw new ClubError(403,'Bạn chỉ có thể gỡ bài của mình.');await db.collection('posts').updateOne({id:post.id},{$set:{status:'removed'}});}
      if(action[2]==='report') {await db.collection('reports').updateOne({postId:post.id,userId:user.id},{$setOnInsert:{reason:text(body.reason,3,1000,'Lý do'),createdAt:new Date()}},{upsert:true});}
      if(action[2]==='like') {try{await db.collection('likes').insertOne({postId:post.id,userId:user.id});}catch(error){if(error.code!==11000)throw error;}const likes=await db.collection('likes').countDocuments({postId:post.id});await db.collection('posts').updateOne({id:post.id},{$set:{likes}});}
      return reply(200,{ok:true});
    }
    if(path==='/feedback' && method==='POST') {
      await rate(db,'feedback:'+user.id,5,3600);
      await db.collection('feedback').insertOne({id:token(),userId:user.id,category:['idea','bug','experience'].includes(body.category)?body.category:'idea',content:text(body.content,5,3000),score:Number(body.score)||0,createdAt:new Date()});
      return reply(201,{ok:true});
    }
    if(path==='/admin/reports' && method==='GET' && user.role==='admin') return reply(200,{reports:(await db.collection('reports').find().sort({createdAt:-1}).limit(100).toArray()).map(clean)});
    return reply(404,{detail:'Không tìm thấy chức năng này.'});
  }catch(error){if(error instanceof ClubError)return reply(error.status,{detail:error.message});if(error instanceof SyntaxError)return reply(400,{detail:'JSON không hợp lệ.'});console.error('Club service failed',error.code || error.name);return reply(503,{detail:'Cộng đồng đang tạm gián đoạn. Hãy thử lại sau.'});}
}
