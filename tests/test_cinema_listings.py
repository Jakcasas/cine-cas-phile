import json
from src.api.enrichment import MovieEnrichment


def test_country_cinema_listings_are_validated_without_overwriting(tmp_path):
    listing={'status':'now','region':'US','source':'Harkins Theatres','url':'https://www.harkins.com/movies/digger','listing_url':'https://www.harkins.com/movies','checked_at':'2026-10-09'}
    japan={**listing,'status':'upcoming','region':'JP','source':'TOHO Cinemas','url':'https://hlo.tohotheater.jp/net/movie/TNPI3060J01.do?sakuhin_cd=029272','listing_url':'https://hlo.tohotheater.jp/net/movie/TNPI3080J01.do','date':'2026-10-16'}
    invalid=[{**listing,'region':'FR'}, {**listing,'url':'https://evil.example/'}, {**listing,'checked_at':'2026-02-31'}, {**listing,'source':'IMDb'}, {**listing,'listing_url':'https://user:password@www.harkins.com/movies'}, {**listing,'date':'2026-02-31'}, {**listing,'show_date':'wrong'}]
    (tmp_path/'cinema_listings.json').write_text(json.dumps({'movies':{'1':{'cinema_listings':[listing,japan,*invalid]}}}),encoding='utf-8')
    movie=MovieEnrichment(tmp_path/'movie_images.json').enrich({'movie_id':1,'rating':None})
    assert movie['cinema_listings']==[listing,japan]
    assert movie['rating'] is None
    assert movie['external_ratings']==[]


def test_chain_posters_and_real_calendar_dates(tmp_path):
    (tmp_path/'cinema_listings.json').write_text(json.dumps({'movies':{'1':{'poster_sources':[{'name':'Pathé','page_url':'https://www.pathe.fr/films/digger-51293','image_url':'https://media.pathe.fr/movie/poster.jpg'}],'releases':[{'region':'FR','date':'2026-02-31','url':'https://www.pathe.fr/films/digger-51293'}]}}}),encoding='utf-8')
    movie=MovieEnrichment(tmp_path/'movie_images.json').enrich({'movie_id':1})
    assert movie['poster_urls']==['https://media.pathe.fr/movie/poster.jpg']
    assert 'release' not in movie
