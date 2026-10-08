"""FastAPI REST API server for MovieLens Recommender System."""

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.api.schemas import (
    RecommendationsResponse,
    HealthResponse,
    ColdStartRequest,
    RecommendationResponseItem,
    MovieDetailResponse,
    ModelInfo,
)
from src.api.service import RecommendationService

from contextlib import asynccontextmanager

service = RecommendationService.get_instance()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    service.initialize()
    yield
    # Shutdown logic if any

app = FastAPI(
    title="Cine Cas Phile - Movie Recommendation Service",
    description="Cine Cas Phile: Production-grade, zero-leakage movie recommendation engine featuring Bayesian Popularity, TF-IDF Content-Based, SVD Biased MF, PyTorch NeuMF, Demographic Deep & Wide, and MMR Diversified Hybrid Ensembles.",
    version="2.5.0",
    lifespan=lifespan,
)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health_check():
    """Check API health, active models, catalog statistics, and uptime."""
    return service.health()


@app.get(
    "/recommendations/{user_id}",
    response_model=RecommendationsResponse,
    tags=["Recommendations"],
)
def get_recommendations(
    user_id: int,
    k: int = Query(default=10, ge=1, le=50, description="Number of recommendations"),
    model: str = Query(
        default="hybrid",
        description="Model architecture: 'popularity', 'content', 'svd', 'neural', or 'hybrid'",
    ),
):
    """Generate personalized top-K unviewed movie recommendations for a user.

    If the user has no history or is unseen, automatically engages cold-start fallback.
    """
    try:
        return service.recommend_for_user(user_id=user_id, k=k, model_name=model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/recommendations/cold-start",
    response_model=List[RecommendationResponseItem],
    tags=["Recommendations"],
)
def cold_start_recommendations(request: ColdStartRequest):
    """Generate recommendations for new users based on selected favorite genres."""
    try:
        return service.cold_start_by_genres(
            preferred_genres=request.preferred_genres, k=request.k
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/movies/{movie_id}", response_model=MovieDetailResponse, tags=["Catalog"])
def get_movie_detail(movie_id: int):
    """Fetch movie metadata and top similar movies."""
    detail = service.get_movie_detail(movie_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Movie ID {movie_id} not found.")
    return detail


@app.get("/models", response_model=List[ModelInfo], tags=["Catalog"])
def list_models():
    """List available recommendation models and descriptions."""
    return [
        ModelInfo(
            name="popularity",
            description="Bayesian shrinkage (IMDb damping) ranking community favorites.",
            best_for="Cold-start fallback & non-personalized discovery.",
        ),
        ModelInfo(
            name="content",
            description="TF-IDF vector space model on genres with user profile vectors.",
            best_for="Users with strong niche genre preferences.",
        ),
        ModelInfo(
            name="svd",
            description="Biased Matrix Factorization (FunkSVD) with global, user, and item bias.",
            best_for="Collaborative filtering with strong accuracy on known user behaviors.",
        ),
        ModelInfo(
            name="neural",
            description="PyTorch NeuMF (GMF + MLP) deep dual-tower embedding network.",
            best_for="Non-linear user-item interaction modeling.",
        ),
        ModelInfo(
            name="hybrid",
            description="Multi-signal ensemble fusing SVD, Content-Based, and Shrinkage Popularity.",
            best_for="Production default: optimal ranking, diversity, and coverage.",
        ),
    ]


@app.get("/", response_class=HTMLResponse, tags=["Demo"])
def interactive_ui():
    """Serve modern interactive web dashboard."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cine Cas Phile 2.5</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: #151d30;
            --card-border: #23314f;
            --accent: #6366f1;
            --accent-hover: #4f46e5;
            --accent-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --success: #10b981;
            --warning: #f59e0b;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        body { background: var(--bg-color); color: var(--text-main); min-height: 100vh; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--card-border); }
        .logo-group h1 { font-size: 1.8rem; font-weight: 800; background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .logo-group p { color: var(--text-muted); font-size: 0.9rem; margin-top: 0.3rem; }
        .status-badge { display: flex; align-items: center; gap: 0.5rem; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); color: var(--success); padding: 0.4rem 1rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; }
        .pulse { width: 8px; height: 8px; background: var(--success); border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        
        .controls-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 1rem; padding: 1.75rem; margin-bottom: 2rem; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); }
        .controls-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)) 160px; gap: 1.25rem; align-items: end; }
        .field label { display: block; font-size: 0.85rem; font-weight: 600; color: var(--text-muted); margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em; }
        .field input, .field select { width: 100%; background: #0b0f19; border: 1px solid var(--card-border); border-radius: 0.6rem; color: #fff; padding: 0.75rem 1rem; font-size: 0.95rem; outline: none; transition: border-color 0.2s; }
        .field input:focus, .field select:focus { border-color: var(--accent); }
        button.btn-primary { background: var(--accent-gradient); border: none; border-radius: 0.6rem; color: #fff; padding: 0.8rem 1.5rem; font-weight: 600; font-size: 0.95rem; cursor: pointer; transition: transform 0.15s, opacity 0.15s; width: 100%; height: 46px; }
        button.btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }
        button.btn-primary:active { transform: translateY(0); }

        .meta-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
        .meta-title { font-size: 1.25rem; font-weight: 700; }
        .meta-stats { display: flex; gap: 1rem; font-size: 0.85rem; color: var(--text-muted); }
        .meta-stats span { background: #151d30; padding: 0.3rem 0.8rem; border-radius: 0.5rem; border: 1px solid var(--card-border); }

        .results-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.25rem; }
        .movie-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 0.85rem; padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.2s, border-color 0.2s; position: relative; overflow: hidden; }
        .movie-card:hover { transform: translateY(-3px); border-color: var(--accent); }
        .movie-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem; }
        .movie-title { font-size: 1.05rem; font-weight: 700; color: #fff; line-height: 1.3; }
        .score-pill { background: rgba(99, 102, 241, 0.15); border: 1px solid var(--accent); color: #a5b4fc; font-size: 0.8rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 0.4rem; white-space: nowrap; margin-left: 0.5rem; }
        .genre-tags { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1rem; }
        .tag { background: #0b0f19; color: #94a3b8; font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 0.3rem; border: 1px solid #1e293b; }
        .reason-box { background: rgba(255, 255, 255, 0.03); border-left: 3px solid var(--accent); padding: 0.6rem 0.8rem; border-radius: 0 0.4rem 0.4rem 0; font-size: 0.8rem; color: #cbd5e1; }
        
        .loading { text-align: center; padding: 4rem; color: var(--text-muted); font-size: 1.1rem; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-group">
                <h1>🎬 Cine Cas Phile</h1>
                <p>Zero-Leakage Temporal Evaluation & Multi-Signal Inference Engine</p>
            </div>
            <div class="status-badge" id="system-status">
                <span class="pulse"></span>
                <span>System Online</span>
            </div>
        </header>

        <div class="controls-card">
            <div class="controls-grid">
                <div class="field">
                    <label>User ID</label>
                    <input type="number" id="userId" value="1" min="1" max="6040">
                </div>
                <div class="field">
                    <label>Model Architecture</label>
                    <select id="modelSelect">
                        <option value="hybrid" selected>Hybrid (Ensemble - Recommended)</option>
                        <option value="svd">Biased Matrix Factorization (SVD)</option>
                        <option value="neural">Neural CF (PyTorch NeuMF)</option>
                        <option value="content">Content-Based (TF-IDF)</option>
                        <option value="popularity">Popularity (Bayesian Shrinkage)</option>
                    </select>
                </div>
                <div class="field">
                    <label>Top-K Results</label>
                    <input type="number" id="topK" value="10" min="1" max="30">
                </div>
                <button class="btn-primary" onclick="loadRecommendations()">Recommend</button>
            </div>
        </div>

        <div class="meta-bar">
            <div class="meta-title" id="results-heading">Recommended Movies for User #1</div>
            <div class="meta-stats" id="meta-stats">
                <span id="stat-model">Model: Hybrid</span>
                <span id="stat-latency">Latency: -- ms</span>
                <span id="stat-count">Count: --</span>
            </div>
        </div>

        <div class="results-grid" id="resultsGrid">
            <div class="loading">Click "Recommend" to fetch personalized movies...</div>
        </div>
    </div>

    <script>
        async function loadRecommendations() {
            const userId = document.getElementById('userId').value;
            const model = document.getElementById('modelSelect').value;
            const k = document.getElementById('topK').value;
            const grid = document.getElementById('resultsGrid');

            grid.innerHTML = '<div class="loading">Computing recommendations...</div>';

            try {
                const res = await fetch(`/recommendations/${userId}?k=${k}&model=${model}`);
                const data = await res.json();

                document.getElementById('results-heading').innerText = `Recommended Movies for User #${data.user_id} ${data.is_fallback ? '(Cold-Start Fallback)' : ''}`;
                document.getElementById('stat-model').innerText = `Model: ${data.model}`;
                document.getElementById('stat-latency').innerText = `Latency: ${data.latency_ms} ms`;
                document.getElementById('stat-count').innerText = `Count: ${data.count} items`;

                if (!data.recommendations || data.recommendations.length === 0) {
                    grid.innerHTML = '<div class="loading">No recommendations returned.</div>';
                    return;
                }

                grid.innerHTML = data.recommendations.map(item => `
                    <div class="movie-card">
                        <div>
                            <div class="movie-header">
                                <div class="movie-title">${item.title}</div>
                                <div class="score-pill">Score: ${item.score}</div>
                            </div>
                            <div class="genre-tags">
                                ${item.genres.split('|').map(g => `<span class="tag">${g}</span>`).join('')}
                            </div>
                        </div>
                        <div class="reason-box">${item.reason}</div>
                    </div>
                `).join('');
            } catch (err) {
                grid.innerHTML = `<div class="loading" style="color: #ef4444;">Error fetching recommendations: ${err.message}</div>`;
            }
        }

        // Auto load on start
        window.addEventListener('DOMContentLoaded', loadRecommendations);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
