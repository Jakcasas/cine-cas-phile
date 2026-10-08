"""Import reviewed Galaxy Cinema detail metadata, keeping sources and market."""
import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from tools.sync_movie_images import aliases

ROOT=Path(__file__).resolve().parents[1]
GENRES={'Hành động':'Action','Tâm lý':'Drama','Hài':'Comedy','Kinh dị':'Horror','Tình cảm':'Romance','Lãng mạn':'Romance','Hoạt hình':'Animation','Khoa học viễn tưởng':'Sci-Fi'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('snapshot',type=Path)
    parser.add_argument('--now-slugs',default='')
    args=parser.parse_args()
    data=json.loads(args.snapshot.read_text(encoding='utf-8'))
    checked=datetime.fromisoformat(data['checked_at']).date().isoformat()
    now=set(args.now_slugs.split(','))
    csv_path=ROOT/'data/raw/catalog_extra.csv'
    with csv_path.open(encoding='utf-8',newline='') as f:extras=list(csv.DictReader(f))
    next_id=max(int(r['movie_id']) for r in extras)+1
    path=ROOT/'data/enrichment/galaxy_releases.json'
    payload=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'movies':{}}
    added=[]
    for item in data['movies']:
        url=urlparse(item['url'])
        if url.scheme!='https' or url.hostname!='www.galaxycine.vn' or not url.path.startswith('/dat-ve/'):raise ValueError('Unexpected source URL')
        image=urlparse(item['image_url'])
        if image.scheme!='https' or image.hostname!='cdn.galaxycine.vn':raise ValueError('Unexpected image source')
        title=item['title'].strip()
        # Prefer main opening date in the release notice to early screening date.
        date_text=(re.findall(r'\d{2}\.\d{2}\.\d{4}',item['early_notice']) or item['dates'])[-1]
        date=datetime.strptime(date_text.replace('.','/'),'%d/%m/%Y').date()
        name={'Người Mẹ Khác':'Other Mommy','Quyết Cua Anh Này':"Henry's First Date",'Quỷ Ăn Tạng 4: Hổ Tinh':'Death Whisperer: Saming the Werebeast'}.get(title,title)
        full=f'{name} ({date.year})'
        matches=[int(r['movie_id']) for r in extras if r['title'].endswith(f'({date.year})') and aliases(r['title']) & aliases(full)]
        if len(matches)>1:raise ValueError('Ambiguous existing film')
        mid=matches[0] if matches else next_id
        if not matches:
            next_id+=1
            genres=list(dict.fromkeys(GENRES[g] for g in item['genres'] if g in GENRES))
            if not genres:raise ValueError('No verified genre')
            extras.append({'movie_id':mid,'title':full,'genres':'|'.join(genres)});added.append(full)
        entry={'catalog_sources':['Galaxy Cinema'],'title_vi':title,'media_type':'film',
               'directors':list(dict.fromkeys(g for g in item['directors'] if g!='Đạo Diễn')),
               'poster_sources':[{'name':'Galaxy Cinema','page_url':item['url'],'image_url':item['image_url'],'fallback_url':None}],
               'release':{'date':date.isoformat(),'region':'VN','source':'Galaxy Cinema','url':item['url'],'checked_at':checked}}
        if url.path.strip('/').split('/')[-1] in now:
            entry['cinema_status']={'status':'now','source':'Galaxy Cinema','region':'VN','url':item['url'],'checked_at':checked}
        payload['movies'][str(mid)]=entry
    payload['updated_at']=checked
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with csv_path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['movie_id','title','genres']);writer.writeheader();writer.writerows(extras)
    report={'checked_at':checked,'source_url':'https://www.galaxycine.vn/phim-dang-chieu/','added_films':added,'verified_detail_entries':len(payload['movies']),'now_playing_verified':len(now),'note':'Opening dates exclude early screenings. Listing snapshot is not live showtimes.'}
    (ROOT/'reports/galaxy_release_sync.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Galaxy: {len(added)} new films; {len(payload["movies"])} verified Vietnamese releases.')

if __name__=='__main__':main()
