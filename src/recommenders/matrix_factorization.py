"""Biased Matrix Factorization (FunkSVD) with user and item biases."""

import time
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from src.recommenders.base import BaseRecommender, RecommendationItem
from src.recommenders.popularity import PopularityRecommender


class BiasedMatrixFactorization(BaseRecommender):
    """Latent Factor Matrix Factorization with explicit global, user and item biases."""

    def __init__(
        self,
        n_factors: int = 32,
        lr: float = 0.005,
        reg: float = 0.02,
        n_epochs: int = 15,
        random_state: int = 42,
    ):
        super().__init__(name="Biased-MF-SVD")
        self.n_factors = n_factors
        self.lr = lr
        self.reg = reg
        self.n_epochs = n_epochs
        self.random_state = random_state

        self.mu: float = 3.5
        self.user_bias: Optional[np.ndarray] = None
        self.item_bias: Optional[np.ndarray] = None
        self.user_factors: Optional[np.ndarray] = None
        self.item_factors: Optional[np.ndarray] = None

        self.user2idx: Dict[int, int] = {}
        self.movie2idx: Dict[int, int] = {}
        self.idx2movie: Dict[int, int] = {}
        self.training_time_sec: float = 0.0
        self.fallback_pop: Optional[PopularityRecommender] = None

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        start_time = time.time()
        self.set_movie_meta(movies_df)

        self.fallback_pop = PopularityRecommender()
        self.fallback_pop.fit(train_df, movies_df)

        unique_users = sorted(train_df["user_id"].unique())
        unique_movies = sorted(self.all_movie_ids)

        self.user2idx = {u: idx for idx, u in enumerate(unique_users)}
        self.movie2idx = {m: idx for idx, m in enumerate(unique_movies)}
        self.idx2movie = {idx: m for idx, m in enumerate(unique_movies)}

        n_users = len(unique_users)
        n_items = len(unique_movies)

        self.mu = float(train_df["rating"].mean())

        # Initialize biases and factors
        rng = np.random.RandomState(self.random_state)
        self.user_bias = np.zeros(n_users, dtype=np.float32)
        self.item_bias = np.zeros(n_items, dtype=np.float32)

        self.user_factors = (
            rng.normal(0, 1.0 / np.sqrt(self.n_factors), (n_users, self.n_factors))
        ).astype(np.float32)
        self.item_factors = (
            rng.normal(0, 1.0 / np.sqrt(self.n_factors), (n_items, self.n_factors))
        ).astype(np.float32)

        u_indices = train_df["user_id"].map(self.user2idx).values
        i_indices = train_df["movie_id"].map(self.movie2idx).values
        ratings = train_df["rating"].values.astype(np.float32)

        n_ratings = len(ratings)

        # SGD training loop
        lr = self.lr
        reg = self.reg
        mu = self.mu

        for epoch in range(self.n_epochs):
            # Shuffle indices
            perm = rng.permutation(n_ratings)
            for idx in perm:
                u = u_indices[idx]
                i = i_indices[idx]
                r = ratings[idx]

                # Prediction
                pred = mu + self.user_bias[u] + self.item_bias[i] + np.dot(
                    self.user_factors[u], self.item_factors[i]
                )
                err = r - pred

                # Update biases
                self.user_bias[u] += lr * (err - reg * self.user_bias[u])
                self.item_bias[i] += lr * (err - reg * self.item_bias[i])

                # Update latent factors
                u_f = self.user_factors[u].copy()
                i_f = self.item_factors[i].copy()

                self.user_factors[u] += lr * (err * i_f - reg * u_f)
                self.item_factors[i] += lr * (err * u_f - reg * i_f)

        self.training_time_sec = time.time() - start_time
        self.is_fitted = True

    def predict(self, user_id: int, movie_id: int) -> float:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        if user_id not in self.user2idx or movie_id not in self.movie2idx:
            return self.fallback_pop.predict(user_id, movie_id)

        u = self.user2idx[user_id]
        i = self.movie2idx[movie_id]

        pred = self.mu + self.user_bias[u] + self.item_bias[i] + np.dot(
            self.user_factors[u], self.item_factors[i]
        )
        return float(np.clip(pred, 1.0, 5.0))

    def recommend(
        self,
        user_id: int,
        k: int = 10,
        candidate_movie_ids: Optional[List[int]] = None,
    ) -> List[RecommendationItem]:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        if user_id not in self.user2idx:
            return self.fallback_pop.recommend(user_id, k, candidate_movie_ids)

        u = self.user2idx[user_id]
        u_factor = self.user_factors[u]
        u_b = self.user_bias[u]

        candidates = (
            candidate_movie_ids
            if candidate_movie_ids is not None
            else list(self.all_movie_ids)
        )

        cand_indices = []
        valid_mids = []
        for mid in candidates:
            if mid in self.movie2idx:
                cand_indices.append(self.movie2idx[mid])
                valid_mids.append(mid)

        if not cand_indices:
            return self.fallback_pop.recommend(user_id, k, candidate_movie_ids)

        cand_idx_arr = np.array(cand_indices)
        sub_item_bias = self.item_bias[cand_idx_arr]
        sub_item_factors = self.item_factors[cand_idx_arr]

        # Vectorized scoring
        scores = self.mu + u_b + sub_item_bias + np.dot(sub_item_factors, u_factor)
        scores = np.clip(scores, 1.0, 5.0)

        # Top k
        top_k_indices = np.argsort(scores)[::-1][:k]

        results: List[RecommendationItem] = []
        for idx in top_k_indices:
            movie_id = valid_mids[idx]
            score = float(scores[idx])
            results.append(
                RecommendationItem(
                    movie_id=movie_id,
                    title=self._get_movie_title(movie_id),
                    genres=self._get_movie_genres(movie_id),
                    score=round(score, 3),
                    reason=f"Predicted rating: {score:.1f}★ based on collaborative tastes",
                )
            )

        return results
