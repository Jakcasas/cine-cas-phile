"""Benchmarking suite evaluating recommenders on identical test splits and candidates."""

import time
from typing import Dict, List, Optional, Set
import numpy as np
import pandas as pd
from tabulate import tabulate
from src.recommenders.base import BaseRecommender
from src.evaluation.metrics import (
    compute_rmse,
    compute_mae,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_ndcg_at_k,
    compute_hit_rate_at_k,
    compute_catalog_coverage,
)


class RecSysBenchmark:
    """Evaluates multiple recommenders under a strict zero-leakage protocol."""

    def __init__(
        self,
        relevance_threshold: float = 4.0,
        top_k: int = 10,
        sample_users: Optional[int] = 500,
        random_seed: int = 42,
    ):
        self.relevance_threshold = relevance_threshold
        self.top_k = top_k
        self.sample_users = sample_users
        self.random_seed = random_seed

    def evaluate_model(
        self,
        model: BaseRecommender,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        all_movie_ids: Set[int],
        user_train_items: Dict[int, Set[int]],
    ) -> Dict[str, float]:
        """Evaluates a single recommender on test split."""
        # 1. Rating Prediction (RMSE, MAE)
        actuals = test_df["rating"].values
        u_list = test_df["user_id"].values
        m_list = test_df["movie_id"].values

        preds = np.array([model.predict(u, m) for u, m in zip(u_list, m_list)])
        rmse = compute_rmse(actuals, preds)
        mae = compute_mae(actuals, preds)

        # 2. Ranking Evaluation on Test Positive Items (r >= threshold)
        test_pos = test_df[test_df["rating"] >= self.relevance_threshold]
        user_rel_items: Dict[int, Set[int]] = (
            test_pos.groupby("user_id")["movie_id"].apply(set).to_dict()
        )

        eval_users = list(user_rel_items.keys())
        if self.sample_users is not None and len(eval_users) > self.sample_users:
            rng = np.random.RandomState(self.random_seed)
            eval_users = list(rng.choice(eval_users, size=self.sample_users, replace=False))

        precisions = []
        recalls = []
        ndcgs = []
        hit_rates = []
        all_recs: Set[int] = set()
        latencies_ms = []

        for u in eval_users:
            rel_items = user_rel_items[u]
            seen_train = user_train_items.get(u, set())
            # Candidate items = all movies not seen in train
            candidates = list(all_movie_ids - seen_train)

            t0 = time.time()
            recs = model.recommend(u, k=self.top_k, candidate_movie_ids=candidates)
            latencies_ms.append((time.time() - t0) * 1000.0)

            rec_ids = [item.movie_id for item in recs]
            all_recs.update(rec_ids)

            prec = compute_precision_at_k(rec_ids, rel_items, self.top_k)
            rec = compute_recall_at_k(rec_ids, rel_items, self.top_k)
            ndcg = compute_ndcg_at_k(rec_ids, rel_items, self.top_k)
            hit = compute_hit_rate_at_k(rec_ids, rel_items, self.top_k)

            precisions.append(prec)
            recalls.append(rec)
            ndcgs.append(ndcg)
            hit_rates.append(hit)

        catalog_cov = compute_catalog_coverage(all_recs, all_movie_ids)

        return {
            "RMSE": round(rmse, 4),
            "MAE": round(mae, 4),
            f"Precision@{self.top_k}": round(float(np.mean(precisions)), 4),
            f"Recall@{self.top_k}": round(float(np.mean(recalls)), 4),
            f"NDCG@{self.top_k}": round(float(np.mean(ndcgs)), 4),
            f"HitRate@{self.top_k}": round(float(np.mean(hit_rates)), 4),
            "CatalogCoverage": round(catalog_cov * 100.0, 2),
            "Latency_p50_ms": round(float(np.percentile(latencies_ms, 50)), 2),
            "Latency_p95_ms": round(float(np.percentile(latencies_ms, 95)), 2),
        }

    def run_benchmark(
        self,
        models: List[BaseRecommender],
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        all_movie_ids: Set[int],
    ) -> pd.DataFrame:
        """Runs full comparison across multiple models and outputs tabular summary."""
        user_train_items = train_df.groupby("user_id")["movie_id"].apply(set).to_dict()

        records = []
        for model in models:
            metrics = self.evaluate_model(
                model=model,
                train_df=train_df,
                test_df=test_df,
                all_movie_ids=all_movie_ids,
                user_train_items=user_train_items,
            )
            record = {"Model": model.name, **metrics}
            records.append(record)

        df_results = pd.DataFrame(records)
        return df_results
