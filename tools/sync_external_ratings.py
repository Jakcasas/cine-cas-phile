"""Verified public rating snapshots, with provider, scale and provenance."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from src import settings
from src.data.catalog import load_catalog
from tools.sync_movie_images import fetch, aliases, CACHE
from tools.sync_editorial import jsonld

# Explicit source URLs; parsed film name AND release year must match the catalog.
PAGES=[('The Matrix',1999,'matrix','the-matrix'),('Toy Story',1995,'toy_story','toy-story'),
       ('American Beauty',1999,'american_beauty','american-beauty'),
       ('The Godfather',1972,'godfather','the-godfather'),
       ('The Shawshank Redemption',1994,'shawshank_redemption','the-shawshank-redemption'),
       ('Pulp Fiction',1994,'pulp_fiction','pulp-fiction'),('Taxi Driver',1976,'taxi_driver','taxi-driver'),
       ('Fight Club',1999,'fight_club','fight-club'),('Parasite',2019,'parasite_2019','parasite'),
       ('The Dark Knight',2008,'the_dark_knight','the-dark-knight'),
       ('Perfect Days',2023,'perfect_days_2023','perfect-days'),
       ('City of God',2002,'city_of_god','city-of-god')]


def movie_schema(soup):
    return next((d for d in jsonld(soup) if isinstance(d,dict) and d.get('@type')=='Movie'),{})


def parse_rating_page(soup, provider, url, title, year, now):
    film=movie_schema(soup)
    if not aliases(film.get('name','')) & aliases(title):return []
    if str(film.get('dateCreated',film.get('datePublished','')))[:4]!=str(year):return []
    def score(value,scale,audience,count=None,**metadata):
        return {'provider':provider,'value':float(value),'scale':scale,'audience':audience,
                'count':count,'url':url,'checked_at':now,**metadata}
    if provider=='Rotten Tomatoes':
        node=soup.select_one('script#media-scorecard-json')
        if not node:return []
        data=json.loads(node.get_text());result=[]
        for key,audience in [('criticsScore','critics'),('audienceScore','audience')]:
            item=data.get(key,{})
            if item.get('score') not in {None,''}:
                result.append(score(item['score'],100,audience,item.get('bandedRatingCount') or item.get('reviewCount'),
                                    metric=item.get('title'),score_type=item.get('scoreType')))
        return result
    rating=film.get('aggregateRating',{})
    if rating.get('ratingValue') is None:return []
    return [score(rating['ratingValue'],float(rating.get('bestRating',100)),
                  'critics',rating.get('reviewCount'),metric='Metascore')]


def main():
    movies=load_catalog(settings.DATA_DIR);index={}
    for row in movies.itertuples():
        for key in aliases(row.title):index.setdefault((key,int(row.year)),set()).add(int(row.movie_id))
    def match(title,year):
        ids=set().union(*(index.get((key,int(year)),set()) for key in aliases(title)))
        return ids.pop() if len(ids)==1 else None
    now=datetime.now(timezone.utc).isoformat();entries={};errors=[]
    def add(mid,score):
        entry=entries.setdefault(str(mid),{'external_ratings':[]})
        entry['external_ratings']=[r for r in entry['external_ratings']
                                 if (r['provider'],r['audience'])!=(score['provider'],score['audience'])]+[score]
    # FshareTV publishes IMDb snapshots. Preserve the intermediary explicitly.
    urls=['https://fsharetv.com/']
    for page in range(1,137):
        urls.append('https://fsharetv.com/filter?'+urlencode({'genre':'','country':'','year':'',
                    'sort_by':'imdb_votes','sub':'','year_range':'','page':page}))
    for url in urls:
        file=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html')
        if not file.exists():continue
        soup=BeautifulSoup(file.read_text(encoding='utf-8'),'html.parser')
        for item in soup.select('.movie-item'):
            heading=item.find('b');link=item.select_one('a[href^="/movie/"]');chips=item.select('.chip')
            if not heading or not link or len(chips)<2:continue
            title=re.match(r'(.+)\s+\((\d{4})\)$',heading.get_text(strip=True))
            imdb=re.search(r'tt\d+',link['href'])
            value=re.search(r'\d+(?:\.\d+)?',chips[0].get_text())
            count=re.sub(r'\D','',chips[1].get_text())
            if not title or not imdb or not value:continue
            mid=match(title[1],title[2])
            if mid is not None:add(mid,{'provider':'IMDb','audience':'audience','value':float(value[0]),'scale':10,
                         'count':int(count) if count else None,'url':'https://www.imdb.com/title/'+imdb[0]+'/',
                         'via':'FshareTV','source_url':'https://fsharetv.com'+link['href'],'checked_at':now,
                         'metric':'IMDb snapshot via FshareTV'})
    tasks=[]
    def retrieve(title,year,provider,url):
        return parse_rating_page(fetch(url),provider,url,title,year,now)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for title,year,rt,mc in PAGES:
            mid=match(title,year)
            if mid is None:continue
            for provider,url in [('Rotten Tomatoes','https://www.rottentomatoes.com/m/'+rt),
                                 ('Metacritic','https://www.metacritic.com/movie/'+mc+'/')]:
                tasks.append((mid,provider,url,pool.submit(retrieve,title,year,provider,url)))
        for mid,provider,url,future in tasks:
            try:
                scores=future.result()
                if not scores:errors.append({'provider':provider,'url':url,'error':'No verified title/year rating'})
                for score in scores:add(mid,score)
            except Exception as error:errors.append({'provider':provider,'url':url,'error':str(error)})
    verified=settings.ROOT/'data/enrichment/verified_audience.json'
    if verified.exists():
        for seed in json.loads(verified.read_text(encoding='utf-8')).get('ratings',[]):
            mid=match(seed['title'],seed['year'])
            if mid is not None:add(mid,{k:v for k,v in seed.items() if k not in {'title','year'}})
    path=settings.ROOT/'data/enrichment/ratings.json'
    path.write_text(json.dumps({'updated_at':now,'movies':entries},ensure_ascii=False,indent=2),encoding='utf-8')
    counts={provider:sum(any(r['provider']==provider for r in e['external_ratings']) for e in entries.values())
            for provider in ['IMDb','Rotten Tomatoes','Metacritic']}
    report={'movies':len(entries),'sources':counts,'errors':errors}
    (settings.ROOT/'reports/ratings_sync.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
