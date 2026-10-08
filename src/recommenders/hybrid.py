"""Hybrid Recommender combining Matrix Factorization, Content-Based, and Popularity."""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from src.recommenders.base import BaseRecommender, RecommendationItem
from src.recommenders.matrix_factorization import BiasedMatrixFactorization
from src.recommenders.content_based import ContentBasedRecommender
from src.recommenders.popularity import PopularityRecommender


class HybridRecommender(BaseRecommender):
    """Ensemble recommender fusing Collaborative Filtering, Content-Based, and Shrinkage Popularity."""

    def __init__(
        self,
        w_cf: float = 0.50,
        w_content: float = 0.30,
        w_pop: float = 0.20,
    ):
        super().__init__(name="Hybrid-Ensemble")
        total_w = w_cf + w_content + w_pop
        self.w_cf = w_cf / total_w
        self.w_content = w_content / total_w
        self.w_pop = w_pop / total_w

        self.cf_model = BiasedMatrixFactorization()
        self.cb_model = ContentBasedRecommender()
        self.pop_model = PopularityRecommender()

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)

        self.cf_model.fit(train_df, movies_df)
        self.cb_model.fit(train_df, movies_df)
        self.pop_model.fit(train_df, movies_df)

        self.is_fitted = True

    def predict(self, user_id: int, movie_id: int) -> float:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        p_cf = self.cf_model.predict(user_id, movie_id)
        p_cb = self.cb_model.predict(user_id, movie_id)
        p_pop = self.pop_model.predict(user_id, movie_id)

        # Weighted prediction
        pred = self.w_cf * p_cf + self.w_content * p_cb + self.w_pop * p_pop
        return float(np.clip(pred, 1.0, 5.0))

    def recommend(
        self,
        user_id: int,
        k: int = 10,
        candidate_movie_ids: Optional[List[int]] = None,
    ) -> List[RecommendationItem]:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        candidates = (
            candidate_movie_ids
            if candidate_movie_ids is not None
            else list(self.all_movie_ids)
        )

        if not candidates:
            return []

        # If user is completely unknown to CF and CB, fallback to popularity
        if user_id not in self.cf_model.user2idx and user_id not in self.cb_model.user_profiles:
            return self.pop_model.recommend(user_id, k, candidate_movie_ids)

        # 1. CF Scores
        cf_preds = np.array([self.cf_model.predict(user_id, mid) for mid in candidates])
        # 2. Content Scores
        cb_preds = np.array([self.cb_model.predict(user_id, mid) for mid in candidates])
        # 3. Popularity Scores
        pop_preds = np.array([self.pop_model.predict(user_id, mid) for mid in candidates])

        # Min-max normalization for ranking fusion
        def min_max_norm(arr: np.ndarray) -> np.ndarray:
            min_v = arr.min()
            max_v = arr.max()
            if max_v - min_v > 1e-6:
                return (arr - min_v) / (max_v - min_v)
            return np.ones_like(arr) * 0.5

        norm_cf = min_max_norm(cf_preds)
        norm_cb = min_max_norm(cb_preds)
        norm_pop = min_max_norm(pop_preds)

        hybrid_scores = (
            self.w_cf * norm_cf + self.w_content * norm_cb + self.w_pop * norm_pop
        )

        top_k_indices = np.argsort(hybrid_scores)[::-1][:k]
        results: List[RecommendationItem] = []

        for idx in top_k_indices:
            movie_id = candidates[idx]
            raw_pred = self.predict(user_id, movie_id)
            movie_genres = self._get_movie_genres(movie_id)

            # Generate multi-signal reason
            top_genre = movie_genres.split("|")[0] if movie_genres else "Cinema"
            cf_score = cf_preds[idx]
            reason = (
                f"Hybrid Pick: {cf_score:.1f}★ taste match + strong {top_genre} genre alignment"
            )

            results.append(
                RecommendationItem(
                    movie_id=movie_id,
                    title=self._get_movie_title(movie_id),
                    genres=movie_genres,
                    score=round(raw_pred, 3),
                    reason=reason,
                )
            )

        return results
