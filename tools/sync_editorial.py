"""Import public MUBI and Letterboxd metadata without copying reviews or plots."""
import csv
from datetime import datetime, timezone
import json
import re
from concurrent.futures import ThreadPoolExecutor
from src import settings
from src.data.catalog import load_catalog
from tools.sync_movie_images import fetch, aliases

GENRES = {'Science Fiction':'Sci-Fi','Music':'Musical','Family':"Children's",'Animated':'Animation'}
ALLOWED = {'Action','Adventure','Animation',"Children's",'Comedy','Crime','Documentary','Drama','Fantasy',
           'Film-Noir','Horror','Musical','Mystery','Romance','Sci-Fi','Thriller','War','Western'}
LB_SLUGS = ['harakiri','the-human-condition-iii-a-soldiers-prayer','12-angry-men','come-and-see',
            'high-and-low','seven-samurai','the-shawshank-redemption','the-godfather-part-ii',
            'the-human-condition-i-no-greater-love','city-of-god','the-lord-of-the-rings-the-return-of-the-king',
            'schindlers-list','yi-yi','cinema-paradiso','ikiru','parasite-2019','the-good-the-bad-and-the-ugly',
            'the-godfather','ran','la-haine','le-trou','autumn-sonata','the-dark-knight','a-brighter-summer-day',
            'the-human-condition-ii-road-to-eternity','grave-of-the-fireflies','neon-genesis-evangelion-the-end-of-evangelion',
            'the-battle-of-algiers','i-am-cuba','goodfellas','the-matrix','toy-story','american-beauty']
MUBI_SLUGS = ['taxi-driver','the-matrix','american-beauty','toy-story','fight-club','pulp-fiction',
              'the-godfather','the-godfather-part-ii','seven-samurai','stalker','in-the-mood-for-love',
              'chungking-express','fallen-angels','mulholland-drive','persona','the-seventh-seal',
              'cinema-paradiso','a-brighter-summer-day','yi-yi','la-haine','ran','come-and-see',
              'perfect-days','parasite','the-fall','amores-perros','12-angry-men','the-shawshank-redemption']


def jsonld(soup):
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield json.loads(re.sub(r'/\*.*?\*/','',script.get_text(),flags=re.S))
        except (ValueError,TypeError):
            continue


def letterboxd(slug):
    url='https://letterboxd.com/film/'+slug+'/'
    soup=fetch(url)
    movie=next((d for d in jsonld(soup) if d.get('@type')=='Movie'),None)
    if not movie or not movie.get('dateCreated'):
        return None
    rating=movie.get('aggregateRating',{})
    imdb=soup.select_one('a[href*="imdb.com/title/"]')
    imdb_id=re.search(r'tt\d+',imdb['href'])[0] if imdb else None
    return {'title':movie['name'],'year':int(movie['dateCreated'][:4]),'genres':movie.get('genre',[]),
            'image_url':movie.get('image'),'page_url':url,'name':'Letterboxd','media_type':'film',
            'imdb_id':imdb_id,'rating':rating.get('ratingValue'),'rating_count':rating.get('ratingCount'),
            'directors':[p['name'] for p in movie.get('director',[])]}


def main():
    catalog=load_catalog(settings.DATA_DIR)
    index={}
    for movie in catalog.itertuples():
        for title in aliases(movie.title):
            index.setdefault((title,int(movie.year)),set()).add(int(movie.movie_id))
    path=settings.ROOT/'data'/'enrichment'/'editorial.json'
    previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    entries=previous.get('movies',{})
    extra_path=settings.DATA_DIR/'catalog_extra.csv'
    extras=[]
    if extra_path.exists():
        with extra_path.open(encoding='utf-8',newline='') as handle:extras=list(csv.DictReader(handle))
    next_id=max([int(row['movie_id']) for row in extras]+[999999])+1
    now=datetime.now(timezone.utc).isoformat()

    def add(item):
        nonlocal next_id
        desired=set().union(*(index.get((key,item['year']),set()) for key in aliases(item['title'])))
        if len(desired)>1:return
        if desired:mid=desired.pop()
        else:
            mid=next_id;next_id+=1
            genres=[GENRES.get(g,g) for g in item['genres']]
            genres=[g for g in genres if g in ALLOWED] or ['Drama']
            extras.append({'movie_id':mid,'title':f"{item['title']} ({item['year']})",'genres':'|'.join(dict.fromkeys(genres))})
            for key in aliases(item['title']):index.setdefault((key,item['year']),set()).add(mid)
        entry=entries.setdefault(str(mid),{'poster_sources':[],'catalog_sources':[],'external_ratings':[]})
        name=item['name']
        entry.update({'media_type':item['media_type'],'directors':item.get('directors',[]),
                      'imdb_id':item.get('imdb_id') or entry.get('imdb_id'),
                      'episode_count':item.get('episode_count')})
        if name not in entry['catalog_sources']:entry['catalog_sources'].append(name)
        source={'name':name,'page_url':item['page_url'],'image_url':item['image_url'],'fallback_url':item.get('fallback_url')}
        entry['poster_sources']=[s for s in entry['poster_sources'] if s['name']!=name]+[source]
        if item.get('still_url'):entry['still_urls']=[item['still_url']]
        if item.get('rating') is not None:
            score={'provider':name,'audience':'audience','value':float(item['rating']),'scale':5,
                   'count':item.get('rating_count'),'url':item['page_url'],'checked_at':now}
            entry['external_ratings']=[r for r in entry['external_ratings'] if r['provider']!=name]+[score]

    mubi=fetch('https://mubi.com/en/vn')
    data=json.loads(mubi.select_one('script#__NEXT_DATA__').get_text())['props']['pageProps']
    mubi_films=list(data.get('trendingFilms',[]))
    errors=[]
    def mubi_film(slug):
        soup=fetch('https://mubi.com/en/vn/films/'+slug)
        node=soup.select_one('script#__NEXT_DATA__')
        if not node:return None
        return json.loads(node.get_text())['props']['pageProps'].get('initFilm')
    with ThreadPoolExecutor(max_workers=3) as pool:
        for slug,future in [(slug,pool.submit(mubi_film,slug)) for slug in MUBI_SLUGS]:
            try:
                f=future.result()
                if f:mubi_films.append(f)
            except Exception as error:errors.append({'source':'MUBI','slug':slug,'error':str(error)})
    for f in mubi_films:
        if f.get('episode') or f.get('series') or 'Erotica' in f.get('genres',[]):continue
        artwork=next((a['image_url'] for a in f.get('artworks',[]) if a.get('format')=='cover_artwork_vertical'),None)
        still=f.get('stills',{}).get('standard') or f.get('still_url')
        add({'title':f['title'],'year':f['year'],'genres':f['genres'],'image_url':artwork or still,
             'still_url':still,'fallback_url':still,'page_url':f['web_url'],'name':'MUBI','media_type':'film',
             'rating':f.get('average_rating'),'rating_count':f.get('number_of_ratings'),
             'directors':[d['name'] for d in f.get('directors',[])]})
    series_soup=fetch('https://mubi.com/en/vn/series/la-mesias')
    s=json.loads(series_soup.select_one('script#__NEXT_DATA__').get_text())['props']['pageProps']['series']
    season=s['seasons'][0]
    image=next(a['image_url'] for a in season['artworks'] if a['format']=='cover_artwork_vertical')
    still=next(a['image_url'] for a in season['artworks'] if a['format']=='tile_artwork')
    add({'title':s['title'],'year':season['release_year'],'genres':s['genres'],'name':'MUBI',
         'image_url':image,'still_url':still,'page_url':'https://mubi.com/en/vn/series/la-mesias',
         'media_type':'series','episode_count':s['episode_count'],'rating':s.get('average_rating'),
         'rating_count':s.get('number_of_ratings')})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[(slug,pool.submit(letterboxd,slug)) for slug in LB_SLUGS]
        for slug,future in futures:
            try:
                item=future.result()
                if item:add(item)
                else:errors.append({'slug':slug,'error':'No public film metadata'})
            except Exception as error:errors.append({'slug':slug,'error':str(error)})
    extra_path.parent.mkdir(parents=True,exist_ok=True)
    with extra_path.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['movie_id','title','genres']);writer.writeheader();writer.writerows(extras)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'updated_at':now,'movies':entries},ensure_ascii=False,indent=2),encoding='utf-8')
    report={'supplemental_movies':len(extras),'editorial_movies':len(entries),
            'sources':{name:sum(name in e['catalog_sources'] for e in entries.values()) for name in ['MUBI','Letterboxd']},'errors':errors}
    (settings.ROOT/'reports'/'editorial_sync.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
