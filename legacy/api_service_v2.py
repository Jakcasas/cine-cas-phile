"""Recommendation Service managing loaded models and inference logic."""

import time
import os
from typing import Dict, List, Optional, Set, Tuple
import pandas as pd
import numpy as np

from src.data.loader import MovieLensLoader
from src.data.splitter import TemporalSplitter
from src.recommenders.base import BaseRecommender, RecommendationItem
from src.recommenders.popularity import PopularityRecommender
from src.recommenders.content_based import ContentBasedRecommender
from src.recommenders.matrix_factorization import BiasedMatrixFactorization
from src.recommenders.neural_mf import NeuralMFRecommender
from src.recommenders.hybrid import HybridRecommender
from src.api.schemas import (
    RecommendationsResponse,
    RecommendationResponseItem,
    HealthResponse,
    MovieDetailResponse,
)


class RecommendationService:
    """Singleton service powering the recommendation API."""

    _instance: Optional["RecommendationService"] = None

    def __init__(self):
        self.start_time = time.time()
        self.is_ready = False
        self.loader = MovieLensLoader()
        self.splitter = TemporalSplitter()

        self.movies_df: Optional[pd.DataFrame] = None
        self.train_df: Optional[pd.DataFrame] = None
        self.all_movie_ids: Set[int] = set()
        self.user_train_items: Dict[int, Set[int]] = {}

        self.models: Dict[str, BaseRecommender] = {}
        self.default_model_name = "hybrid"

    @classmethod
    def get_instance(cls) -> "RecommendationService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self):
        """Load data and initialize models."""
        if self.is_ready:
            return

        print("[Service] Loading datasets...")
        self.movies_df = self.loader.load_movies()
        ratings_df = self.loader.load_ratings()
        self.loader.build_mappings()

        self.all_movie_ids = set(self.movies_df["movie_id"].unique())

        print("[Service] Splitting ratings temporally...")
        train_df, val_df, test_df, _ = self.splitter.split(ratings_df)
        self.train_df = train_df
        self.user_train_items = TemporalSplitter.get_user_train_items(train_df)

        print("[Service] Fitting recommenders...")
        pop_model = PopularityRecommender()
        pop_model.fit(train_df, self.movies_df)

        cb_model = ContentBasedRecommender()
        cb_model.fit(train_df, self.movies_df)

        svd_model = BiasedMatrixFactorization(n_factors=32, n_epochs=12)
        svd_model.fit(train_df, self.movies_df)

        # Neural MF
        neural_model = NeuralMFRecommender(epochs=5, batch_size=2048)
        neural_model.fit(train_df, self.movies_df, val_df=val_df)

        # Hybrid
        hybrid_model = HybridRecommender()
        hybrid_model.fit(train_df, self.movies_df)

        self.models = {
            "popularity": pop_model,
            "content": cb_model,
            "svd": svd_model,
            "neural": neural_model,
            "hybrid": hybrid_model,
        }

        self.is_ready = True
        print("[Service] All models fitted and ready for inference!")

    def recommend_for_user(
        self, user_id: int, k: int = 10, model_name: str = "hybrid"
    ) -> RecommendationsResponse:
        """Generates recommendations with automatic cold-start fallback."""
        if not self.is_ready:
            raise RuntimeError("Recommendation service is not initialized.")

        t0 = time.time()
        model_key = model_name.lower().strip()
        if model_key not in self.models:
            model_key = self.default_model_name

        model = self.models[model_key]

        is_fallback = False
        seen_items = self.user_train_items.get(user_id, set())
        if not seen_items or user_id < 0:
            is_fallback = True

        # Candidates are all movies not seen in train
        candidates = list(self.all_movie_ids - seen_items)

        items = model.recommend(user_id, k=k, candidate_movie_ids=candidates)
        elapsed_ms = (time.time() - t0) * 1000.0

        resp_items = [
            RecommendationResponseItem(
                movie_id=item.movie_id,
                title=item.title,
                genres=item.genres,
                score=item.score,
                reason=item.reason,
            )
            for item in items
        ]

        return RecommendationsResponse(
            user_id=user_id,
            model=model.name,
            is_fallback=is_fallback,
            count=len(resp_items),
            latency_ms=round(elapsed_ms, 2),
            recommendations=resp_items,
        )

    def cold_start_by_genres(
        self, preferred_genres: List[str], k: int = 10
    ) -> List[RecommendationResponseItem]:
        """Interactive cold-start matching by preferred genres."""
        if not self.is_ready:
            raise RuntimeError("Recommendation service is not initialized.")

        pref_set = {g.strip().lower() for g in preferred_genres if g.strip()}
        if not pref_set:
            pop = self.models["popularity"]
            items = pop.recommend(user_id=-1, k=k)
            return [
                RecommendationResponseItem(
                    movie_id=it.movie_id,
                    title=it.title,
                    genres=it.genres,
                    score=it.score,
                    reason=it.reason,
                )
                for it in items
            ]

        cb_model: ContentBasedRecommender = self.models["content"]
        query_doc = " ".join(pref_set)
        query_vec = cb_model.vectorizer.transform([query_doc]).toarray()[0]
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec = query_vec / q_norm

        sims = np.dot(cb_model.movie_vectors, query_vec)

        # Blend with shrinkage popularity
        pop_model: PopularityRecommender = self.models["popularity"]
        scores = []
        ordered_mids = []
        for idx in range(len(cb_model.movie_vectors)):
            mid = cb_model.idx_to_movie_id[idx]
            sim = sims[idx]
            pop_score = (pop_model.movie_scores.get(mid, 3.5) - 1.0) / 4.0
            # 70% genre match + 30% popularity
            blended = 0.7 * sim + 0.3 * pop_score
            scores.append(blended)
            ordered_mids.append(mid)

        top_indices = np.argsort(scores)[::-1][:k]
        results = []
        for idx in top_indices:
            mid = ordered_mids[idx]
            score = scores[idx]
            genres = cb_model._get_movie_genres(mid)
            matched = pref_set.intersection({g.lower() for g in genres.split("|")})
            matched_str = ", ".join(m.title() for m in matched) if matched else "genre selection"
            results.append(
                RecommendationResponseItem(
                    movie_id=mid,
                    title=cb_model._get_movie_title(mid),
                    genres=genres,
                    score=round(float(score), 3),
                    reason=f"Recommended for your preference in {matched_str}",
                )
            )

        return results

    def get_movie_detail(self, movie_id: int) -> Optional[MovieDetailResponse]:
        """Retrieve movie metadata and top similar movies."""
        if not self.is_ready:
            raise RuntimeError("Recommendation service is not initialized.")

        meta = self.models["popularity"].movie_meta.get(movie_id)
        if not meta:
            return None

        # Similar movies using CB vectors
        cb_model: ContentBasedRecommender = self.models["content"]
        similar_items: List[RecommendationResponseItem] = []
        if movie_id in cb_model.movie_id_to_idx:
            target_idx = cb_model.movie_id_to_idx[movie_id]
            target_vec = cb_model.movie_vectors[target_idx]
            sims = np.dot(cb_model.movie_vectors, target_vec)
            top_sim_indices = np.argsort(sims)[::-1][1:6]  # skip itself
            for s_idx in top_sim_indices:
                s_mid = cb_model.idx_to_movie_id[s_idx]
                similar_items.append(
                    RecommendationResponseItem(
                        movie_id=s_mid,
                        title=cb_model._get_movie_title(s_mid),
                        genres=cb_model._get_movie_genres(s_mid),
                        score=round(float(sims[s_idx]), 3),
                        reason=f"Similar movie ({sims[s_idx]:.0%} genre similarity)",
                    )
                )

        return MovieDetailResponse(
            movie_id=movie_id,
            title=meta["title"],
            genres=meta["genres"],
            year=meta.get("year"),
            similar_movies=similar_items,
        )

    def health(self) -> HealthResponse:
        return HealthResponse(
            status="healthy" if self.is_ready else "initializing",
            version="2.0.0",
            loaded_models=list(self.models.keys()),
            catalog_size=len(self.all_movie_ids),
            users_count=len(self.user_train_items),
            uptime_seconds=round(time.time() - self.start_time, 2),
        )
