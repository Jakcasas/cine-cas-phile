"""Evaluation metrics for rating prediction and top-K ranking."""

from typing import Dict, List, Set, Tuple
import numpy as np


def compute_rmse(actuals: np.ndarray, preds: np.ndarray) -> float:
    """Root Mean Squared Error."""
    return float(np.sqrt(np.mean((actuals - preds) ** 2)))


def compute_mae(actuals: np.ndarray, preds: np.ndarray) -> float:
    """Mean Absolute Error."""
    return float(np.mean(np.abs(actuals - preds)))


def compute_precision_at_k(recommended_ids: List[int], relevant_ids: Set[int], k: int) -> float:
    """Precision@K: proportion of recommended items in top-K that are relevant."""
    if k <= 0:
        return 0.0
    rec_k = set(recommended_ids[:k])
    return len(rec_k.intersection(relevant_ids)) / float(k)


def compute_recall_at_k(recommended_ids: List[int], relevant_ids: Set[int], k: int) -> float:
    """Recall@K: proportion of relevant items captured in top-K."""
    if not relevant_ids:
        return 0.0
    rec_k = set(recommended_ids[:k])
    return len(rec_k.intersection(relevant_ids)) / float(len(relevant_ids))


def compute_hit_rate_at_k(recommended_ids: List[int], relevant_ids: Set[int], k: int) -> float:
    """HitRate@K: 1 if at least one relevant item is in top-K, else 0."""
    rec_k = set(recommended_ids[:k])
    return 1.0 if len(rec_k.intersection(relevant_ids)) > 0 else 0.0


def compute_ndcg_at_k(recommended_ids: List[int], relevant_ids: Set[int], k: int) -> float:
    """Normalized Discounted Cumulative Gain at rank K."""
    if not relevant_ids or k <= 0:
        return 0.0

    dcg = 0.0
    for rank, item_id in enumerate(recommended_ids[:k], start=1):
        if item_id in relevant_ids:
            dcg += 1.0 / np.log2(rank + 1)

    n_rel = min(k, len(relevant_ids))
    idcg = sum(1.0 / np.log2(rank + 1) for rank in range(1, n_rel + 1))

    if idcg <= 0.0:
        return 0.0
    return dcg / idcg


def compute_catalog_coverage(all_recommended_ids: Set[int], total_catalog_ids: Set[int]) -> float:
    """Catalog Coverage: fraction of unique items ever recommended."""
    if not total_catalog_ids:
        return 0.0
    return len(all_recommended_ids.intersection(total_catalog_ids)) / float(len(total_catalog_ids))
