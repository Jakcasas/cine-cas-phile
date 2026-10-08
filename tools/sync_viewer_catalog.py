"""Add verified public film metadata and fill missing posters, without reviews.

Title + year must match exactly. Failed or ambiguous matches stay missing.
Public pages are cached; use --limit to bound requests and rerun safely.
"""
import argparse
import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tools.sync_editorial import letterboxd, ALLOWED, GENRES
from tools.sync_movie_images import aliases
from src.data.catalog import load_catalog
from src import settings

NEW_FILMS = ['digger-2026', 'verity-2026', 'other-mommy', 'clayface', 'forgotten-island-2026']

def slug(title):
    title = re.sub(r'\([^)]*\)', '', title).strip()
    title = re.sub(r'^(.+),\s*(The|A|An|Le|La|Les|El|Il)$', r'\2 \1', title)
    return '-'.join(re.findall(r'[a-z0-9]+', title.lower().replace("'", '').replace('’','')))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=150)
    args = parser.parse_args()
    catalog = load_catalog(settings.DATA_DIR)
    path = settings.ROOT/'data/enrichment/editorial.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    entries = data['movies']
    images = json.loads((path.parent/'movie_images.json').read_text(encoding='utf-8'))['movies']
    extras_path = settings.DATA_DIR/'catalog_extra.csv'
    with extras_path.open(encoding='utf-8',newline='') as handle: extras=list(csv.DictReader(handle))
    next_id = max(int(row['movie_id']) for row in extras)+1
    errors=[]; updated=[]; added=[]
    now=datetime.now(timezone.utc).isoformat()
    def save():
        data['updated_at']=now
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        with extras_path.open('w',encoding='utf-8',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=['movie_id','title','genres']);writer.writeheader();writer.writerows(extras)
    def add(mid,item):
        entry=entries.setdefault(str(mid),{})
        entry['catalog_sources']=list(dict.fromkeys(entry.get('catalog_sources',[])+['Letterboxd']))
        entry['poster_sources']=[s for s in entry.get('poster_sources',[]) if s['name']!='Letterboxd']+[{'name':'Letterboxd','page_url':item['page_url'],'image_url':item['image_url'],'fallback_url':None}]
        entry.update({k:item[k] for k in ['directors','imdb_id','media_type']})
        if item.get('rating') is not None:
            entry['external_ratings']=[r for r in entry.get('external_ratings',[]) if r['provider']!='Letterboxd']+[{'provider':'Letterboxd','audience':'audience','value':float(item['rating']),'scale':5,'count':item.get('rating_count'),'url':item['page_url'],'checked_at':now}]
        updated.append(mid)
    for name in NEW_FILMS:
        try:
            item=letterboxd(name)
            if not item or item['year']!=2026 or not item.get('image_url'):raise ValueError('No verified 2026 metadata')
            matches=[int(row.movie_id) for row in catalog.itertuples() if int(row.year)==item['year'] and aliases(row.title)&aliases(item['title'])]
            if len(matches)>1:raise ValueError('Ambiguous title/year')
            if matches:mid=matches[0]
            else:
                mid=next_id;next_id+=1
                genres=[GENRES.get(g,g) for g in item['genres']]
                extras.append({'movie_id':mid,'title':f"{item['title']} ({item['year']})",'genres':'|'.join(g for g in genres if g in ALLOWED) or 'Drama'})
                added.append(item['title'])
            add(mid,item)
        except Exception as error:errors.append({'slug':name,'error':str(error)})
    save()
    counts={}
    with (settings.DATA_DIR/'ratings.csv').open(encoding='utf-8',newline='') as handle:
        first=handle.readline();handle.seek(0)
        for row in csv.DictReader(handle,delimiter='\t' if '\t' in first else ','):
            mid=int(row.get('movie_id') or row['MovieID']);counts[mid]=counts.get(mid,0)+1
    missing=[row for row in catalog.itertuples() if not images.get(str(row.movie_id),{}).get('poster_sources') and not entries.get(str(row.movie_id),{}).get('poster_sources')]
    missing.sort(key=lambda row:-counts.get(int(row.movie_id),0))
    def retrieve(row):
        time.sleep(.4)
        name=slug(row.title)
        for candidate in [name+'-'+str(int(row.year)),name]:
            try:
                item=letterboxd(candidate)
                if item and item['year']==int(row.year) and aliases(item['title'])&aliases(row.title) and item.get('image_url'):return item
            except Exception:continue
        return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[(row,pool.submit(retrieve,row)) for row in missing[:args.limit]]
        for i,(row,future) in enumerate(futures,1):
            item=future.result()
            if item:add(int(row.movie_id),item)
            else:errors.append({'movie_id':int(row.movie_id),'error':'No exact public title/year poster match'})
            if i%25==0:save();print(f'{i}/{len(futures)} checked; {len(updated)} verified posters',flush=True)
    save()
    report={'checked_at':now,'added_films':added,'verified_updates':len(updated),'attempted_missing':len(futures),'errors':errors}
    (settings.ROOT/'reports/viewer_catalog_sync.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='errors'},ensure_ascii=True),flush=True)

if __name__=='__main__':main()
