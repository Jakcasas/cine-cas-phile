# Cine Cas Phile — measured benchmark

Seed 42; 200 ranking users; 10000 test rating pairs.

Full catalog candidates exclude train and validation items. Relevance ≥4; K=10; MMR=0.

| Model | RMSE | MAE | Precision@10 | Recall@10 | NDCG@10 | Hit@10 | Coverage | ILD | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | — | — | 0.0165 | 0.025587 | 0.025584 | 0.125 | 0.132567 | 0.261642 | 10.839 |
| collaborative | 0.969718 | 0.744412 | 0.001 | 0.001714 | 0.001018 | 0.01 | 0.163474 | 0.701347 | 11.159 |
| svd | 0.936547 | 0.731557 | 0.0345 | 0.048841 | 0.048665 | 0.23 | 0.034227 | 0.814884 | 13.013 |
| content | — | — | 0.006 | 0.009771 | 0.00681 | 0.055 | 0.109579 | 0.08272 | 13.009 |
| popularity | 1.001988 | 0.796843 | 0.019 | 0.029283 | 0.026677 | 0.15 | 0.011494 | 0.861187 | 11.666 |

Only calibrated rating outputs are measured for RMSE/MAE. All five modes are measured for ranking.

Per-user temporal holdout is not a global-time split. Metadata uses the full known catalog. Coverage depends on sample size; latency depends on hardware. No claim that the hybrid beats every baseline.

Validation is reserved and excluded from test candidates; no hyperparameter search was performed.