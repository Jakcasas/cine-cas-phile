import {readFileSync,existsSync} from 'node:fs';
import {join} from 'node:path';
import {loadEngine} from './lib/engine.mjs';

export async function handler(event){
  const started=performance.now();const reply=(status,data)=>({statusCode:status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'},body:JSON.stringify(data)});
  try {
    const engine=loadEngine(),d=engine.d;const path=(event.path||'/').replace(/^\/(?:\.netlify\/functions\/)?api\/?/,'/');
    const method=event.httpMethod||'GET',p={...(event.queryStringParameters||{})};
    for(const key of ['year_min','year_max','page','page_size','k'])if(p[key]!=null)p[key]=Number(p[key]);
    if(event.body&&event.body.length>1024*1024)return reply(413,{detail:'Request too large'});
    const body=event.body?JSON.parse(event.isBase64Encoded?Buffer.from(event.body,'base64').toString():event.body):{};
    const health={status:'healthy',version:'3.0.0-netlify',catalog_size:d.movies.length,users_count:d.user_ids.length,loaded_models:['hybrid','collaborative','svd','content','popularity']};
    if(path==='/health')return reply(200,health);
    if(path==='/stats')return reply(200,{...health,genres:d.genres,split:d.manifest,year_min:Math.min(...d.movies.map(m=>m.year)),year_max:Math.max(...d.movies.map(m=>m.year)),poster_movies:d.poster_movies});
    if(path==='/movies'&&method==='GET')return reply(200,engine.catalog(p));
    const detail=path.match(/^\/movies\/(\d+)$/);if(detail)return reply(200,{...engine.movie(detail[1]),similar_movies:engine.similar(detail[1])});
    if(path==='/movie-batch'&&method==='POST'){if(!Array.isArray(body.ids)||body.ids.length>5000)throw new Error('Invalid IDs');return reply(200,{movies:body.ids.map(id=>engine.movie(id))});}
    if(path==='/discover'&&method==='POST'){
      const items=engine.recommend(body);const sig=engine.signals(body),model=body.model||'hybrid';
      const fallback=model==='svd'&&!sig.known||model==='collaborative'&&!sig.hasHistory||model==='content'&&!sig.hasContent||model==='hybrid'&&!sig.hasHistory&&!sig.hasContent;
      return reply(200,{model,count:items.length,recommendations:items,latency_ms:Math.round((performance.now()-started)*100)/100,is_fallback:fallback,
        fallback_reason:model==='svd'&&fallback?'SVD cần ID MovieLens có lịch sử train. Hiện đang dùng điểm cộng đồng; chọn Hybrid để dùng gu cá nhân.':null});
    }
    if(path==='/benchmark'){
      const root=process.env.LAMBDA_TASK_ROOT||process.cwd();
      const paths=[join(root,'netlify/functions/data/benchmark.json'),join(root,'data/benchmark.json')];const file=paths.find(p=>existsSync(p));
      return reply(200,{...JSON.parse(readFileSync(file,'utf8')),runtime_note:'Báo cáo được đo trên engine Python. Bản Netlify chuyển cùng artifact sang JavaScript; latency thực tế hiển thị khi gợi ý.'});
    }
    return reply(404,{detail:'Endpoint not found'});
  } catch(error){return reply(error.message==='Movie not found'?404:422,{detail:error.message});}
}
