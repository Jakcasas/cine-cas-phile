"""Unit tests for recommendation metrics."""

import numpy as np
import pytest
from src.evaluation.metrics import (
    compute_rmse,
    compute_mae,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_hit_rate_at_k,
    compute_ndcg_at_k,
    compute_catalog_coverage,
)


def test_rmse_and_mae():
    actuals = np.array([4.0, 5.0, 3.0, 2.0])
    preds = np.array([4.0, 4.0, 3.0, 1.0])

    rmse = compute_rmse(actuals, preds)
    mae = compute_mae(actuals, preds)

    assert pytest.approx(rmse, 0.01) == np.sqrt(2.0 / 4.0)
    assert pytest.approx(mae, 0.01) == 0.5


def test_ranking_metrics_perfect_match():
    recommended = [10, 20, 30, 40, 50]
    relevant = {10, 20}

    prec = compute_precision_at_k(recommended, relevant, k=5)
    rec = compute_recall_at_k(recommended, relevant, k=5)
    hit = compute_hit_rate_at_k(recommended, relevant, k=5)
    ndcg = compute_ndcg_at_k(recommended, relevant, k=5)

    assert prec == 2.0 / 5.0
    assert rec == 1.0
    assert hit == 1.0
    assert ndcg == 1.0  # Top 2 positions are relevant


def test_ranking_metrics_no_match():
    recommended = [10, 20, 30]
    relevant = {99, 100}

    prec = compute_precision_at_k(recommended, relevant, k=3)
    rec = compute_recall_at_k(recommended, relevant, k=3)
    hit = compute_hit_rate_at_k(recommended, relevant, k=3)
    ndcg = compute_ndcg_at_k(recommended, relevant, k=3)

    assert prec == 0.0
    assert rec == 0.0
    assert hit == 0.0
    assert ndcg == 0.0


def test_catalog_coverage():
    all_recs = {1, 2, 3, 4}
    catalog = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}

    cov = compute_catalog_coverage(all_recs, catalog)
    assert cov == 0.4
