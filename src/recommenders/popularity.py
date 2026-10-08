"""Popularity baseline with Bayesian shrinkage (IMDb damping)."""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from src.recommenders.base import BaseRecommender, RecommendationItem


class PopularityRecommender(BaseRecommender):
    """Recommender that ranks movies by shrinkage-damped popularity."""

    def __init__(self, shrinkage_m: float = 25.0):
        super().__init__(name="Popularity-Shrinkage")
        self.shrinkage_m = shrinkage_m
        self.global_mean: float = 3.5
        self.movie_scores: Dict[int, float] = {}
        self.movie_counts: Dict[int, int] = {}
        self.movie_means: Dict[int, float] = {}
        self.ranked_movie_ids: List[int] = []

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)

        self.global_mean = float(train_df["rating"].mean())
        grouped = train_df.groupby("movie_id")["rating"]
        counts = grouped.count().to_dict()
        means = grouped.mean().to_dict()

        scores = {}
        m = self.shrinkage_m
        C = self.global_mean

        for movie_id in self.all_movie_ids:
            v = counts.get(movie_id, 0)
            r = means.get(movie_id, C)
            score = (v / (v + m)) * r + (m / (v + m)) * C
            scores[movie_id] = score
            self.movie_counts[movie_id] = v
            self.movie_means[movie_id] = r

        self.movie_scores = scores
        # Sort descending by score, tiebreak by rating count
        self.ranked_movie_ids = sorted(
            scores.keys(), key=lambda mid: (scores[mid], self.movie_counts.get(mid, 0)), reverse=True
        )
        self.is_fitted = True

    def predict(self, user_id: int, movie_id: int) -> float:
        return self.movie_scores.get(movie_id, self.global_mean)

    def recommend(
        self,
        user_id: int,
        k: int = 10,
        candidate_movie_ids: Optional[List[int]] = None,
    ) -> List[RecommendationItem]:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        candidates_pool = (
            candidate_movie_ids
            if candidate_movie_ids is not None
            else self.ranked_movie_ids
        )
        cand_set = set(candidates_pool)

        results: List[RecommendationItem] = []
        for movie_id in self.ranked_movie_ids:
            if movie_id in cand_set:
                score = self.movie_scores[movie_id]
                cnt = self.movie_counts.get(movie_id, 0)
                mean_r = self.movie_means.get(movie_id, self.global_mean)
                results.append(
                    RecommendationItem(
                        movie_id=movie_id,
                        title=self._get_movie_title(movie_id),
                        genres=self._get_movie_genres(movie_id),
                        score=round(score, 3),
                        reason=f"Community Favorite (Bayesian score: {score:.2f}, {cnt} reviews, avg: {mean_r:.1f})",
                    )
                )
                if len(results) >= k:
                    break

        return results
