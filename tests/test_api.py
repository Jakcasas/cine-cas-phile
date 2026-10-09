"""Integration tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "hybrid" in data["loaded_models"]
    assert data["catalog_size"] > 0


def test_models_endpoint(client):
    response = client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 5


def test_search_without_accents(client):
    data = client.get('/movies', params={'q': ' la mesias '}).json()
    assert any(movie['title'] == 'La Mesías' for movie in data['movies'])


def test_search_exact_title_and_alias_priority(client):
    response = client.get('/movies', params={'q': 'Alien', 'sort': 'relevance'})
    assert response.status_code == 200
    assert response.json()['movies'][0]['title'] == 'Alien'
    response = client.get('/movies', params={'q': '룩백', 'sort': 'relevance'})
    assert response.status_code == 200
    assert any(movie['movie_id'] == 1000097 for movie in response.json()['movies'])


def test_search_relevance_handles_accents_and_articles():
    from src.api.service import search_relevance
    assert search_relevance({'title': 'Matrix, The'}, 'The Matrix') == 100
    assert search_relevance({'title_vi': 'Thế giới yên tĩnh'}, 'the gioi yen tinh') == 100
    assert search_relevance({'title': 'Aliens'}, 'Alien') < search_relevance({'title': 'Alien'}, 'Alien')


def test_recommendations_endpoint(client):
    response = client.get("/recommendations/1?k=5&model=hybrid")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 1
    assert data["count"] == 5
    assert len(data["recommendations"]) == 5
    assert "score" in data["recommendations"][0]
    assert "reason" in data["recommendations"][0]


def test_cold_start_fallback_for_unknown_user(client):
    response = client.get("/recommendations/999999?k=5&model=hybrid")
    assert response.status_code == 200
    data = response.json()
    assert data["is_fallback"] is True
    assert len(data["recommendations"]) == 5


def test_cold_start_genres_endpoint(client):
    payload = {"preferred_genres": ["Animation", "Children's"], "k": 5}
    response = client.post("/recommendations/cold-start", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


def test_editorial_catalog_and_series(client):
    data=client.get('/movies?source=MUBI&page_size=60').json()
    assert data['total']>=35
    assert all('MUBI' in m['catalog_sources'] for m in data['movies'])
    series=next(m for m in data['movies'] if m['title']=='La Mesías')
    assert series['media_type']=='series' and series['episode_count']==7
    assert series['rating_count']==0 and series['poster_urls']


def test_external_ratings_keep_audience_and_critics_separate(client):
    movie=client.get('/movies/2571').json()
    scores=movie['external_ratings']
    rt=[r for r in scores if r['provider']=='Rotten Tomatoes']
    assert {r['audience'] for r in rt}=={'audience','critics'}
    assert all(r['scale']==100 for r in rt)
    mc=[r for r in scores if r['provider']=='Metacritic']
    assert {r['scale'] for r in mc}=={10,100}
    assert next(r for r in scores if r['provider']=='Letterboxd')['scale']==5


def test_visual_upload_validation(client):
    response=client.post('/visual-search',files={'image':('scene.png',b'invalid','image/png')})
    assert response.status_code==422
    assert client.post('/visual-search').status_code==422
    status=client.get('/visual-search/status').json()
    assert status['ready'] and status['scene_images']>=35


def test_actual_scene_upload_returns_matching_film(client):
    import hashlib
    import numpy as np
    from src import settings
    with np.load(settings.ROOT/'artifacts/vision/image_index.npz',allow_pickle=False) as index:
        pos=next(i for i,(mid,kind) in enumerate(zip(index['movie_ids'],index['kinds'])) if mid==2571 and kind=='still')
        url=str(index['urls'][pos])
    reference=settings.ROOT/'runtime/reference-images'/(hashlib.sha256(url.encode()).hexdigest()+'.img')
    if not reference.exists():pytest.skip('Developer reference cache absent; not packaged in release')
    response=client.post('/visual-search?k=5',files={'image':('scene.jpg',reference.read_bytes(),'image/jpeg')})
    assert response.status_code==200
    matches=response.json()['matches']
    assert matches[0]['movie_id']==2571 and matches[0]['visual_similarity']>.95
    assert matches[0]['matched_image_kind']=='still'
    assert matches[0]['poster_urls']
    assert not list((settings.ROOT/'runtime').glob('upload*'))
