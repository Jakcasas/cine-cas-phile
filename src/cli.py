"""Train once, evaluate reproducibly, then serve cached arrays."""
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from src import settings
from src.data.loader import MovieLensLoader
from src.data.catalog import load_catalog
from src.data.splitter import TemporalSplitter
from src.recommenders.engine import RecommendationEngine, MODELS, fingerprint


def dataset():
    loader = MovieLensLoader(*(str(settings.DATA_DIR / name) for name in ("movies.csv", "ratings.csv", "users.csv")))
    movies = load_catalog(settings.DATA_DIR)
    loader.movies_df = movies
    ratings = loader.load_ratings()
    ratings = ratings[ratings.movie_id.isin(movies.movie_id)].reset_index(drop=True)
    loader.ratings_df = ratings
    return loader, movies, ratings


def train():
    loader, movies, ratings = dataset()
    training, validation, test, manifest = TemporalSplitter().split(ratings)
    print(f"Training: {len(training):,}; validation: {len(validation):,}; test: {len(test):,}", flush=True)
    engine = RecommendationEngine(movies).fit(training)
    engine.save(settings.ARTIFACT, fingerprint(settings.DATA_DIR), manifest)
    processed = settings.ROOT / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "split_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    stats = asdict(loader.get_stats())
    reports = settings.ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "data_quality.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"Saved {settings.ARTIFACT}; fitted in {engine.training_seconds:.2f}s", flush=True)
    return engine


def load_engine():
    from src.api.service import RecommendationService
    service = RecommendationService()
    service.initialize()
    return service.engine


def benchmark(users=100, rating_pairs=5000):
    from src.evaluation.metrics import (compute_precision_at_k, compute_recall_at_k,
                                       compute_ndcg_at_k, compute_hit_rate_at_k)
    _, movies, ratings = dataset()
    training, validation, test, manifest = TemporalSplitter().split(ratings)
    engine = load_engine()
    if engine.manifest != manifest:
        raise ValueError("Train artifact has a different evaluation split")
    positives = test[test.rating >= 4].groupby("user_id").movie_id.apply(set).to_dict()
    val_seen = validation.groupby("user_id").movie_id.apply(list).to_dict()
    rng = np.random.default_rng(42)
    selected = sorted(rng.choice(sorted(positives), size=min(users, len(positives)), replace=False).tolist())
    if not selected or test.empty:
        raise ValueError("No test users available for evaluation")
    rating_sample = test.sample(n=min(rating_pairs, len(test)), random_state=42)
    raw_signals = {}
    for user, group in rating_sample.groupby("user_id"):
        signals, _, _ = engine.signals(int(user))
        for name in ("popularity", "collaborative", "svd"):
            raw_signals.setdefault(name, []).extend((float(r.rating), float(signals[name][engine.movie_index[int(r.movie_id)]])) for r in group.itertuples())
    results = []
    for model in MODELS:
        collected = {key: [] for key in ("precision", "recall", "ndcg", "hit_rate", "ild", "latency")}
        recommended = set()
        for user in selected:
            started = time.perf_counter()
            items = engine.recommend(user_id=int(user), model=model, k=10, diversity=0, exclude_ids=val_seen.get(user, []))
            collected["latency"].append((time.perf_counter() - started) * 1000)
            mids = [item["movie_id"] for item in items]
            recommended.update(mids)
            relevant = positives[user]
            collected["precision"].append(compute_precision_at_k(mids, relevant, 10))
            collected["recall"].append(compute_recall_at_k(mids, relevant, 10))
            collected["ndcg"].append(compute_ndcg_at_k(mids, relevant, 10))
            collected["hit_rate"].append(compute_hit_rate_at_k(mids, relevant, 10))
            vectors = engine.features[[engine.movie_index[mid] for mid in mids]]
            similarity = vectors @ vectors.T
            collected["ild"].append(float((1 - similarity)[np.triu_indices(len(mids), 1)].mean()) if len(mids) > 1 else 0)
        rating_values = np.array(raw_signals[model]) if model in raw_signals else None
        result = {"model": model, **{key: round(float(np.mean(collected[key])), 6) for key in ("precision", "recall", "ndcg", "hit_rate", "ild")},
                  "rmse": round(float(np.sqrt(np.mean((rating_values[:, 0] - rating_values[:, 1]) ** 2))), 6) if rating_values is not None else None,
                  "mae": round(float(np.mean(np.abs(rating_values[:, 0] - rating_values[:, 1]))), 6) if rating_values is not None else None,
                  "coverage": round(len(recommended) / len(engine.movie_ids), 6),
                  "latency_p50_ms": round(float(np.percentile(collected["latency"], 50)), 3),
                  "latency_p95_ms": round(float(np.percentile(collected["latency"], 95)), 3)}
        results.append(result)
        print(json.dumps(result), flush=True)
    report = {"seed": 42, "ranking_users": len(selected), "rating_pairs": len(rating_sample),
              "dataset_fingerprint": fingerprint(settings.DATA_DIR), "split": manifest,
              "candidates": "Full catalog excluding train and validation; no sampled negatives",
              "relevance_threshold": 4, "k": 10, "diversity": 0,
              "rating_metrics": "Content and hybrid are ranking scores without rating calibration; RMSE/MAE omitted",
              "selection": "Uniform sample of users with at least one positive test rating",
              "results": results}
    report_dir = settings.ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "benchmark.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    lines = ["# Cine Cas Phile — measured benchmark", "", f"Seed 42; {len(selected)} ranking users; {len(rating_sample)} test rating pairs.", "",
             "Full catalog candidates exclude train and validation items. Relevance ≥4; K=10; MMR=0.", "",
             "| Model | RMSE | MAE | Precision@10 | Recall@10 | NDCG@10 | Hit@10 | Coverage | ILD | p95 ms |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in results:
        lines.append("| " + " | ".join(str(row[key]) if row[key] is not None else "—" for key in ("model", "rmse", "mae", "precision", "recall", "ndcg", "hit_rate", "coverage", "ild", "latency_p95_ms")) + " |")
    lines += ["", "Only calibrated rating outputs are measured for RMSE/MAE. All five modes are measured for ranking.", "",
              "Per-user temporal holdout is not a global-time split. Metadata uses the full known catalog. Coverage depends on sample size; latency depends on hardware. No claim that the hybrid beats every baseline.", "",
              "Validation is reserved and excluded from test candidates; no hyperparameter search was performed."]
    (report_dir / "benchmark_report.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cine-cas-phile")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("train", help="Fit train-only models and save safe NPZ arrays")
    evaluation = commands.add_parser("benchmark", help="Evaluate held-out test ratings")
    evaluation.add_argument("--users", type=int, default=100)
    evaluation.add_argument("--rating-pairs", type=int, default=5000)
    serving = commands.add_parser("serve", help="Serve the local web interface")
    serving.add_argument("--port", type=int, default=8000)
    serving.add_argument("--host", default="127.0.0.1")
    recommend = commands.add_parser("recommend", help="Generate recommendations as JSON")
    recommend.add_argument("--user", type=int)
    recommend.add_argument("--genres", default="")
    recommend.add_argument("--model", choices=list(MODELS), default="hybrid")
    recommend.add_argument("--k", type=int, default=10)
    args = parser.parse_args(argv)
    if args.command == "train":
        train()
    elif args.command == "benchmark":
        if args.users < 1 or args.rating_pairs < 1:
            parser.error("Sample sizes must be positive")
        benchmark(args.users, args.rating_pairs)
    elif args.command == "serve":
        import uvicorn
        uvicorn.run("src.api.main:app", host=args.host, port=args.port)
    else:
        items = load_engine().recommend(user_id=args.user, preferred_genres=[g.strip() for g in args.genres.split(',') if g.strip()], model=args.model, k=args.k)
        print(json.dumps(items, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
