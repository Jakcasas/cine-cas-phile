"""Evaluation metrics and benchmark runner."""

from src.evaluation.metrics import (
    compute_rmse,
    compute_mae,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_ndcg_at_k,
    compute_hit_rate_at_k,
    compute_catalog_coverage,
)
from src.evaluation.benchmark import RecSysBenchmark

__all__ = [
    "compute_rmse",
    "compute_mae",
    "compute_precision_at_k",
    "compute_recall_at_k",
    "compute_ndcg_at_k",
    "compute_hit_rate_at_k",
    "compute_catalog_coverage",
    "RecSysBenchmark",
]
