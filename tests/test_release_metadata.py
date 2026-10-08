import json
from src.api.enrichment import MovieEnrichment


def test_release_sources_remain_separate_from_ratings(tmp_path):
    release={'date':'2026-10-16','region':'VN','source':'Galaxy Cinema','url':'https://www.galaxycine.vn/dat-ve/example/','checked_at':'2026-10-09'}
    entries={'movies':{'1':{'release':release,'poster_sources':[{'name':'Galaxy Cinema','page_url':release['url'],'image_url':'https://cdn.galaxycine.vn/media/example.jpg'}]}}}
    (tmp_path/'galaxy_releases.json').write_text(json.dumps(entries),encoding='utf-8')
    enrichment=MovieEnrichment(tmp_path/'movie_images.json')
    movie=enrichment.enrich({'movie_id':1,'rating':None})
    assert movie['release']==release
    assert movie['rating'] is None
    assert movie['external_ratings']==[]
    assert movie['poster_sources'][0]['name']=='Galaxy Cinema'


def test_untrusted_release_and_poster_urls_are_not_imported(tmp_path):
    entries={'movies':{'1':{'release':{'date':'2026-10-16','region':'VN','url':'https://evil.example/a'},'poster_sources':[{'name':'IMDb','page_url':'https://www.imdb.com/title/tt1/','image_url':'https://evil.example/poster.jpg'}]}}}
    (tmp_path/'imdb_releases.json').write_text(json.dumps(entries),encoding='utf-8')
    movie=MovieEnrichment(tmp_path/'movie_images.json').enrich({'movie_id':1})
    assert 'release' not in movie
    assert movie['poster_sources']==[]


def test_one_film_can_keep_different_release_dates_by_market(tmp_path):
    us={'date':'2026-10-02','region':'US','source':'IMDb','url':'https://www.imdb.com/title/tt31450459/','checked_at':'2026-10-09'}
    japan={**us,'date':'2026-10-09','region':'JP'}
    entries={'movies':{'1':{'release':us,'releases':[us,japan]}}}
    (tmp_path/'imdb_releases.json').write_text(json.dumps(entries),encoding='utf-8')
    movie=MovieEnrichment(tmp_path/'movie_images.json').enrich({'movie_id':1})
    assert [(r['region'],r['date']) for r in movie['releases']]==[('US','2026-10-02'),('JP','2026-10-09')]
