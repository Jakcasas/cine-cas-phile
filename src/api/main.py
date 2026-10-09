"""Cine (cas) phile. API and same-origin web interface."""
from contextlib import asynccontextmanager
from typing import Literal
import time
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from src import settings
from src.api.service import RecommendationService
from src.api.profiles import ProfileStore
from src.recommenders.engine import MODELS, fingerprint
from src.api.vision import VisualSearch

service = RecommendationService.get_instance()
store = ProfileStore(settings.DATABASE)


@asynccontextmanager
async def lifespan(app):
    service.initialize()
    store.initialize()
    app.state.visual = VisualSearch(settings.ROOT / "artifacts" / "vision", fingerprint(settings.DATA_DIR))
    yield


app = FastAPI(title="Cine (cas) phile.", version=settings.VERSION,
              description="MovieLens discovery, explainable recommendations and local profiles.", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=settings.ROOT / "web"), name="static")


class DiscoverRequest(BaseModel):
    profile_id: str | None = Field(default=None, max_length=64)
    user_id: int | None = Field(default=None, ge=1)
    model: Literal["hybrid", "collaborative", "svd", "content", "popularity"] = "hybrid"
    preferred_genres: list[str] = Field(default_factory=list, max_length=18)
    seed_ids: list[int] = Field(default_factory=list, max_length=20)
    k: int = Field(default=12, ge=1, le=50)
    diversity: float = Field(default=.2, ge=0, le=1)
    genre: str | None = None
    year_min: int | None = Field(default=None, ge=1800, le=2100)
    year_max: int | None = Field(default=None, ge=1800, le=2100)


class RatingRequest(BaseModel):
    rating: float = Field(ge=1, le=5, allow_inf_nan=False)


class PreferencesRequest(BaseModel):
    genres: list[str] = Field(default_factory=list, max_length=18)


def profile_or_404(profile_id):
    profile = store.get(profile_id)
    if profile is None:
        raise HTTPException(404, "Profile not found")
    return profile


def movie_or_404(movie_id):
    if movie_id not in service.engine.movie_index:
        raise HTTPException(404, "Movie not found")
    return service.enrich(service.engine.movie(movie_id))


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(settings.ROOT / "web" / "index.html")


@app.get("/health")
def health():
    return service.health()


@app.get("/models")
def models():
    return [{"name": key, "description": value, "best_for": "Khám phá phim"} for key, value in MODELS.items()]


@app.get("/stats")
def stats():
    engine = service.engine
    return {**service.health(), "genres": engine.genres, "train_ratings": int(engine.history.nnz),
            "split": engine.manifest, "dataset": "MovieLens 1M", "score_description": "Điểm xếp hạng 0–1, không phải xác suất",
            "year_min": int(engine.movies.year.min()), "year_max": int(engine.movies.year.max()),
            "poster_movies": sum(bool(m['poster_sources']) for m in service.enrichment.movies.values()) if hasattr(service, "enrichment") else 0}


@app.get("/benchmark")
def benchmark_report():
    import json
    report = settings.ROOT / "reports" / "benchmark.json"
    if not report.exists():
        raise HTTPException(404, "Run python -m src.cli benchmark")
    data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("dataset_fingerprint") != fingerprint(settings.DATA_DIR):
        raise HTTPException(409, "Benchmark belongs to a different dataset; rerun benchmark")
    return data


@app.get("/movies")
def catalog(q: str = Query(default="", max_length=200), genre: str | None = None,
            year_min: int | None = None, year_max: int | None = None,
            sort: Literal["popular", "rating", "year", "title", "relevance"] = "relevance",
            page: int = Query(default=1, ge=1), page_size: int = Query(default=24, ge=1, le=60),
            source: Literal["MUBI", "Letterboxd", "editorial"] | None = None):
    try:
        return service.catalog(q, genre, year_min, year_max, sort, page, page_size, source)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/movies/{movie_id}")
def movie_detail(movie_id: int):
    return {**movie_or_404(movie_id), "similar_movies": [service.enrich(m) for m in service.engine.similar(movie_id)]}


@app.get("/visual-search/status")
def visual_status():
    visual=app.state.visual
    return {"ready":visual.ready,"indexed_movies":visual.count,"scene_images":visual.stills_count,
            "method":"CLIP ViT-B/32 INT8 · cosine similarity", "upload_scope":"local computer only"}


@app.post("/visual-search")
async def visual_search(image: UploadFile = File(...), k: int = Query(default=12,ge=1,le=30)):
    from starlette.concurrency import run_in_threadpool
    try:
        data=await image.read(8*1024*1024+1)
        matches=await run_in_threadpool(app.state.visual.search,data,k)
        return {"matches":[{**movie_or_404(m["movie_id"]),**m} for m in matches if m["movie_id"] in service.engine.movie_index],
                "notice":"Ứng viên có hình ảnh gần giống trong kho tham chiếu; không phải xác suất nhận diện. Ảnh được xử lý trên máy và không lưu lại."}
    except ValueError as error:
        raise HTTPException(422,str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503,str(error)) from error
    finally:
        await image.close()


@app.post("/discover")
def discover(request: DiscoverRequest):
    started = time.perf_counter()
    profile = profile_or_404(request.profile_id) if request.profile_id else None
    ratings = profile["ratings"] if profile else {}
    genres = request.preferred_genres or (profile["genres"] if profile else [])
    try:
        items = service.engine.recommend(user_id=request.user_id, ratings=ratings, preferred_genres=genres,
                   seed_ids=request.seed_ids, model=request.model, k=request.k, diversity=request.diversity,
                   genre=request.genre, year_min=request.year_min, year_max=request.year_max)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    known = request.user_id in service.engine.user_index
    has_history = known or bool(ratings)
    has_content = bool(genres or request.seed_ids) or any(value > 3 for value in ratings.values()) or (known and bool(service.engine.profiles[service.engine.user_index[request.user_id]].any()))
    fallback = (request.model == "svd" and not known) or (request.model == "collaborative" and not has_history) or (request.model == "content" and not has_content) or (request.model == "hybrid" and not has_history and not has_content)
    fallback_reason = "SVD cần ID MovieLens có lịch sử train. Hiện đang dùng điểm cộng đồng; chọn Hybrid để dùng gu cá nhân." if request.model == "svd" and fallback else None
    return {"user_id": request.user_id, "model": request.model, "is_fallback": fallback,
            "count": len(items), "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "score_type": "relative_rank_0_1", "fallback_reason": fallback_reason, "recommendations": [service.enrich(m) for m in items]}


@app.get("/recommendations/{user_id}")
def legacy_recommend(user_id: int, k: int = Query(default=10, ge=1, le=50),
                     model: Literal["hybrid", "collaborative", "svd", "content", "popularity"] = "hybrid"):
    return discover(DiscoverRequest(user_id=user_id, k=k, model=model, diversity=0))


class ColdStartRequest(BaseModel):
    preferred_genres: list[str] = Field(default_factory=list, max_length=18)
    k: int = Field(default=10, ge=1, le=50)


@app.post("/recommendations/cold-start")
def cold_start(request: ColdStartRequest):
    return discover(DiscoverRequest(preferred_genres=request.preferred_genres, k=request.k))["recommendations"]


@app.post("/profiles", status_code=201)
def create_profile():
    return store.create()


@app.get("/profiles/{profile_id}")
def get_profile(profile_id: str):
    profile = profile_or_404(profile_id)
    profile["watchlist_movies"] = [service.enrich(service.engine.movie(mid)) for mid in profile["watchlist"] if mid in service.engine.movie_index]
    profile["rated_movies"] = [{**service.enrich(service.engine.movie(int(mid))), "my_rating": rating}
                               for mid, rating in profile["ratings"].items() if int(mid) in service.engine.movie_index]
    return profile


@app.put("/profiles/{profile_id}/preferences")
def save_preferences(profile_id: str, request: PreferencesRequest):
    profile_or_404(profile_id)
    if any(genre.lower() not in service.engine.genre_index for genre in request.genres):
        raise HTTPException(422, "Unknown genre")
    store.preferences(profile_id, list(dict.fromkeys(request.genres)))
    return get_profile(profile_id)


@app.put("/profiles/{profile_id}/ratings/{movie_id}")
def rate(profile_id: str, movie_id: int, request: RatingRequest):
    profile_or_404(profile_id)
    movie_or_404(movie_id)
    store.rate(profile_id, movie_id, request.rating)
    return {"movie_id": movie_id, "rating": request.rating}


@app.delete("/profiles/{profile_id}/ratings/{movie_id}")
def unrate(profile_id: str, movie_id: int):
    profile_or_404(profile_id)
    store.unrate(profile_id, movie_id)
    return {"removed": movie_id}


@app.put("/profiles/{profile_id}/watchlist/{movie_id}")
def save_movie(profile_id: str, movie_id: int):
    profile_or_404(profile_id)
    movie_or_404(movie_id)
    store.watchlist(profile_id, movie_id, True)
    return {"saved": movie_id}


@app.delete("/profiles/{profile_id}/watchlist/{movie_id}")
def unsave_movie(profile_id: str, movie_id: int):
    profile_or_404(profile_id)
    store.watchlist(profile_id, movie_id, False)
    return {"removed": movie_id}
