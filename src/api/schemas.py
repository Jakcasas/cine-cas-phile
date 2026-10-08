"""FastAPI Pydantic data schemas for requests and responses."""

from typing import List, Optional
from pydantic import BaseModel, Field


class RecommendationResponseItem(BaseModel):
    movie_id: int = Field(..., description="Unique MovieLens Movie ID")
    title: str = Field(..., description="Movie title and release year")
    genres: str = Field(..., description="Pipe-separated movie genres")
    score: float = Field(..., description="Predicted score or similarity")
    reason: str = Field(..., description="Human-interpretable recommendation explanation")


class RecommendationsResponse(BaseModel):
    user_id: int = Field(..., description="Target user ID")
    model: str = Field(..., description="Algorithm used to generate recommendations")
    is_fallback: bool = Field(..., description="Whether a cold-start fallback was triggered")
    count: int = Field(..., description="Number of returned movies")
    latency_ms: float = Field(..., description="Inference latency in milliseconds")
    recommendations: List[RecommendationResponseItem]


class ColdStartRequest(BaseModel):
    preferred_genres: List[str] = Field(..., description="List of genres preferred by user (e.g. ['Action', 'Sci-Fi'])")
    k: int = Field(default=10, ge=1, le=50, description="Number of recommendations requested")


class MovieDetailResponse(BaseModel):
    movie_id: int
    title: str
    genres: str
    year: Optional[str] = None
    similar_movies: List[RecommendationResponseItem] = []


class ModelInfo(BaseModel):
    name: str
    description: str
    best_for: str


class HealthResponse(BaseModel):
    status: str
    version: str
    loaded_models: List[str]
    catalog_size: int
    users_count: int
    uptime_seconds: float
