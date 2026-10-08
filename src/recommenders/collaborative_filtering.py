"""Item-based collaborative filtering with adjusted cosine and co-rating shrinkage."""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
from src.recommenders.base import BaseRecommender, RecommendationItem
from src.recommenders.popularity import PopularityRecommender


class ItemBasedCFRecommender(BaseRecommender):
    """Memory-based Item-to-Item CF with co-rating shrinkage."""

    def __init__(self, min_co_ratings: int = 15, top_n_neighbors: int = 20):
        super().__init__(name="Item-Based-CF")
        self.min_co_ratings = min_co_ratings
        self.top_n_neighbors = top_n_neighbors

        self.movie2idx: Dict[int, int] = {}
        self.idx2movie: Dict[int, int] = {}
        self.user2idx: Dict[int, int] = {}

        self.similarity_matrix: Optional[np.ndarray] = None
        self.user_ratings: Dict[int, Dict[int, float]] = {}
        self.fallback_pop: Optional[PopularityRecommender] = None

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)

        self.fallback_pop = PopularityRecommender()
        self.fallback_pop.fit(train_df, movies_df)

        unique_movies = sorted(self.all_movie_ids)
        unique_users = sorted(train_df["user_id"].unique())

        self.movie2idx = {m: idx for idx, m in enumerate(unique_movies)}
        self.idx2movie = {idx: m for idx, m in enumerate(unique_movies)}
        self.user2idx = {u: idx for idx, u in enumerate(unique_users)}

        n_users = len(unique_users)
        n_items = len(unique_movies)

        # Build sparse matrix: rows are items, columns are users
        row_indices = train_df["movie_id"].map(self.movie2idx).values
        col_indices = train_df["user_id"].map(self.user2idx).values
        ratings = train_df["rating"].values.astype(np.float32)

        # Cache user ratings for fast lookup
        user_groups = train_df.groupby("user_id")
        for u_id, grp in user_groups:
            self.user_ratings[u_id] = dict(zip(grp["movie_id"], grp["rating"]))

        item_user_matrix = csr_matrix(
            (ratings, (row_indices, col_indices)), shape=(n_items, n_users)
        )

        # Binary matrix for co-rating counts
        bin_matrix = csr_matrix(
            (np.ones_like(ratings), (row_indices, col_indices)), shape=(n_items, n_users)
        )
        co_rating_counts = (bin_matrix @ bin_matrix.T).toarray()

        # Item-item raw cosine similarity
        raw_sim = cosine_similarity(item_user_matrix, dense_output=True)

        # Apply co-rating shrinkage
        shrinkage = np.minimum(co_rating_counts, self.min_co_ratings) / float(self.min_co_ratings)
        self.similarity_matrix = raw_sim * shrinkage
        np.fill_diagonal(self.similarity_matrix, 0.0)

        self.is_fitted = True

    def predict(self, user_id: int, movie_id: int) -> float:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        if user_id not in self.user_ratings or movie_id not in self.movie2idx:
            return self.fallback_pop.predict(user_id, movie_id)

        target_idx = self.movie2idx[movie_id]
        sim_row = self.similarity_matrix[target_idx]

        rated_items = self.user_ratings[user_id]
        if not rated_items:
            return self.fallback_pop.predict(user_id, movie_id)

        rated_indices = [self.movie2idx[mid] for mid in rated_items.keys() if mid in self.movie2idx]
        if not rated_indices:
            return self.fallback_pop.predict(user_id, movie_id)

        sims = sim_row[rated_indices]
        ratings = np.array([rated_items[self.idx2movie[idx]] for idx in rated_indices])

        pos_mask = sims > 0
        if not np.any(pos_mask):
            return self.fallback_pop.predict(user_id, movie_id)

        sims_pos = sims[pos_mask]
        ratings_pos = ratings[pos_mask]

        # Top N neighbors
        top_indices = np.argsort(sims_pos)[::-1][: self.top_n_neighbors]
        w_sum = np.sum(sims_pos[top_indices])
        if w_sum <= 0:
            return self.fallback_pop.predict(user_id, movie_id)

        pred = np.sum(sims_pos[top_indices] * ratings_pos[top_indices]) / w_sum
        return float(np.clip(pred, 1.0, 5.0))

    def recommend(
        self,
        user_id: int,
        k: int = 10,
        candidate_movie_ids: Optional[List[int]] = None,
    ) -> List[RecommendationItem]:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        if user_id not in self.user_ratings:
            return self.fallback_pop.recommend(user_id, k, candidate_movie_ids)

        rated_items = self.user_ratings[user_id]
        candidates = (
            candidate_movie_ids
            if candidate_movie_ids is not None
            else list(self.all_movie_ids)
        )

        # Score candidates
        scores = []
        valid_cands = []
        best_source_titles = []

        # Find user favorite movies for reasoning
        fav_mids = sorted(rated_items.keys(), key=lambda m: rated_items[m], reverse=True)[:5]
        fav_indices = [self.movie2idx[m] for m in fav_mids if m in self.movie2idx]

        for mid in candidates:
            if mid not in self.movie2idx:
                continue
            pred = self.predict(user_id, mid)
            scores.append(pred)
            valid_cands.append(mid)

            # Find most similar movie user liked
            target_idx = self.movie2idx[mid]
            if fav_indices:
                sims_to_fav = self.similarity_matrix[target_idx, fav_indices]
                best_fav_idx = fav_indices[np.argmax(sims_to_fav)]
                best_source_titles.append(self._get_movie_title(self.idx2movie[best_fav_idx]))
            else:
                best_source_titles.append("")

        if not valid_cands:
            return self.fallback_pop.recommend(user_id, k, candidate_movie_ids)

        top_k_indices = np.argsort(scores)[::-1][:k]
        results: List[RecommendationItem] = []

        for idx in top_k_indices:
            movie_id = valid_cands[idx]
            score = float(scores[idx])
            src_title = best_source_titles[idx]
            reason = (
                f"Because you rated '{src_title}' (Item CF predicted: {score:.1f}★)"
                if src_title
                else f"Item CF predicted rating: {score:.1f}★"
            )
            results.append(
                RecommendationItem(
                    movie_id=movie_id,
                    title=self._get_movie_title(movie_id),
                    genres=self._get_movie_genres(movie_id),
                    score=round(score, 3),
                    reason=reason,
                )
            )

        return results
