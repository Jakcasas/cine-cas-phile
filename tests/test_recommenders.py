"""Unit tests for recommender models."""

import pandas as pd
import numpy as np
import pytest
from src.recommenders.popularity import PopularityRecommender
from src.recommenders.content_based import ContentBasedRecommender
from src.recommenders.matrix_factorization import BiasedMatrixFactorization
from src.recommenders.hybrid import HybridRecommender


@pytest.fixture
def sample_data():
    movies = pd.DataFrame([
        {"movie_id": 1, "title": "Toy Story (1995)", "genres": "Animation|Comedy", "genres_list": ["Animation", "Comedy"], "year": 1995},
        {"movie_id": 2, "title": "Jumanji (1995)", "genres": "Adventure|Fantasy", "genres_list": ["Adventure", "Fantasy"], "year": 1995},
        {"movie_id": 3, "title": "Heat (1995)", "genres": "Action|Crime", "genres_list": ["Action", "Crime"], "year": 1995},
        {"movie_id": 4, "title": "Casino (1995)", "genres": "Crime|Drama", "genres_list": ["Crime", "Drama"], "year": 1995},
    ])

    ratings = pd.DataFrame([
        {"user_id": 1, "movie_id": 1, "rating": 5.0, "timestamp": 100},
        {"user_id": 1, "movie_id": 2, "rating": 4.0, "timestamp": 101},
        {"user_id": 2, "movie_id": 3, "rating": 5.0, "timestamp": 102},
        {"user_id": 2, "movie_id": 4, "rating": 4.5, "timestamp": 103},
        {"user_id": 3, "movie_id": 1, "rating": 4.0, "timestamp": 104},
        {"user_id": 3, "movie_id": 3, "rating": 3.0, "timestamp": 105},
    ])
    return movies, ratings


def test_popularity_recommender(sample_data):
    movies_df, ratings_df = sample_data
    model = PopularityRecommender(shrinkage_m=2.0)
    model.fit(ratings_df, movies_df)

    recs = model.recommend(user_id=1, k=2)
    assert len(recs) == 2
    assert recs[0].score >= recs[1].score


def test_content_based_recommender(sample_data):
    movies_df, ratings_df = sample_data
    model = ContentBasedRecommender()
    model.fit(ratings_df, movies_df)

    # User 2 likes Action and Crime (Heat, Casino)
    recs = model.recommend(user_id=2, k=2)
    assert len(recs) == 2
    assert "Crime" in recs[0].genres or "Action" in recs[0].genres or "Drama" in recs[0].genres


def test_biased_mf_recommender(sample_data):
    movies_df, ratings_df = sample_data
    model = BiasedMatrixFactorization(n_factors=4, n_epochs=5)
    model.fit(ratings_df, movies_df)

    pred = model.predict(user_id=1, movie_id=3)
    assert 1.0 <= pred <= 5.0

    recs = model.recommend(user_id=1, k=2)
    assert len(recs) == 2


def test_hybrid_recommender(sample_data):
    movies_df, ratings_df = sample_data
    model = HybridRecommender(w_cf=0.5, w_content=0.3, w_pop=0.2)
    model.fit(ratings_df, movies_df)

    recs = model.recommend(user_id=1, k=2)
    assert len(recs) == 2
    assert recs[0].reason != ""
