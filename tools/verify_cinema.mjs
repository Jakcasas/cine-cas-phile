import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {handler} from '../netlify/functions/api.mjs';
const require=createRequire(import.meta.url),films=require('../web/film-utils.js');
const site=process.argv[2];
async function get(path){
  if(site){const response=await fetch(site+path,{signal:AbortSignal.timeout(25000)});assert.equal(response.status,200,path);return response.json();}
  const url=new URL(path,'http://localhost');
  const response=await handler({path:url.pathname,httpMethod:'GET',headers:{},queryStringParameters:Object.fromEntries(url.searchParams)});
  assert.equal(response.statusCode,200,path);return JSON.parse(response.body);
}
const catalog=JSON.parse(readFileSync('data/catalog/movies.json','utf8'));
const stats=await get('/api/stats');assert.equal(stats.catalog_size,catalog.length);
assert.equal(stats.cinema_markets.length,6);
const coverage=[];
for(const region of Object.keys(films.regions)){
  const entry={region};
  for(const mode of ['all','released','recent','screening','upcoming']){
    const query=new URLSearchParams({release_region:region,release:mode,page_size:60});
    const result=await get('/api/movies?'+query);entry[mode]=result.total;
    for(const movie of result.movies)assert.ok(films.matchesRelease(movie,mode,undefined,region),region+' '+mode+' '+movie.title);
    const expected=catalog.filter(m=>films.matchesRelease(m,mode,undefined,region)).length;
    assert.equal(result.total,expected,region+' '+mode+' total');
  }
  assert.ok(entry.screening>0 && entry.upcoming>0 && entry.recent>0,region+' coverage');
  const ordered=await get('/api/movies?'+new URLSearchParams({release_region:region,release:'upcoming',sort:'release-date',page_size:60}));
  const dates=ordered.movies.map(m=>films.releaseSortDate(m,region,'upcoming'));
  for(let i=1;i<dates.length;i++)assert.ok(!dates[i] || dates[i-1] && dates[i-1]<=dates[i],region+' upcoming date order');
  coverage.push(entry);
}
for(const [query,id] of [['룩백',1000097],['クジラに落ちた男',1000100],['Heart of the Beast',1000111]]){
  const result=await get('/api/movies?q='+encodeURIComponent(query));assert.ok(result.movies.some(m=>m.movie_id===id),query);
}
const report={passed:true,site:site || 'local function handler',checked_at:new Date().toISOString(),catalog_size:stats.catalog_size,markets:stats.cinema_markets,filters:coverage};
if(site)writeFileSync('runtime/cinema-production-check.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
