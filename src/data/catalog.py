"""Original MovieLens catalog plus explicit supplemental editorial entries."""
import pandas as pd
from src.data.loader import MovieLensLoader


def load_catalog(data_dir):
    movies = MovieLensLoader(raw_movies_path=str(data_dir / "movies.csv")).load_movies()
    extra = data_dir / "catalog_extra.csv"
    if extra.exists():
        supplemental = MovieLensLoader(raw_movies_path=str(extra)).load_movies()
        if (supplemental.movie_id < 1_000_000).any() or set(supplemental.movie_id) & set(movies.movie_id):
            raise ValueError("Supplemental catalog must use unique IDs above 1,000,000")
        movies = pd.concat([movies, supplemental], ignore_index=True).sort_values("movie_id").reset_index(drop=True)
    return movies
