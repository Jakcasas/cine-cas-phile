"""Unit tests for data loader and temporal splitter."""

import pandas as pd
import numpy as np
import pytest
from src.data.splitter import TemporalSplitter


def test_temporal_splitter_no_leakage():
    # Construct synthetic interactions for 3 users
    data = []
    # User 1: 10 interactions chronologically ordered
    for i in range(10):
        data.append({"user_id": 1, "movie_id": 100 + i, "rating": 4.0, "timestamp": 1000 + i * 10})
    # User 2: 10 interactions
    for i in range(10):
        data.append({"user_id": 2, "movie_id": 200 + i, "rating": 3.0, "timestamp": 2000 + i * 10})

    df = pd.DataFrame(data)

    splitter = TemporalSplitter(train_ratio=0.8, val_ratio=0.1, test_ratio=0.1)
    train_df, val_df, test_df, manifest = splitter.split(df)

    assert len(train_df) + len(val_df) + len(test_df) == len(df)
    assert not manifest["leakage_detected"]

    # Verify per user timestamp ordering
    for u in [1, 2]:
        u_train_max = train_df[train_df["user_id"] == u]["timestamp"].max()
        u_val_min = val_df[val_df["user_id"] == u]["timestamp"].min()
        u_val_max = val_df[val_df["user_id"] == u]["timestamp"].max()
        u_test_min = test_df[test_df["user_id"] == u]["timestamp"].min()

        assert u_train_max <= u_val_min
        assert u_val_max <= u_test_min


def test_candidate_generation():
    all_movies = {1, 2, 3, 4, 5}
    train_movies = {1, 2}

    candidates = TemporalSplitter.get_candidate_items(all_movies, train_movies)
    assert set(candidates) == {3, 4, 5}
