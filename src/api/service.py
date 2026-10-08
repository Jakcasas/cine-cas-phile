"""Artifact loading and catalog queries; no training during API startup."""
import time
import unicodedata
import numpy as np
from src import settings
from src.data.loader import MovieLensLoader
from src.recommenders.engine import RecommendationEngine, fingerprint
from src.api.enrichment import MovieEnrichment
from src.data.catalog import load_catalog


def search_key(value):
    """Normalize accents for Vietnamese and international movie titles."""
    text = unicodedata.normalize('NFD', str(value).casefold()).replace('đ', 'd')
    return ''.join(char for char in text if unicodedata.category(char) != 'Mn').strip()


class RecommendationService:
    _instance = None

    def __init__(self, data_dir=None, artifact=None):
        self.data_dir = data_dir or settings.DATA_DIR
        self.artifact = artifact or settings.ARTIFACT
        self.start_time = time.monotonic()
        self.is_ready = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self):
        if self.is_ready:
            return
        movies = load_catalog(self.data_dir)
        if not self.artifact.exists():
            raise RuntimeError("Chưa có mô hình. Chạy: python -m src.cli train")
        self.engine = RecommendationEngine(movies).load(self.artifact, fingerprint(self.data_dir))
        self.enrichment = MovieEnrichment(settings.ROOT / "data" / "enrichment" / "movie_images.json")
        self.is_ready = True

    def enrich(self, movie):
        enrichment = getattr(self, "enrichment", None)
        return enrichment.enrich(movie) if enrichment else movie

    def catalog(self, q="", genre=None, year_min=None, year_max=None, sort="popular", page=1, page_size=24, source=None):
        if year_min is not None and year_max is not None and year_min > year_max:
            raise ValueError("year_min must not exceed year_max")
        frame = self.engine.movies
        mask = np.ones(len(frame), dtype=bool)
        if source:
            names = {"MUBI", "Letterboxd"} if source == "editorial" else {source}
            mask &= np.array([bool(names & set(self.enrichment.movies.get(int(mid), {}).get("catalog_sources", [])))
                              for mid in self.engine.movie_ids])
        if q:
            query = search_key(q)
            title_mask = np.array([query in search_key(title) for title in frame.title])
            enrichment = getattr(self, "enrichment", None)
            if enrichment:
                title_mask = title_mask | np.array([query in search_key(enrichment.movies.get(int(mid), {}).get("title_vi", ""))
                                                   for mid in self.engine.movie_ids])
            mask &= title_mask
        if genre:
            if genre.lower() not in self.engine.genre_index:
                raise ValueError("Unknown genre")
            mask &= self.engine.features[:, self.engine.genre_index[genre.lower()]] > 0
        if year_min is not None:
            mask &= frame.year.to_numpy(dtype=float) >= year_min
        if year_max is not None:
            mask &= frame.year.to_numpy(dtype=float) <= year_max
        indices = np.flatnonzero(mask)
        if sort == "popular":
            order = np.argsort(-self.engine.counts[indices], kind="stable")
        elif sort == "rating":
            order = np.argsort(-self.engine.popularity[indices], kind="stable")
        elif sort == "year":
            order = np.argsort(-np.nan_to_num(frame.year.to_numpy(dtype=float)[indices]), kind="stable")
        elif sort == "title":
            order = np.argsort(frame.title_clean.str.lower().to_numpy()[indices], kind="stable")
        else:
            raise ValueError("Unknown sort order")
        selected = indices[order][(page - 1) * page_size:page * page_size]
        return {"total": len(indices), "page": page, "page_size": page_size,
                "movies": [self.enrich(self.engine.movie(int(self.engine.movie_ids[i]))) for i in selected]}

    def health(self):
        from src.recommenders.engine import MODELS
        return {"status": "healthy" if self.is_ready else "initializing", "version": settings.VERSION,
                "loaded_models": list(MODELS) if self.is_ready else [],
                "catalog_size": len(self.engine.movie_ids) if self.is_ready else 0,
                "users_count": len(self.engine.user_ids) if self.is_ready else 0,
                "uptime_seconds": round(time.monotonic() - self.start_time, 2)}
