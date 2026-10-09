# Cine Cas Phile — measured benchmark

Seed 42; 200 ranking users; 10000 test rating pairs.

Full catalog candidates exclude train and validation items. Relevance ≥4; K=10; MMR=0.

| Model | RMSE | MAE | Precision@10 | Recall@10 | NDCG@10 | Hit@10 | Coverage | ILD | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | — | — | 0.0165 | 0.025587 | 0.025584 | 0.125 | 0.127326 | 0.26139 | 5.131 |
| collaborative | 0.969718 | 0.744412 | 0.001 | 0.001714 | 0.001018 | 0.01 | 0.156709 | 0.70145 | 3.805 |
| svd | 0.936547 | 0.731557 | 0.0345 | 0.048841 | 0.048665 | 0.23 | 0.032811 | 0.814638 | 3.899 |
| content | — | — | 0.0055 | 0.008104 | 0.006069 | 0.05 | 0.107003 | 0.082533 | 4.646 |
| popularity | 1.001988 | 0.796843 | 0.019 | 0.029283 | 0.026677 | 0.15 | 0.011019 | 0.860999 | 3.97 |

Only calibrated rating outputs are measured for RMSE/MAE. All five modes are measured for ranking.

Per-user temporal holdout is not a global-time split. Metadata uses the full known catalog. Coverage depends on sample size; latency depends on hardware. No claim that the hybrid beats every baseline.

Validation is reserved and excluded from test candidates; no hyperparameter search was performed.