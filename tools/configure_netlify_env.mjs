import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const allowed=['SITE_URL','MONGODB_URI','MONGODB_DB','GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','FACEBOOK_APP_ID','FACEBOOK_APP_SECRET','FACEBOOK_API_VERSION','FACEBOOK_LOGIN_ENABLED','ADMIN_EMAIL'];
if(!existsSync('.env')){console.log('No .env file yet. Copy .env.example and fill in your credentials.');process.exitCode=1;}
else{
  process.loadEnvFile('.env');
  if(!process.env.MONGODB_URI && process.env.MONGODB_PASSWORD && process.env.MONGODB_HOST && process.env.MONGODB_USER)
    process.env.MONGODB_URI=`mongodb+srv://${encodeURIComponent(process.env.MONGODB_USER)}:${encodeURIComponent(process.env.MONGODB_PASSWORD)}@${process.env.MONGODB_HOST}/${process.env.MONGODB_DB || 'cinecasphile'}?retryWrites=true&w=majority&appName=CineCasPhile`;
  const keys=allowed.filter(key=>process.env[key]?.trim());
  if(process.argv.includes('--check'))console.log(JSON.stringify({configuredKeys:keys,missingKeys:allowed.filter(key=>!keys.includes(key))}));
  else {
    const req=createRequire(process.cwd()+'/runtime/netlify-cli/package.json');
    const {getGlobalConfigStore}=await import(pathToFileURL(req.resolve('@netlify/dev-utils')));
    const {NetlifyAPI}=await import(pathToFileURL(req.resolve('@netlify/api')));
    const config=await getGlobalConfigStore();
    const api=new NetlifyAPI(config.get(`users.${config.get('userId')}.auth.token`));
    const siteId='00750758-f294-4229-bdd8-865b45c6382d';
    const site=await api.getSite({siteId});
    const accountId=site.account_slug;
    const existing=await api.getEnvVars({accountId,siteId});
    for(const key of keys){
    try{const old=existing.find(v=>v.key===key);
      const values=[...(old?.values || []).filter(v=>v.context!=='production'),{context:'production',value:process.env[key]}];
      const body={key,is_secret:/SECRET|MONGODB_URI/.test(key),scopes:/SECRET|MONGODB_URI/.test(key)?['builds','functions','runtime']:['builds','functions','runtime','post_processing'],values};
      if(old)await api.updateEnvVar({accountId,siteId,key,body});
      else await api.createEnvVars({accountId,siteId,body:[body]});
      console.log('Configured '+key);}
    catch(error){console.error('Could not set '+key+' (HTTP '+(error.status || 'unknown')+'). No secret values were printed.');process.exitCode=1;break;}
    }
  }
}
