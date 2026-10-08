"""Data loading, cleaning, validation and mapping module for MovieLens 1M."""

import os
import re
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd


def read_table(path, columns):
    """Read MovieLens CSV/TSV or headerless :: DAT without dropping row one."""
    try:
        with open(path, encoding="utf-8") as handle:
            handle.read()
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        encoding = "latin-1"
    with open(path, encoding=encoding) as handle:
        first = handle.readline()
    sep = "\t" if "\t" in first else "::" if "::" in first else ","
    headerless = sep == "::" and first.split("::", 1)[0].strip().isdigit()
    frame = pd.read_csv(path, sep=sep, encoding=encoding, engine="python" if sep == "::" else "c",
                        header=None if headerless else 0, names=columns if headerless else None)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    frame = frame.drop(columns=[c for c in frame if c.startswith("unnamed") or c == "index" or "emb_id" in c])
    frame = frame.rename(columns={"movieid": "movie_id", "userid": "user_id", "zip": "zipcode"})
    missing = set(columns) - set(frame)
    if missing:
        raise ValueError(f"Missing columns in {path}: {sorted(missing)}")
    return frame


@dataclass
class DatasetStats:
    n_ratings: int
    n_users: int
    n_movies: int
    density_percent: float
    sparsity_percent: float
    min_rating: float
    max_rating: float
    mean_rating: float
    std_rating: float
    min_ratings_per_user: int
    max_ratings_per_user: int
    median_ratings_per_user: float
    min_ratings_per_movie: int
    max_ratings_per_movie: int
    median_ratings_per_movie: float
    earliest_timestamp: str
    latest_timestamp: str
    unique_genres_count: int


class MovieLensLoader:
    """Robust data loader and validator for MovieLens datasets."""

    def __init__(
        self,
        raw_movies_path: str = "data/raw/movies.csv",
        raw_ratings_path: str = "data/raw/ratings.csv",
        raw_users_path: str = "data/raw/users.csv",
    ):
        self.raw_movies_path = raw_movies_path
        self.raw_ratings_path = raw_ratings_path
        self.raw_users_path = raw_users_path

        self.movies_df: Optional[pd.DataFrame] = None
        self.ratings_df: Optional[pd.DataFrame] = None
        self.users_df: Optional[pd.DataFrame] = None

        self.user2idx: Dict[int, int] = {}
        self.idx2user: Dict[int, int] = {}
        self.movie2idx: Dict[int, int] = {}
        self.idx2movie: Dict[int, int] = {}

    def load_movies(self) -> pd.DataFrame:
        """Load, validate, and clean movies data."""
        if not os.path.exists(self.raw_movies_path):
            raise FileNotFoundError(f"Movies file not found: {self.raw_movies_path}")

        df = read_table(self.raw_movies_path, ["movie_id", "title", "genres"])

        # Drop index column if present
        cols_to_drop = [c for c in df.columns if "Unnamed" in c or c.lower() == "index"]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)

        # Standardize columns
        df.columns = [c.strip().lower() for c in df.columns]
        expected_cols = {"movie_id", "title", "genres"}
        if not expected_cols.issubset(set(df.columns)):
            # If dat format without header
            if len(df.columns) >= 3:
                df.columns = ["movie_id", "title", "genres"] + list(df.columns[3:])

        df["movie_id"] = df["movie_id"].astype(int)
        df["title"] = df["title"].astype(str).str.strip()
        df["genres"] = df["genres"].astype(str).str.strip()

        # Extract year
        def extract_year(title: str) -> Optional[int]:
            match = re.search(r"\((\d{4})\)", title)
            return int(match.group(1)) if match else None

        df["year"] = df["title"].apply(extract_year)
        df["title_clean"] = df["title"].str.replace(r"\s*\(\d{4}\)", "", regex=True).str.strip()

        # Parse genres as list
        df["genres_list"] = df["genres"].apply(
            lambda x: [g.strip() for g in x.split("|") if g.strip()] if x else []
        )

        # Remove duplicates if any
        df = df.drop_duplicates(subset=["movie_id"]).reset_index(drop=True)
        self.movies_df = df
        return self.movies_df

    def load_users(self) -> pd.DataFrame:
        """Load, validate, and clean users data."""
        if not os.path.exists(self.raw_users_path):
            raise FileNotFoundError(f"Users file not found: {self.raw_users_path}")

        df = read_table(self.raw_users_path, ["user_id", "gender", "age", "occupation", "zipcode"])

        cols_to_drop = [c for c in df.columns if "Unnamed" in c or c.lower() == "index"]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)

        df.columns = [c.strip().lower() for c in df.columns]
        df["user_id"] = df["user_id"].astype(int)
        df = df.drop_duplicates(subset=["user_id"]).reset_index(drop=True)
        self.users_df = df
        return self.users_df

    def load_ratings(self) -> pd.DataFrame:
        """Load, validate, and clean ratings data."""
        if not os.path.exists(self.raw_ratings_path):
            raise FileNotFoundError(f"Ratings file not found: {self.raw_ratings_path}")

        df = read_table(self.raw_ratings_path, ["user_id", "movie_id", "rating", "timestamp"])

        cols_to_drop = [c for c in df.columns if "Unnamed" in c or "emb_id" in c]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)

        df.columns = [c.strip().lower() for c in df.columns]
        df = df[["user_id", "movie_id", "rating", "timestamp"]]

        df["user_id"] = df["user_id"].astype(int)
        df["movie_id"] = df["movie_id"].astype(int)
        df["rating"] = df["rating"].astype(float)
        df["timestamp"] = df["timestamp"].astype(int)

        # Validate rating range
        valid_mask = (df["rating"] >= 1.0) & (df["rating"] <= 5.0)
        df = df[valid_mask]

        # Deduplicate: keep latest rating if user rated same movie multiple times
        df = df.sort_values(["user_id", "timestamp"]).drop_duplicates(
            subset=["user_id", "movie_id"], keep="last"
        ).reset_index(drop=True)

        self.ratings_df = df
        return self.ratings_df

    def build_mappings(self) -> Tuple[Dict[int, int], Dict[int, int]]:
        """Build contiguous 0-based indices for users and items."""
        if self.ratings_df is None:
            self.load_ratings()

        unique_users = sorted(self.ratings_df["user_id"].unique())
        self.user2idx = {u: idx for idx, u in enumerate(unique_users)}
        self.idx2user = {idx: u for idx, u in enumerate(unique_users)}

        unique_movies = sorted(self.ratings_df["movie_id"].unique())
        self.movie2idx = {m: idx for idx, m in enumerate(unique_movies)}
        self.idx2movie = {idx: m for idx, m in enumerate(unique_movies)}

        # Add index columns
        self.ratings_df["user_idx"] = self.ratings_df["user_id"].map(self.user2idx)
        self.ratings_df["movie_idx"] = self.ratings_df["movie_id"].map(self.movie2idx)

        return self.user2idx, self.movie2idx

    def get_stats(self) -> DatasetStats:
        """Calculate comprehensive data quality statistics."""
        if self.ratings_df is None:
            self.load_ratings()
        if self.movies_df is None:
            self.load_movies()

        n_ratings = len(self.ratings_df)
        n_users = self.ratings_df["user_id"].nunique()
        n_movies = self.ratings_df["movie_id"].nunique()

        total_possible = n_users * n_movies
        density = (n_ratings / total_possible) * 100.0
        sparsity = 100.0 - density

        ratings_per_user = self.ratings_df.groupby("user_id").size()
        ratings_per_movie = self.ratings_df.groupby("movie_id").size()

        all_genres = set()
        for g_list in self.movies_df["genres_list"]:
            all_genres.update(g_list)

        earliest = pd.to_datetime(self.ratings_df["timestamp"].min(), unit="s").isoformat()
        latest = pd.to_datetime(self.ratings_df["timestamp"].max(), unit="s").isoformat()

        stats = DatasetStats(
            n_ratings=n_ratings,
            n_users=n_users,
            n_movies=n_movies,
            density_percent=round(density, 4),
            sparsity_percent=round(sparsity, 4),
            min_rating=float(self.ratings_df["rating"].min()),
            max_rating=float(self.ratings_df["rating"].max()),
            mean_rating=round(float(self.ratings_df["rating"].mean()), 4),
            std_rating=round(float(self.ratings_df["rating"].std()), 4),
            min_ratings_per_user=int(ratings_per_user.min()),
            max_ratings_per_user=int(ratings_per_user.max()),
            median_ratings_per_user=float(ratings_per_user.median()),
            min_ratings_per_movie=int(ratings_per_movie.min()),
            max_ratings_per_movie=int(ratings_per_movie.max()),
            median_ratings_per_movie=float(ratings_per_movie.median()),
            earliest_timestamp=earliest,
            latest_timestamp=latest,
            unique_genres_count=len(all_genres),
        )
        return stats
