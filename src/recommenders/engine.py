"""Shared, vectorized ranking engine. Artifacts contain arrays, never pickled code."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, diags
from sklearn.utils.extmath import randomized_svd

MODELS = {
    "hybrid": "Kết hợp hành vi cộng đồng, nhân tố ẩn, thể loại và điểm Bayesian",
    "collaborative": "Item-based CF với cosine điều chỉnh và co-rating shrinkage",
    "svd": "Truncated SVD trên phần dư của điểm đánh giá, 32 nhân tố ẩn",
    "content": "Hồ sơ thể loại TF-IDF có trọng số đánh giá và thời gian",
    "popularity": "Điểm trung bình Bayesian với 25 đánh giá giả định",
}
FORMAT_VERSION = 3


def fingerprint(data_dir: Path) -> str:
    digest = hashlib.sha256()
    digest.update(f"cine-engine-{FORMAT_VERSION}".encode())
    names = ["movies.csv", "ratings.csv"]
    if (data_dir / "catalog_extra.csv").exists():
        names.append("catalog_extra.csv")
    for name in names:
        with (data_dir / name).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def normalize(values):
    values = np.asarray(values, dtype=np.float64)
    span = np.ptp(values)
    return (values - values.min()) / span if span > 1e-12 else np.full_like(values, .5)


class RecommendationEngine:
    def __init__(self, movies: pd.DataFrame):
        self.movies = movies.sort_values("movie_id").reset_index(drop=True)
        self.movie_ids = self.movies.movie_id.to_numpy(dtype=np.int64)
        self.movie_index = {int(mid): i for i, mid in enumerate(self.movie_ids)}
        self.genres = sorted({g for row in self.movies.genres_list for g in row})
        self.genre_index = {g.lower(): i for i, g in enumerate(self.genres)}
        features = np.zeros((len(self.movies), len(self.genres)), dtype=np.float32)
        for i, row in enumerate(self.movies.genres_list):
            for genre in row:
                features[i, self.genre_index[genre.lower()]] = 1
        idf = np.log((1 + len(features)) / (1 + features.sum(axis=0))) + 1
        features *= idf
        self.features = features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-8)
        self.ready = False

    def fit(self, train: pd.DataFrame, factors=32, neighbors=60):
        if train.empty:
            raise ValueError("Training ratings cannot be empty")
        if not train.movie_id.isin(self.movie_ids).all():
            raise ValueError("Ratings reference movies outside the catalog")
        started = time.perf_counter()
        self.user_ids = np.sort(train.user_id.unique()).astype(np.int64)
        self.user_index = {int(uid): i for i, uid in enumerate(self.user_ids)}
        rows = train.user_id.map(self.user_index).to_numpy()
        cols = train.movie_id.map(self.movie_index).to_numpy()
        values = train.rating.to_numpy(dtype=np.float32)
        self.history = csr_matrix((values, (rows, cols)), shape=(len(self.user_ids), len(self.movie_ids)))
        self.history.sort_indices()
        counts_user = np.asarray(self.history.getnnz(axis=1)).ravel()
        self.user_means = np.asarray(self.history.sum(axis=1)).ravel() / np.maximum(counts_user, 1)
        self.global_mean = float(values.mean())
        self.counts = np.bincount(cols, minlength=len(self.movie_ids)).astype(np.int64)
        sums = np.bincount(cols, weights=values, minlength=len(self.movie_ids))
        self.means = np.divide(sums, self.counts, out=np.full(len(sums), self.global_mean), where=self.counts > 0)
        self.popularity = ((sums + 25 * self.global_mean) / (self.counts + 25)).astype(np.float32)
        # Use each user's latest TRAIN timestamp, never wall-clock or held-out timestamps.
        latest = train.groupby("user_id").timestamp.transform("max").to_numpy()
        decay = np.exp2(-(latest - train.timestamp.to_numpy()) / (180 * 86400))
        weights = np.maximum(values - 3, 0) * decay
        profiles = csr_matrix((weights, (rows, cols)), shape=self.history.shape) @ self.features
        self.profiles = (profiles / np.maximum(np.linalg.norm(profiles, axis=1, keepdims=True), 1e-8)).astype(np.float32)
        # Adjusted cosine: center each observed rating by the user's mean.
        residual = csr_matrix((values - self.user_means[rows], (rows, cols)), shape=self.history.shape)
        binary = self.history.copy()
        binary.data = np.ones_like(binary.data)
        norms = np.sqrt(np.asarray(residual.power(2).sum(axis=0)).ravel())
        normalized = residual @ diags(1 / np.maximum(norms, 1e-8))
        edge_rows, edge_cols, edge_values = [], [], []
        # Block computation bounds memory; retain only positive top neighbors.
        for start in range(0, len(self.movie_ids), 256):
            stop = min(start + 256, len(self.movie_ids))
            sims = (normalized[:, start:stop].T @ normalized).toarray()
            co = (binary[:, start:stop].T @ binary).toarray()
            sims *= co / (co + 15)
            for local, row in enumerate(sims):
                row[start + local] = 0
                indices = np.argsort(-row, kind="stable")[:neighbors]
                indices = indices[row[indices] > 0]
                edge_rows.extend([start + local] * len(indices))
                edge_cols.extend(indices)
                edge_values.extend(row[indices])
        self.similarities = csr_matrix((edge_values, (edge_rows, edge_cols)), shape=(len(self.movie_ids), len(self.movie_ids)), dtype=np.float32)
        # Baseline residual SVD is distinct from the legacy SGD FunkSVD model.
        self.user_bias = ((self.user_means - self.global_mean) * counts_user / (counts_user + 10)).astype(np.float32)
        adjusted = values - self.global_mean - self.user_bias[rows]
        self.item_bias = (np.bincount(cols, weights=adjusted, minlength=len(self.movie_ids)) / (self.counts + 25)).astype(np.float32)
        residual_svd = csr_matrix((adjusted - self.item_bias[cols], (rows, cols)), shape=self.history.shape)
        rank = max(1, min(factors, min(self.history.shape)))
        left, singular, right = randomized_svd(residual_svd, n_components=rank, n_iter=4, random_state=42)
        self.user_factors = (left * np.sqrt(singular)).astype(np.float32)
        self.item_factors = (right.T * np.sqrt(singular)).astype(np.float32)
        self.training_seconds = time.perf_counter() - started
        self.ready = True
        return self

    def save(self, path: Path, data_fingerprint: str, manifest: dict):
        import json
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        arrays = {key: getattr(self, key) for key in ("movie_ids", "user_ids", "user_means", "profiles", "counts", "means", "popularity", "user_bias", "item_bias", "user_factors", "item_factors")}
        for prefix, matrix in (("history", self.history), ("similarities", self.similarities)):
            arrays.update({f"{prefix}_{key}": getattr(matrix, key) for key in ("data", "indices", "indptr", "shape")})
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, **arrays, global_mean=self.global_mean, training_seconds=self.training_seconds,
                                fingerprint=data_fingerprint, manifest=json.dumps(manifest))
        temporary.replace(path)

    def load(self, path: Path, expected_fingerprint: str):
        import json
        with np.load(path, allow_pickle=False) as arrays:
            if str(arrays["fingerprint"]) != expected_fingerprint or not np.array_equal(arrays["movie_ids"], self.movie_ids):
                raise ValueError("Artifact does not match dataset; run python -m src.cli train")
            for key in ("user_ids", "user_means", "profiles", "counts", "means", "popularity", "user_bias", "item_bias", "user_factors", "item_factors"):
                setattr(self, key, arrays[key].copy())
            for prefix in ("history", "similarities"):
                setattr(self, prefix, csr_matrix((arrays[f"{prefix}_data"], arrays[f"{prefix}_indices"], arrays[f"{prefix}_indptr"]), shape=tuple(arrays[f"{prefix}_shape"])))
            self.global_mean = float(arrays["global_mean"])
            self.training_seconds = float(arrays["training_seconds"])
            self.manifest = json.loads(str(arrays["manifest"]))
        self.user_index = {int(uid): i for i, uid in enumerate(self.user_ids)}
        self.ready = True
        return self

    def signals(self, user_id=None, ratings=None, preferred_genres=None, seed_ids=None):
        n = len(self.movie_ids)
        known = user_id in self.user_index
        uid = self.user_index.get(user_id)
        history = self.history.getrow(uid) if known else csr_matrix((1, n), dtype=np.float32)
        history = history.copy().tolil()
        for mid, value in (ratings or {}).items():
            if int(mid) in self.movie_index:
                history[0, self.movie_index[int(mid)]] = float(value)
        history = history.tocsr()
        history.eliminate_zeros()
        seen = set(history.indices)
        profile = self.profiles[uid].copy() if known and not ratings else np.zeros(len(self.genres), dtype=np.float32)
        if history.nnz and (ratings or not known):
            profile = np.maximum(history.data - 3, 0) @ self.features[history.indices]
        for genre in preferred_genres or []:
            profile[self.genre_index[genre.lower()]] += 1.5
        for mid in seed_ids or []:
            index = self.movie_index[int(mid)]
            profile += self.features[index] * 2
            seen.add(index)
        norm = np.linalg.norm(profile)
        profile /= max(norm, 1e-8)
        content = self.features @ profile
        cf = self.popularity.copy()
        if history.nnz:
            mean = float(history.data.mean())
            weights = self.similarities[:, history.indices]
            denominator = np.asarray(weights.sum(axis=1)).ravel()
            numerator = np.asarray(weights @ (history.data - mean)).ravel()
            np.divide(numerator, denominator, out=cf, where=denominator > 1e-8)
            cf[denominator > 1e-8] += mean
        cf = np.clip(cf, 1, 5)
        svd = self.popularity.copy()
        if known:
            svd = np.clip(self.global_mean + self.user_bias[uid] + self.item_bias + self.item_factors @ self.user_factors[uid], 1, 5)
        return {"popularity": self.popularity, "content": content, "collaborative": cf, "svd": svd}, seen, profile

    def recommend(self, user_id=None, ratings=None, preferred_genres=None, seed_ids=None,
                  model="hybrid", k=12, diversity=.2, genre=None, year_min=None, year_max=None, exclude_ids=None):
        if not self.ready:
            raise RuntimeError("Engine not fitted")
        if model not in MODELS:
            raise ValueError("Unknown model")
        if not 1 <= k <= 50 or not 0 <= diversity <= 1:
            raise ValueError("Invalid k or diversity")
        for g in (preferred_genres or []) + ([genre] if genre else []):
            if g.lower() not in self.genre_index:
                raise ValueError(f"Unknown genre: {g}")
        if any(int(mid) not in self.movie_index for mid in seed_ids or []):
            raise ValueError("Unknown seed movie")
        if year_min is not None and year_max is not None and year_min > year_max:
            raise ValueError("year_min must not exceed year_max")
        signals, seen, profile = self.signals(user_id, ratings, preferred_genres, seed_ids)
        seen.update(self.movie_index[int(mid)] for mid in exclude_ids or [] if int(mid) in self.movie_index)
        mask = np.ones(len(self.movie_ids), dtype=bool)
        mask[list(seen)] = False
        if genre:
            mask &= self.features[:, self.genre_index[genre.lower()]] > 0
        years = self.movies.year.to_numpy(dtype=float)
        if year_min is not None:
            mask &= years >= year_min
        if year_max is not None:
            mask &= years <= year_max
        candidates = np.flatnonzero(mask)
        if not len(candidates):
            return []
        has_history = bool(ratings) or user_id in self.user_index
        has_content = np.linalg.norm(profile) > 0
        normalized = {name: normalize(values[candidates]) for name, values in signals.items()}
        if model == "hybrid":
            weights = {"collaborative": .35 if has_history else 0, "svd": .25 if user_id in self.user_index else 0,
                       "content": .25 if has_content else 0, "popularity": .15}
            scores = sum(weights[name] * normalized[name] for name in weights) / sum(weights.values())
        else:
            effective = "popularity" if (model == "svd" and user_id not in self.user_index) or (model == "collaborative" and not has_history) or (model == "content" and not has_content) else model
            scores = normalized[effective]
        pool_order = np.argsort(-scores, kind="stable")[:max(200, k * 5)]
        pool = candidates[pool_order]
        pool_scores = scores[pool_order]
        selected = []
        penalties = np.zeros(len(pool))
        available = np.ones(len(pool), dtype=bool)
        for _ in range(min(k, len(pool))):
            mmr = (1 - diversity) * pool_scores - diversity * penalties
            mmr[~available] = -np.inf
            choice = int(np.argmax(mmr))
            selected.append(choice)
            available[choice] = False
            penalties = np.maximum(penalties, self.features[pool] @ self.features[pool[choice]])
        results = []
        for choice in selected:
            index = int(pool[choice])
            row = self.movies.iloc[index]
            matches = [g for g in row.genres_list if profile[self.genre_index[g.lower()]] > .15]
            if model == "content" or (model == "hybrid" and has_content):
                reason = f"Hợp gu {', '.join(matches[:3])}" if matches else "Kết hợp gu phim và điểm cộng đồng"
            elif (model == "collaborative" and has_history) or (model == "svd" and user_id in self.user_index):
                reason = "Gợi ý từ mẫu đánh giá của cộng đồng" if model == "collaborative" else "Phù hợp với nhân tố sở thích trong lịch sử MovieLens"
            else:
                reason = "Được cộng đồng đánh giá cao sau hiệu chỉnh Bayesian"
            results.append(self.movie(int(row.movie_id), score=float(pool_scores[choice]), reason=reason,
                                      predicted_rating=float(signals[model][index]) if model in ("popularity", "collaborative", "svd") else None))
        return results

    def movie(self, movie_id, **extra):
        index = self.movie_index[int(movie_id)]
        row = self.movies.iloc[index]
        return {"movie_id": int(movie_id), "title": str(row.title_clean), "full_title": str(row.title),
                "genres": str(row.genres), "year": int(row.year) if pd.notna(row.year) else None,
                "rating": round(float(self.means[index]), 2) if self.counts[index] else None,
                "rating_count": int(self.counts[index]), "bayesian_rating": round(float(self.popularity[index]), 2), **extra}

    def similar(self, movie_id, k=8):
        target = self.movie_index[int(movie_id)]
        content = self.features @ self.features[target]
        co = self.similarities.getrow(target).toarray().ravel()
        scores = .65 * content + .25 * normalize(co) + .1 * normalize(self.popularity)
        scores[target] = -np.inf
        return [self.movie(int(self.movie_ids[i]), score=round(float(scores[i]), 4), reason="Gần nhau về thể loại và hành vi đánh giá")
                for i in np.argsort(-scores, kind="stable")[:min(k, len(scores) - 1)]]
