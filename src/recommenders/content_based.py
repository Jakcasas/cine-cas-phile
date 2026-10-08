"""Content-based recommender using TF-IDF genre matching and profile modeling."""

from typing import Dict, List, Optional, Set
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.recommenders.base import BaseRecommender, RecommendationItem
from src.recommenders.popularity import PopularityRecommender


class ContentBasedRecommender(BaseRecommender):
    """Recommender based on movie genre TF-IDF similarities and user taste vectors."""

    def __init__(self, positive_threshold: float = 3.5):
        super().__init__(name="Content-Based-TFIDF")
        self.positive_threshold = positive_threshold
        self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w\'-]+\b")
        self.movie_vectors: Optional[np.ndarray] = None
        self.movie_id_to_idx: Dict[int, int] = {}
        self.idx_to_movie_id: Dict[int, int] = {}
        self.user_profiles: Dict[int, np.ndarray] = {}
        self.user_top_genres: Dict[int, List[str]] = {}
        self.fallback_pop: Optional[PopularityRecommender] = None

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)

        # Fit fallback
        self.fallback_pop = PopularityRecommender()
        self.fallback_pop.fit(train_df, movies_df)

        # Build genre strings
        genre_docs = []
        ordered_movie_ids = []
        for _, row in movies_df.iterrows():
            mid = row["movie_id"]
            genres_clean = " ".join(row["genres_list"])
            genre_docs.append(genres_clean)
            ordered_movie_ids.append(mid)

        tfidf_matrix = self.vectorizer.fit_transform(genre_docs).toarray()
        self.movie_vectors = tfidf_matrix
        self.movie_id_to_idx = {mid: idx for idx, mid in enumerate(ordered_movie_ids)}
        self.idx_to_movie_id = {idx: mid for idx, mid in enumerate(ordered_movie_ids)}

        # Build user profiles
        user_groups = train_df.groupby("user_id")
        for user_id, group in user_groups:
            # Weight: center around 2.5 so ratings >= 4 give high positive weights
            weights = (group["rating"].values - 2.5).astype(np.float32)
            # Only consider positive contributions
            pos_mask = weights > 0
            if not np.any(pos_mask):
                continue

            valid_mids = group["movie_id"].values[pos_mask]
            valid_weights = weights[pos_mask]

            vec_indices = [
                self.movie_id_to_idx[mid]
                for mid in valid_mids
                if mid in self.movie_id_to_idx
            ]
            if not vec_indices:
                continue

            sub_vecs = self.movie_vectors[vec_indices]
            # Weighted average
            profile = np.sum(sub_vecs * valid_weights[:, np.newaxis], axis=0)
            norm = np.linalg.norm(profile)
            if norm > 0:
                profile = profile / norm
                self.user_profiles[user_id] = profile

                # Find user top genre words
                feature_names = np.array(self.vectorizer.get_feature_names_out())
                top_word_indices = np.argsort(profile)[::-1][:3]
                self.user_top_genres[user_id] = [
                    feature_names[i].title()
                    for i in top_word_indices
                    if profile[i] > 0
                ]

        self.is_fitted = True

    def predict(self, user_id: int, movie_id: int) -> float:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        if user_id not in self.user_profiles or movie_id not in self.movie_id_to_idx:
            return self.fallback_pop.predict(user_id, movie_id)

        u_vec = self.user_profiles[user_id]
        m_vec = self.movie_vectors[self.movie_id_to_idx[movie_id]]

        similarity = float(np.dot(u_vec, m_vec))
        # Map similarity [0, 1] to rating [2.0, 5.0]
        pred_rating = 2.0 + 3.0 * similarity
        return max(1.0, min(5.0, pred_rating))

    def recommend(
        self,
        user_id: int,
        k: int = 10,
        candidate_movie_ids: Optional[List[int]] = None,
    ) -> List[RecommendationItem]:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        if user_id not in self.user_profiles:
            # Graceful fallback to popularity
            return self.fallback_pop.recommend(user_id, k, candidate_movie_ids)

        u_vec = self.user_profiles[user_id]
        candidates = (
            candidate_movie_ids
            if candidate_movie_ids is not None
            else list(self.all_movie_ids)
        )

        cand_indices = []
        valid_cands = []
        for mid in candidates:
            if mid in self.movie_id_to_idx:
                cand_indices.append(self.movie_id_to_idx[mid])
                valid_cands.append(mid)

        if not cand_indices:
            return self.fallback_pop.recommend(user_id, k, candidate_movie_ids)

        cand_matrix = self.movie_vectors[cand_indices]
        sims = np.dot(cand_matrix, u_vec)

        # Sort descending
        top_k_indices = np.argsort(sims)[::-1][:k]

        user_top_g = set(self.user_top_genres.get(user_id, []))
        results: List[RecommendationItem] = []

        for idx in top_k_indices:
            movie_id = valid_cands[idx]
            sim = float(sims[idx])
            movie_genres = self._get_movie_genres(movie_id)
            movie_g_set = set(movie_genres.split("|"))
            matched_genres = user_top_g.intersection(movie_g_set)
            if matched_genres:
                genre_str = ", ".join(matched_genres)
                reason = f"Matches your taste in {genre_str} (similarity: {sim:.0%})"
            else:
                reason = f"High genre match with your watch history (similarity: {sim:.0%})"

            results.append(
                RecommendationItem(
                    movie_id=movie_id,
                    title=self._get_movie_title(movie_id),
                    genres=movie_genres,
                    score=round(sim, 3),
                    reason=reason,
                )
            )

        return results
