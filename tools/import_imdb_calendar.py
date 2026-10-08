"""Import an explicitly captured public IMDb calendar JSON snapshot.

Does not fetch protected pages, fabricate ratings, or import reviews. Re-running
the same snapshot retains IDs. Dates describe the selected market, not showtimes.
"""
import argparse
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {'Action','Adventure','Animation',"Children's",'Comedy','Crime','Documentary','Drama','Fantasy','Film-Noir','Horror','Musical','Mystery','Romance','Sci-Fi','Thriller','War','Western'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--through', default='2026-11-06')
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding='utf-8'))
    checked = datetime.fromisoformat(snapshot['checked_at']).date()
    end = datetime.fromisoformat(args.through).date()
    region=snapshot['region']
    if region not in {'US','GB','FR','JP','KR'} or snapshot['source_url'] != f'https://www.imdb.com/calendar/?region={region}':
        raise ValueError('Unexpected calendar market or source')
    csv_path = ROOT/'data/raw/catalog_extra.csv'
    with csv_path.open(encoding='utf-8',newline='') as f:
        extras = list(csv.DictReader(f))
    editorial = json.loads((ROOT/'data/enrichment/editorial.json').read_text(encoding='utf-8'))['movies']
    release_path = ROOT/'data/enrichment/imdb_releases.json'
    payload = json.loads(release_path.read_text(encoding='utf-8')) if release_path.exists() else {'movies':{}}
    known = {e.get('imdb_id'):int(mid) for mid,e in editorial.items() if e.get('imdb_id')}
    known.update({e['imdb_id']:int(mid) for mid,e in payload['movies'].items()})
    titles = {r['title'].casefold():int(r['movie_id']) for r in extras}
    next_id = max(int(r['movie_id']) for r in extras)+1
    added=[]
    for item in snapshot['movies']:
        date = datetime.strptime(item['date'],'%b %d, %Y').date()
        if not checked-timedelta(days=30) <= date <= end:
            continue
        title = item['title'].strip()
        if not re.search(r'\(202[4-9]\)$', title) or not re.fullmatch(r'tt\d+',item['imdb_id']):
            continue
        genres = list(dict.fromkeys('Children\'s' if g=='Family' else 'Musical' if g=='Music' else g for g in item['genres']))
        genres = [g for g in genres if g in ALLOWED]
        # Concert screenings are outside this film selection.
        if not genres or genres == ['Musical'] or 'Live Viewing' in title:
            continue
        localized = ''
        if item['imdb_id']=='tt36586020': localized,title=title.rsplit(' (',1)[0],'Other Mommy (2026)'
        if item['imdb_id']=='tt37510326': localized,title=title.rsplit(' (',1)[0],'The Social Reckoning (2026)'
        if item['imdb_id']=='tt27419420': localized,title=title.rsplit(' (',1)[0],'Street Fighter (2026)'
        mid = known.get(item['imdb_id']) or titles.get(title.casefold())
        if mid is None:
            mid=next_id;next_id+=1
            extras.append({'movie_id':mid,'title':title,'genres':'|'.join(genres)})
            titles[title.casefold()]=mid
            added.append(title)
        page = f"https://www.imdb.com/title/{item['imdb_id']}/"
        image = item.get('image_url')
        if image and (urlparse(image).scheme!='https' or urlparse(image).hostname!='m.media-amazon.com'):
            raise ValueError('Unexpected image host')
        # Same observed image asset at poster size; leave source identity intact.
        image = re.sub(r'\._V1_.*?\.jpg$', '._V1_QL85_UX600_.jpg',image) if image else None
        previous=payload['movies'].get(str(mid),{})
        release={'date':date.isoformat(),'region':region,'source':'IMDb','url':page,
                 'calendar_url':snapshot['source_url'],'checked_at':checked.isoformat()}
        releases=previous.get('releases', [previous['release']] if previous.get('release') else [])
        releases=[r for r in releases if r['region']!=region]+[release]
        entry={**previous,'imdb_id':item['imdb_id'],'catalog_sources':['IMDb'],'media_type':'film',
               'release':release if previous.get('release',{}).get('region')==region else previous.get('release',release),'releases':releases,
               'title_aliases':list(dict.fromkeys(previous.get('title_aliases',[])+[item['title'].rsplit(' (',1)[0]])),
               'poster_sources':[{'name':'IMDb','page_url':page,'image_url':image,'fallback_url':None}] if image else []}
        if not image:entry['poster_sources']=previous.get('poster_sources',[])
        if localized: entry['title_vi']=localized
        payload['movies'][str(mid)]=entry
        known[item['imdb_id']]=mid
    payload['updated_at']=checked.isoformat()
    release_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with csv_path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['movie_id','title','genres']);writer.writeheader();writer.writerows(extras)
    report_path=ROOT/'reports/imdb_release_sync.json'
    prior=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    markets=prior.get('markets',{'US':55} if prior else {})
    markets[region]=sum(any(r['region']==region for r in e.get('releases',[e['release']])) for e in payload['movies'].values())
    report={'checked_at':checked.isoformat(),'source_url':snapshot['source_url'],'markets':markets,
            'added_films':list(dict.fromkeys(prior.get('added_films',[])+added)),'release_entries':len(payload['movies']),
            'note':'Release-calendar snapshot, not confirmed local cinema availability. No ratings imported.'}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"IMDb {region}: {len(added)} new films; {markets[region]} sourced release dates.")

if __name__=='__main__':main()
