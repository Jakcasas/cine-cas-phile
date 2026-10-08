import json
from src.api.enrichment import MovieEnrichment


def test_missing_enrichment_is_optional(tmp_path):
    movie = {"movie_id": 1, "title": "Toy Story", "score": .7}
    assert MovieEnrichment(tmp_path / "missing.json").enrich(movie) == movie


def test_source_priority_and_unsafe_urls(tmp_path):
    path = tmp_path / "images.json"
    path.write_text(json.dumps({"movies": {"1": {"title_vi": "Câu chuyện đồ chơi", "poster_sources": [
        {"name": "FshareTV", "page_url": "https://fsharetv.com/movie/toy-story", "image_url": "https://m.media-amazon.com/one.jpg"},
        {"name": "PhimMoi", "page_url": "https://phimmoic.ws/phim/toy-story", "image_url": "https://phimmoic.ws/poster.webp"},
        {"name": "PhimMoi", "page_url": "javascript:alert(1)", "image_url": "https://untrusted.example/image.jpg"}
    ]}}}), encoding="utf-8")
    movie = {"movie_id": 1, "title": "Toy Story", "score": .7, "reason": "genre match"}
    enriched = MovieEnrichment(path).enrich(movie)
    assert enriched["poster_urls"] == ["https://phimmoic.ws/poster.webp", "https://m.media-amazon.com/one.jpg"]
    assert enriched["title_vi"] == "Câu chuyện đồ chơi"
    assert enriched["score"] == movie["score"] and enriched["reason"] == movie["reason"]
    assert len(enriched["poster_sources"]) == 2
    assert "poster_urls" not in movie
