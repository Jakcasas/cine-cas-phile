import pytest
from fastapi.testclient import TestClient
from src.api import main
from src.api.profiles import ProfileStore


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'store',ProfileStore(tmp_path/'profiles.sqlite3'))
    with TestClient(main.app) as client:
        yield client


def test_personal_journey(client):
    profile=client.post('/profiles').json();pid=profile['profile_id']
    assert client.put(f'/profiles/{pid}/preferences',json={'genres':['Sci-Fi']}).status_code==200
    assert client.put(f'/profiles/{pid}/ratings/1',json={'rating':5}).status_code==200
    assert client.put(f'/profiles/{pid}/watchlist/2').status_code==200
    result=client.post('/discover',json={'profile_id':pid,'k':5}).json()
    assert not result['is_fallback'] and len(result['recommendations'])==5
    assert 1 not in {row['movie_id'] for row in result['recommendations']}
    saved=client.get(f'/profiles/{pid}').json()
    assert saved['ratings']=={'1':5.0} and saved['watchlist_movies'][0]['movie_id']==2
    assert client.delete(f'/profiles/{pid}/ratings/1').status_code==200
    assert client.delete(f'/profiles/{pid}/watchlist/2').status_code==200
    assert client.get(f'/profiles/{pid}').json()['watchlist']==[]


def test_validation_and_missing_records(client):
    pid=client.post('/profiles').json()['profile_id']
    assert client.put(f'/profiles/{pid}/ratings/1',json={'rating':6}).status_code==422
    assert client.put(f'/profiles/{pid}/ratings/999999',json={'rating':4}).status_code==404
    assert client.get('/profiles/missing').status_code==404
    assert client.post('/discover',json={'model':'made-up'}).status_code==422
    assert client.post('/discover',json={'preferred_genres':['Made-up']}).status_code==422
    assert client.post('/discover',json={'year_min':2000,'year_max':1900}).status_code==422
    assert client.get('/movies/999999').status_code==404
    svd=client.post('/discover',json={'profile_id':pid,'preferred_genres':['Drama'],'model':'svd'}).json()
    assert svd['is_fallback'] and 'SVD' in svd['fallback_reason']


def test_search_pagination_and_similar(client):
    page=client.get('/movies?q=Toy%20Story&page_size=1').json()
    assert page['total']>=1 and len(page['movies'])==1
    assert all('Toy Story' in row['title'] for row in page['movies'])
    first=client.get('/movies?page=1&page_size=3').json()['movies']
    second=client.get('/movies?page=2&page_size=3').json()['movies']
    assert not {m['movie_id'] for m in first}&{m['movie_id'] for m in second}
    similar=client.get('/movies/1').json()['similar_movies']
    assert 1 not in {m['movie_id'] for m in similar}
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200


def test_posters_reach_catalog_details_and_saved_lists(client, tmp_path, monkeypatch):
    import json
    from src.api.enrichment import MovieEnrichment
    path=tmp_path/'posters.json'
    path.write_text(json.dumps({'movies':{'1':{'title_vi':'Câu chuyện đồ chơi','poster_sources':[
        {'name':'PhimMoi','page_url':'https://phimmoic.ws/phim/toy-story',
         'image_url':'https://phimmoic.ws/storage/toy-story.webp'}]}}}),encoding='utf-8')
    monkeypatch.setattr(main.service,'enrichment',MovieEnrichment(path))
    detail=client.get('/movies/1').json()
    assert detail['poster_urls']==['https://phimmoic.ws/storage/toy-story.webp']
    search=client.get('/movies',params={'q':'Câu chuyện đồ chơi'}).json()
    assert search['total']==1 and search['movies'][0]['movie_id']==1
    pid=client.post('/profiles').json()['profile_id']
    client.put(f'/profiles/{pid}/watchlist/1')
    saved=client.get(f'/profiles/{pid}').json()['watchlist_movies'][0]
    assert saved['poster_urls']==detail['poster_urls']
