"""Enrich existing films via Letterboxd's documented IMDb-ID redirects."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import json
import re
import time
from src import settings
from src.data.catalog import load_catalog
from tools.sync_movie_images import fetch
from tools.sync_editorial import jsonld


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=1000)
    args=parser.parse_args()
    folder=settings.ROOT/'data/enrichment';path=folder/'editorial.json'
    data=json.loads(path.read_text(encoding='utf-8'));entries=data['movies']
    ratings=json.loads((folder/'ratings.json').read_text(encoding='utf-8'))['movies']
    catalog=load_catalog(settings.DATA_DIR).set_index('movie_id')
    tasks=[]
    for mid,entry in ratings.items():
        imdb=next((re.search(r'tt\d+',r['url'])[0] for r in entry['external_ratings'] if r['provider']=='IMDb'),None)
        if imdb and 'Letterboxd' not in entries.get(mid,{}).get('catalog_sources',[]):tasks.append((int(mid),imdb))
    now=datetime.now(timezone.utc).isoformat();errors=[];updated=0
    def retrieve(mid,imdb):
        time.sleep(.15)
        soup=fetch('https://letterboxd.com/imdb/'+imdb+'/')
        film=next((d for d in jsonld(soup) if isinstance(d,dict) and d.get('@type')=='Movie'),None)
        link=soup.find('link',rel='canonical') or soup.find('meta',property='og:url')
        imdb_link=soup.select_one('a[href*="imdb.com/title/"]')
        if not film or not imdb_link or imdb not in imdb_link.get('href',''):return None
        if str(film.get('dateCreated',''))[:4]!=str(int(catalog.loc[mid,'year'])):return None
        if not film.get('image'):return None
        url=(link.get('href') or link.get('content')) if link else film.get('url')
        return (film,url) if url else None
    def save():
        data['updated_at']=now
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[(mid,imdb,pool.submit(retrieve,mid,imdb)) for mid,imdb in tasks[:args.limit]]
        for count,(mid,imdb,future) in enumerate(futures,1):
            try:
                result=future.result()
                if not result:errors.append({'movie_id':mid,'imdb_id':imdb,'error':'No matching public metadata'});continue
                film,url=result
                entry=entries.setdefault(str(mid),{'poster_sources':[],'catalog_sources':[],'external_ratings':[]})
                entry['catalog_sources']=list(dict.fromkeys(entry.get('catalog_sources',[])+['Letterboxd']))
                entry['poster_sources']=[s for s in entry.get('poster_sources',[]) if s['name']!='Letterboxd']+[{'name':'Letterboxd','page_url':url,'image_url':film['image'],'fallback_url':None}]
                entry['imdb_id']=imdb;entry['media_type']='film'
                entry['directors']=[p['name'] for p in film.get('director',[])]
                rating=film.get('aggregateRating',{})
                if rating.get('ratingValue') is not None:
                    entry['external_ratings']=[r for r in entry.get('external_ratings',[]) if r['provider']!='Letterboxd']+[{'provider':'Letterboxd','audience':'audience','value':float(rating['ratingValue']),'scale':5,'count':rating.get('ratingCount'),'url':url,'checked_at':now}]
                updated+=1
            except Exception as error:errors.append({'movie_id':mid,'error':str(error)})
            if count%50==0:save();print(f'Letterboxd {count}/{len(futures)}: {updated} updated',flush=True)
    save()
    report={'attempted':min(len(tasks),args.limit),'updated':updated,
            'letterboxd_movies':sum('Letterboxd' in e.get('catalog_sources',[]) for e in entries.values()),'errors':errors}
    (settings.ROOT/'reports/letterboxd_sync.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='errors'}),flush=True)


if __name__=='__main__':main()
