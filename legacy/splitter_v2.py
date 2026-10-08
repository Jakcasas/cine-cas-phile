"""Temporal user-based splitting module with zero data leakage."""

import json
import os
from typing import Dict, List, Set, Tuple
import numpy as np
import pandas as pd


class TemporalSplitter:
    """Splits ratings temporally per user to prevent future information leakage."""

    def __init__(
        self,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        random_seed: int = 42,
    ):
        assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-5, "Ratios must sum to 1.0"
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.random_seed = random_seed

    def split(
        self, ratings_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]:
        """Performs chronological splitting for each user.

        Guarantees:
        train_timestamp <= val_timestamp <= test_timestamp per user.
        """
        # Ensure ordered by user_id and timestamp
        df_sorted = ratings_df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)

        train_indices: List[int] = []
        val_indices: List[int] = []
        test_indices: List[int] = []

        # Group by user_id and split indices
        user_groups = df_sorted.groupby("user_id", sort=False).indices

        for user_id, indices in user_groups.items():
            n = len(indices)
            if n < 5:
                # Keep small user history in train to avoid degenerate models
                train_indices.extend(indices)
                continue

            n_train = int(np.floor(n * self.train_ratio))
            n_val = int(np.floor(n * self.val_ratio))
            if n_val == 0:
                n_val = 1
            n_test = n - n_train - n_val
            if n_test <= 0:
                n_test = 1
                n_train = n - n_val - n_test

            train_idx = indices[:n_train]
            val_idx = indices[n_train : n_train + n_val]
            test_idx = indices[n_train + n_val :]

            train_indices.extend(train_idx)
            val_indices.extend(val_idx)
            test_indices.extend(test_idx)

        train_df = df_sorted.iloc[train_indices].reset_index(drop=True)
        val_df = df_sorted.iloc[val_indices].reset_index(drop=True)
        test_df = df_sorted.iloc[test_indices].reset_index(drop=True)

        # Verification of no leakage
        leakage_detected = False
        train_max_time = train_df.groupby("user_id")["timestamp"].max()
        test_min_time = test_df.groupby("user_id")["timestamp"].min()
        common_users = set(train_max_time.index).intersection(set(test_min_time.index))
        for u in common_users:
            if train_max_time[u] > test_min_time[u]:
                leakage_detected = True
                break

        manifest = {
            "protocol": "temporal_per_user",
            "train_ratio": self.train_ratio,
            "val_ratio": self.val_ratio,
            "test_ratio": self.test_ratio,
            "random_seed": self.random_seed,
            "n_total": len(ratings_df),
            "n_train": len(train_df),
            "n_val": len(val_df),
            "n_test": len(test_df),
            "users_in_train": int(train_df["user_id"].nunique()),
            "users_in_val": int(val_df["user_id"].nunique()),
            "users_in_test": int(test_df["user_id"].nunique()),
            "items_in_train": int(train_df["movie_id"].nunique()),
            "items_in_val": int(val_df["movie_id"].nunique()),
            "items_in_test": int(test_df["movie_id"].nunique()),
            "leakage_detected": leakage_detected,
        }

        return train_df, val_df, test_df, manifest

    @staticmethod
    def get_user_train_items(train_df: pd.DataFrame) -> Dict[int, Set[int]]:
        """Maps each user_id to set of movie_ids seen in train set."""
        return train_df.groupby("user_id")["movie_id"].apply(set).to_dict()

    @staticmethod
    def get_candidate_items(
        all_movie_ids: Set[int], user_train_items: Set[int]
    ) -> List[int]:
        """Generates candidate movie_ids (all catalog movies minus train movies)."""
        return list(all_movie_ids - user_train_items)
