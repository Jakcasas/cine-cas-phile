"""Import reviewed official cinema listings; never infer now-playing from presales.

Snapshots contain public facts only. Unmatched cards must be reviewed for film
identity, original year and genres before adding them to the catalog.
"""
import argparse
import csv
import json
from pathlib import Path
from src.api.enrichment import CINEMAS, IMAGE_HOSTS, safe_url, valid_day
from src.data.catalog import load_catalog
from src import settings


def import_snapshot(snapshot, root=settings.ROOT):
    if not valid_day(snapshot.get('checked_at')):raise ValueError('Invalid snapshot date')
    path=root/'data/raw/catalog_extra.csv'
    with path.open(encoding='utf-8',newline='') as f:extras=list(csv.DictReader(f))
    known=set(load_catalog(root/'data/raw').movie_id)
    next_id=max(known)+1
    payload={'updated_at':snapshot['checked_at'],'movies':{}}
    added=[]
    reviewed_new=[]
    for market in snapshot['markets']:
        source=market['source']
        region,hosts=CINEMAS.get(source,(None,set()))
        if market.get('region')!=region or not safe_url(market.get('listing_url'),hosts):raise ValueError('Unexpected cinema market/source')
        for item in market['movies']:
            if item.get('status') not in {'now','upcoming'} or not safe_url(item.get('url'),hosts):raise ValueError('Invalid cinema listing')
            mid=item.get('movie_id')
            if mid is None:
                if not item.get('title') or not isinstance(item.get('year'),int) or not 1800<=item['year']<=2200:raise ValueError('New films need a reviewed original year')
                genres=item.get('genres',[])
                if not genres or not set(genres)<=set(settings.GENRES if hasattr(settings,'GENRES') else ['Action','Adventure','Animation',"Children's",'Comedy','Crime','Documentary','Drama','Fantasy','Film-Noir','Horror','Musical','Mystery','Romance','Sci-Fi','Thriller','War','Western']):raise ValueError('New films need verified genres')
                full=f"{item['title']} ({item['year']})"
                if full not in reviewed_new:reviewed_new.append(full)
                matching=[int(r['movie_id']) for r in extras if r['title']==full]
                mid=matching[0] if matching else next_id
                if not matching:
                    next_id+=1;extras.append({'movie_id':mid,'title':full,'genres':'|'.join(dict.fromkeys(genres))});known.add(mid);added.append(full)
            if mid not in known:raise ValueError('Unknown existing movie ID')
            entry=payload['movies'].setdefault(str(mid),{'catalog_sources':[],'cinema_listings':[],'releases':[],'poster_sources':[],'title_aliases':[]})
            if source not in entry['catalog_sources']:entry['catalog_sources'].append(source)
            listing={'status':item['status'],'region':region,'source':source,'url':item['url'],'listing_url':market['listing_url'],'checked_at':snapshot['checked_at']}
            for key in ('date','show_date'):
                if item.get(key):
                    if not valid_day(item[key]):raise ValueError('Invalid listing date')
                    listing[key]=item[key]
            if market.get('venue'):listing['venue']=market['venue']
            if listing not in entry['cinema_listings']:entry['cinema_listings'].append(listing)
            if item.get('date') and item.get('date_basis')!='calendar':
                release={'date':item['date'],'region':region,'source':source,'url':item['url'],'checked_at':snapshot['checked_at']}
                if item.get('rerelease'):release['kind']='rerelease'
                if release not in entry['releases']:entry['releases'].append(release)
            image=safe_url(item.get('image_url'),IMAGE_HOSTS)
            if item.get('image_url') and not image:raise ValueError('Unexpected cinema poster host')
            if image:
                poster={'name':source,'page_url':item['url'],'image_url':image,'fallback_url':None}
                if poster not in entry['poster_sources']:entry['poster_sources'].append(poster)
            for name in [item.get('source_title'),*item.get('aliases',[])]:
                if isinstance(name,str) and name not in entry['title_aliases']:entry['title_aliases'].append(name[:200])
            if item.get('directors'):entry['directors']=item['directors']
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['movie_id','title','genres']);writer.writeheader();writer.writerows(extras)
    destination=root/'data/enrichment/cinema_listings.json'
    destination.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report={'checked_at':snapshot['checked_at'],'cinema_films':len(payload['movies']),'cinema_listings':sum(len(e['cinema_listings']) for e in payload['movies'].values()),'added_films':reviewed_new,'added_films_this_import':added,'markets':[{'region':m['region'],'source':m['source'],'listing_url':m['listing_url'],'venue':m.get('venue'),'reviewed_cards':len(m['movies'])} for m in snapshot['markets']],'unmatched_cards':snapshot.get('unmatched_cards',[]),'limits':'Reviewed cinema-chain snapshot, not complete national coverage or live showtimes. Presales are upcoming; now listings expire after seven days. IMDb calendars supplement dates.'}
    (root/'reports/cinema_sync.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Cinema import: {len(added)} new films, {len(payload['movies'])} matched films, {report['cinema_listings']} market listings.")


def main():
    parser=argparse.ArgumentParser();parser.add_argument('snapshot',type=Path);args=parser.parse_args()
    import_snapshot(json.loads(args.snapshot.read_text(encoding='utf-8')))


if __name__=='__main__':main()
