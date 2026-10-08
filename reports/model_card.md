# Cine Cas Phile 3.0 — Model card

Local educational movie discovery system built on supplied MovieLens 1M files. One train-only NumPy/SciPy engine serves Bayesian popularity, genre TF-IDF, item-based CF, residual truncated SVD and a weighted hybrid. MMR diversification is optional at inference. This is not the former FunkSVD / NeuMF service.

The artifact contains only arrays, loaded without pickle. A SHA-256 fingerprint covers movies, ratings and engine format. Full catalog metadata is assumed available; only train ratings enter priors, features derived from interactions, neighbor similarity and factors. Validation is reserved; no hyperparameter search was performed.

Temporal splitting keeps equal timestamps together per user, checks all boundary pairs and rejects duplicate user/movie interactions. This does not prove global chronological causality across users. MovieLens is historical and demographically selective; results do not establish performance on present-day audiences.

Measured report: `benchmark_report.md`, 200 ranking users, 10,000 test rating pairs, seed 42. SVD has the best NDCG@10 among the measured modes. Hybrid favors mixed taste and genre coverage but is not uniformly better. Content and hybrid are uncalibrated ranking scores and do not have reported rating RMSE.

Personal ratings are stored separately in SQLite and affect content/neighbor inference immediately. They do not update SVD factors online or enter offline benchmark data. Unknown profiles fall back to supplied genres/seeds or community priors. Score is not a probability.

Intended for local personal/research use, not an authenticated multi-user public service. Public source metadata and supplemental film titles are separate from historical MovieLens interactions. New films have genre content features, but no invented MovieLens ratings or trained collaborative history. External scores are display snapshots and do not enter the model. No streaming is provided. Dataset and artwork licensing are separate from source-code licensing; consult `docs/MOVIELENS_README.txt` and `docs/ENRICHMENT.md`.
