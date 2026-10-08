"""Base class and common data models for recommender models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import pandas as pd
import numpy as np


@dataclass
class RecommendationItem:
    movie_id: int
    title: str
    genres: str
    score: float
    reason: str


class BaseRecommender(ABC):
    """Abstract base class for all recommender implementations."""

    def __init__(self, name: str):
        self.name = name
        self.is_fitted = False
        self.movies_df: Optional[pd.DataFrame] = None
        self.movie_meta: Dict[int, Dict[str, str]] = {}
        self.all_movie_ids: Set[int] = set()

    def set_movie_meta(self, movies_df: pd.DataFrame):
        """Cache movie metadata for rapid lookup and explainability."""
        self.movies_df = movies_df
        self.all_movie_ids = set(movies_df["movie_id"].unique())
        self.movie_meta = {
            row["movie_id"]: {
                "title": row["title"],
                "genres": row["genres"],
                "year": str(row["year"]) if pd.notnull(row["year"]) else "",
            }
            for _, row in movies_df.iterrows()
        }

    @abstractmethod
    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        """Fit model using training interactions and movie metadata."""
        pass

    @abstractmethod
    def predict(self, user_id: int, movie_id: int) -> float:
        """Predict rating score for a single (user, movie) pair."""
        pass

    @abstractmethod
    def recommend(
        self,
        user_id: int,
        k: int = 10,
        candidate_movie_ids: Optional[List[int]] = None,
    ) -> List[RecommendationItem]:
        """Generate top-K recommended movies for a user."""
        pass

    def _get_movie_title(self, movie_id: int) -> str:
        return self.movie_meta.get(movie_id, {}).get("title", f"Movie #{movie_id}")

    def _get_movie_genres(self, movie_id: int) -> str:
        return self.movie_meta.get(movie_id, {}).get("genres", "Unknown")
