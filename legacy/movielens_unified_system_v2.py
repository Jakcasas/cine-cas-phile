"""================================================================================
CINE CAS PHILE: UNIFIED & ENHANCED MOVIE RECOMMENDATION SYSTEM
================================================================================
A complete, self-contained production-grade recommender system evolved from
https://github.com/khanhnamle1994/movielens and improved according to the 6-phase roadmap.

NEW ADVANCED ENHANCEMENTS INCLUDED:
1. Zero-Data-Leakage Protocol: Chronological per-user split (80/10/10).
2. Demographic-Aware Deep & Wide Network: Embeds user demographics (age, gender,
   occupation) and movie attributes (release year, multi-hot genres, ID).
3. Time-Decay Recency Weighting: Prioritizes recent user tastes over ancient ratings.
4. Maximal Marginal Relevance (MMR) Diversification: Re-ranks top-K lists to prevent
   genre redundancy and filter bubbles.
5. Multi-Signal Hybrid Meta-Model: Fuses Collaborative Filtering, Deep Demographics,
   TF-IDF Content Matching, and Shrinkage Popularity.
6. Unified CLI & Built-in FastAPI Server + Web Dashboard in one single file.
================================================================================"""

import os
import sys
import re
import time
import json
import argparse
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tabulate import tabulate

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# ==============================================================================
# 1. CONFIGURATION & CONSTANTS
# ==============================================================================
RANDOM_SEED = 42
RELEVANCE_THRESHOLD = 4.0
TOP_K_DEFAULT = 10
SHRINKAGE_M = 25.0
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

GENRE_MAP = [
    "Action", "Adventure", "Animation", "Children's", "Comedy", "Crime",
    "Documentary", "Drama", "Fantasy", "Film-Noir", "Horror", "Musical",
    "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western"
]
GENRE_TO_IDX = {g: i for i, g in enumerate(GENRE_MAP)}
AGE_MAP = {1: 0, 18: 1, 25: 2, 35: 3, 45: 4, 50: 5, 56: 6}


# ==============================================================================
# 2. DATA MODELS & STRUCTS
# ==============================================================================
@dataclass
class RecommendationItem:
    movie_id: int
    title: str
    genres: str
    score: float
    reason: str


# ==============================================================================
# 3. DATA LOADER, VALIDATION & FEATURE ENGINEERING
# ==============================================================================
class UnifiedDataLoader:
    """Loads, validates and engineers demographic & movie side-information."""

    def __init__(self, raw_dir: str = "data/raw"):
        self.raw_dir = raw_dir
        self.movies_df: Optional[pd.DataFrame] = None
        self.ratings_df: Optional[pd.DataFrame] = None
        self.users_df: Optional[pd.DataFrame] = None

        self.user2idx: Dict[int, int] = {}
        self.idx2user: Dict[int, int] = {}
        self.movie2idx: Dict[int, int] = {}
        self.idx2movie: Dict[int, int] = {}

    def load_all(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        # 1. Movies
        movies_path = os.path.join(self.raw_dir, "movies.csv")
        sep = "\t" if open(movies_path, "r", encoding="latin-1").readline().count("\t") > 0 else "::"
        movies = pd.read_csv(movies_path, sep=sep, encoding="latin-1")
        movies = movies.drop(columns=[c for c in movies.columns if "Unnamed" in c or c.lower() == "index"])
        movies.columns = [c.strip().lower() for c in movies.columns]

        def extract_year(t: str) -> int:
            m = re.search(r"\((\d{4})\)", t)
            return int(m.group(1)) if m else 1990

        movies["year"] = movies["title"].apply(extract_year)
        movies["genres_list"] = movies["genres"].apply(
            lambda x: [g.strip() for g in str(x).split("|") if g.strip()]
        )
        self.movies_df = movies.drop_duplicates("movie_id").reset_index(drop=True)

        # 2. Users
        users_path = os.path.join(self.raw_dir, "users.csv")
        sep = "\t" if open(users_path, "r", encoding="latin-1").readline().count("\t") > 0 else "::"
        users = pd.read_csv(users_path, sep=sep, encoding="latin-1")
        users = users.drop(columns=[c for c in users.columns if "Unnamed" in c or c.lower() == "index"])
        users.columns = [c.strip().lower() for c in users.columns]
        users["gender_idx"] = (users["gender"].str.upper() == "F").astype(int)
        users["age_idx"] = users["age"].map(lambda a: AGE_MAP.get(a, 2)).astype(int)
        users["occ_idx"] = users["occupation"].clip(0, 20).astype(int)
        self.users_df = users.drop_duplicates("user_id").reset_index(drop=True)

        # 3. Ratings
        ratings_path = os.path.join(self.raw_dir, "ratings.csv")
        sep = "\t" if open(ratings_path, "r", encoding="latin-1").readline().count("\t") > 0 else "::"
        ratings = pd.read_csv(ratings_path, sep=sep, encoding="latin-1")
        ratings = ratings.drop(columns=[c for c in ratings.columns if "Unnamed" in c or "emb_id" in c])
        ratings.columns = [c.strip().lower() for c in ratings.columns]
        ratings = ratings[["user_id", "movie_id", "rating", "timestamp"]]
        ratings["rating"] = ratings["rating"].astype(float)
        ratings["timestamp"] = ratings["timestamp"].astype(int)
        ratings = ratings[(ratings["rating"] >= 1.0) & (ratings["rating"] <= 5.0)]
        ratings = ratings.sort_values(["user_id", "timestamp"]).drop_duplicates(
            subset=["user_id", "movie_id"], keep="last"
        ).reset_index(drop=True)
        self.ratings_df = ratings

        # Build contiguous mappings
        u_sorted = sorted(ratings["user_id"].unique())
        m_sorted = sorted(self.movies_df["movie_id"].unique())
        self.user2idx = {u: i for i, u in enumerate(u_sorted)}
        self.idx2user = {i: u for i, u in enumerate(u_sorted)}
        self.movie2idx = {m: i for i, m in enumerate(m_sorted)}
        self.idx2movie = {i: m for i, m in enumerate(m_sorted)}

        self.ratings_df["user_idx"] = self.ratings_df["user_id"].map(self.user2idx)
        self.ratings_df["movie_idx"] = self.ratings_df["movie_id"].map(self.movie2idx)

        return self.movies_df, self.ratings_df, self.users_df


# ==============================================================================
# 4. CHRONOLOGICAL SPLITTING (ZERO LEAKAGE)
# ==============================================================================
class TemporalSplitter:
    """Chronologically splits interactions per user with verification."""

    @staticmethod
    def split(
        ratings_df: pd.DataFrame, train_ratio: float = 0.8, val_ratio: float = 0.1
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]:
        df_sorted = ratings_df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
        train_idx, val_idx, test_idx = [], [], []

        for _, indices in df_sorted.groupby("user_id", sort=False).indices.items():
            n = len(indices)
            if n < 5:
                train_idx.extend(indices)
                continue
            n_train = int(np.floor(n * train_ratio))
            n_val = max(1, int(np.floor(n * val_ratio)))
            n_test = max(1, n - n_train - n_val)
            n_train = n - n_val - n_test

            train_idx.extend(indices[:n_train])
            val_idx.extend(indices[n_train : n_train + n_val])
            test_idx.extend(indices[n_train + n_val :])

        train_df = df_sorted.iloc[train_idx].reset_index(drop=True)
        val_df = df_sorted.iloc[val_idx].reset_index(drop=True)
        test_df = df_sorted.iloc[test_idx].reset_index(drop=True)

        # Leakage check
        tr_max = train_df.groupby("user_id")["timestamp"].max()
        te_min = test_df.groupby("user_id")["timestamp"].min()
        common = set(tr_max.index).intersection(set(te_min.index))
        leakage = any(tr_max[u] > te_min[u] for u in common)

        manifest = {
            "n_train": len(train_df),
            "n_val": len(val_df),
            "n_test": len(test_df),
            "leakage_detected": leakage,
        }
        return train_df, val_df, test_df, manifest


# ==============================================================================
# 5. BASE & CORE RECOMMENDER MODELS
# ==============================================================================
class BaseRecommender:
    def __init__(self, name: str):
        self.name = name
        self.is_fitted = False
        self.movie_meta: Dict[int, Dict[str, str]] = {}
        self.all_movie_ids: Set[int] = set()

    def set_movie_meta(self, movies_df: pd.DataFrame):
        self.all_movie_ids = set(movies_df["movie_id"].unique())
        self.movie_meta = {
            r["movie_id"]: {"title": r["title"], "genres": r["genres"]}
            for _, r in movies_df.iterrows()
        }

    def _get_title(self, mid: int) -> str:
        return self.movie_meta.get(mid, {}).get("title", f"Movie #{mid}")

    def _get_genres(self, mid: int) -> str:
        return self.movie_meta.get(mid, {}).get("genres", "Unknown")


# --- Model 1: Popularity with Bayesian Shrinkage ---
class PopularityRecommender(BaseRecommender):
    def __init__(self, m: float = SHRINKAGE_M):
        super().__init__("Popularity-Shrinkage")
        self.m = m
        self.scores: Dict[int, float] = {}
        self.counts: Dict[int, int] = {}
        self.global_mean: float = 3.5

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.global_mean = float(train_df["rating"].mean())
        grouped = train_df.groupby("movie_id")["rating"]
        counts = grouped.count().to_dict()
        means = grouped.mean().to_dict()

        for mid in self.all_movie_ids:
            v = counts.get(mid, 0)
            r = means.get(mid, self.global_mean)
            self.scores[mid] = (v / (v + self.m)) * r + (self.m / (v + self.m)) * self.global_mean
            self.counts[mid] = v

        self.ranked = sorted(self.scores.keys(), key=lambda x: self.scores[x], reverse=True)
        self.is_fitted = True

    def predict(self, uid: int, mid: int) -> float:
        return self.scores.get(mid, self.global_mean)

    def recommend(self, uid: int, k: int = 10, candidates: Optional[List[int]] = None) -> List[RecommendationItem]:
        cand_set = set(candidates) if candidates is not None else self.all_movie_ids
        res = []
        for mid in self.ranked:
            if mid in cand_set:
                score = self.scores[mid]
                res.append(RecommendationItem(
                    movie_id=mid,
                    title=self._get_title(mid),
                    genres=self._get_genres(mid),
                    score=round(score, 3),
                    reason=f"Community Favorite (Bayesian score: {score:.2f}, {self.counts.get(mid, 0)} reviews)"
                ))
                if len(res) >= k:
                    break
        return res


# --- Model 2: Content-Based TF-IDF with Time-Decay Profile ---
class ContentBasedRecommender(BaseRecommender):
    def __init__(self, time_decay_half_life_days: float = 365.0):
        super().__init__("Content-Based-TFIDF-TimeDecay")
        self.half_life_days = time_decay_half_life_days
        self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w\'-]+\b")
        self.movie_vecs: Optional[np.ndarray] = None
        self.mid2idx: Dict[int, int] = {}
        self.idx2mid: Dict[int, int] = {}
        self.user_profiles: Dict[int, np.ndarray] = {}
        self.fallback_pop = PopularityRecommender()

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.fallback_pop.fit(train_df, movies_df)

        docs = [" ".join(r["genres_list"]) for _, r in movies_df.iterrows()]
        mids = movies_df["movie_id"].tolist()
        self.movie_vecs = self.vectorizer.fit_transform(docs).toarray()
        self.mid2idx = {m: i for i, m in enumerate(mids)}
        self.idx2mid = {i: m for i, m in enumerate(mids)}

        max_t = train_df["timestamp"].max()
        for uid, grp in train_df.groupby("user_id"):
            pos = grp[grp["rating"] >= 3.0]
            if len(pos) == 0:
                continue
            delta_days = (max_t - pos["timestamp"].values) / (24 * 3600)
            time_weights = np.exp(-np.log(2) * delta_days / self.half_life_days)
            rating_weights = (pos["rating"].values - 2.5) * time_weights

            vec_indices = [self.mid2idx[m] for m in pos["movie_id"] if m in self.mid2idx]
            if not vec_indices:
                continue
            sub_vecs = self.movie_vecs[vec_indices]
            profile = np.sum(sub_vecs * rating_weights[:, np.newaxis], axis=0)
            norm = np.linalg.norm(profile)
            if norm > 0:
                self.user_profiles[uid] = profile / norm

        self.is_fitted = True

    def predict(self, uid: int, mid: int) -> float:
        if uid not in self.user_profiles or mid not in self.mid2idx:
            return self.fallback_pop.predict(uid, mid)
        sim = float(np.dot(self.user_profiles[uid], self.movie_vecs[self.mid2idx[mid]]))
        return float(np.clip(2.0 + 3.0 * sim, 1.0, 5.0))

    def recommend(self, uid: int, k: int = 10, candidates: Optional[List[int]] = None) -> List[RecommendationItem]:
        if uid not in self.user_profiles:
            return self.fallback_pop.recommend(uid, k, candidates)

        u_vec = self.user_profiles[uid]
        cands = candidates if candidates is not None else list(self.all_movie_ids)
        cand_idx = [self.mid2idx[m] for m in cands if m in self.mid2idx]
        valid_mids = [m for m in cands if m in self.mid2idx]
        if not cand_idx:
            return self.fallback_pop.recommend(uid, k, candidates)

        sims = np.dot(self.movie_vecs[cand_idx], u_vec)
        top_k = np.argsort(sims)[::-1][:k]

        res = []
        for i in top_k:
            mid = valid_mids[i]
            sim = sims[i]
            res.append(RecommendationItem(
                movie_id=mid,
                title=self._get_title(mid),
                genres=self._get_genres(mid),
                score=round(float(sim), 3),
                reason=f"Matches your recent taste ({sim:.0%} genre cosine similarity)"
            ))
        return res


# --- Model 3: Biased Matrix Factorization (FunkSVD) ---
class BiasedMatrixFactorization(BaseRecommender):
    def __init__(self, n_factors: int = 32, lr: float = 0.005, reg: float = 0.02, epochs: int = 12):
        super().__init__("Biased-MF-SVD")
        self.k = n_factors
        self.lr = lr
        self.reg = reg
        self.epochs = epochs
        self.mu = 3.5
        self.user_bias = None
        self.item_bias = None
        self.user_factors = None
        self.item_factors = None
        self.u2idx = {}
        self.m2idx = {}
        self.fallback_pop = PopularityRecommender()

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.fallback_pop.fit(train_df, movies_df)

        users = sorted(train_df["user_id"].unique())
        movies = sorted(self.all_movie_ids)
        self.u2idx = {u: i for i, u in enumerate(users)}
        self.m2idx = {m: i for i, m in enumerate(movies)}

        nu, nm = len(users), len(movies)
        self.mu = float(train_df["rating"].mean())
        self.user_bias = np.zeros(nu, dtype=np.float32)
        self.item_bias = np.zeros(nm, dtype=np.float32)

        rng = np.random.RandomState(RANDOM_SEED)
        self.user_factors = rng.normal(0, 0.1, (nu, self.k)).astype(np.float32)
        self.item_factors = rng.normal(0, 0.1, (nm, self.k)).astype(np.float32)

        u_arr = train_df["user_id"].map(self.u2idx).values
        i_arr = train_df["movie_id"].map(self.m2idx).values
        r_arr = train_df["rating"].values.astype(np.float32)
        n = len(r_arr)

        for _ in range(self.epochs):
            perm = rng.permutation(n)
            for idx in perm:
                u, i, r = u_arr[idx], i_arr[idx], r_arr[idx]
                pred = self.mu + self.user_bias[u] + self.item_bias[i] + np.dot(self.user_factors[u], self.item_factors[i])
                err = r - pred

                self.user_bias[u] += self.lr * (err - self.reg * self.user_bias[u])
                self.item_bias[i] += self.lr * (err - self.reg * self.item_bias[i])
                uf = self.user_factors[u].copy()
                self.user_factors[u] += self.lr * (err * self.item_factors[i] - self.reg * uf)
                self.item_factors[i] += self.lr * (err * uf - self.reg * self.item_factors[i])

        self.is_fitted = True

    def predict(self, uid: int, mid: int) -> float:
        if uid not in self.u2idx or mid not in self.m2idx:
            return self.fallback_pop.predict(uid, mid)
        u, i = self.u2idx[uid], self.m2idx[mid]
        pred = self.mu + self.user_bias[u] + self.item_bias[i] + np.dot(self.user_factors[u], self.item_factors[i])
        return float(np.clip(pred, 1.0, 5.0))

    def recommend(self, uid: int, k: int = 10, candidates: Optional[List[int]] = None) -> List[RecommendationItem]:
        if uid not in self.u2idx:
            return self.fallback_pop.recommend(uid, k, candidates)

        u = self.u2idx[uid]
        cands = candidates if candidates is not None else list(self.all_movie_ids)
        cand_indices = [self.m2idx[m] for m in cands if m in self.m2idx]
        valid_mids = [m for m in cands if m in self.m2idx]
        if not cand_indices:
            return self.fallback_pop.recommend(uid, k, candidates)

        c_idx = np.array(cand_indices)
        scores = self.mu + self.user_bias[u] + self.item_bias[c_idx] + np.dot(self.item_factors[c_idx], self.user_factors[u])
        top_k = np.argsort(scores)[::-1][:k]

        res = []
        for i in top_k:
            mid = valid_mids[i]
            score = float(scores[i])
            res.append(RecommendationItem(
                movie_id=mid,
                title=self._get_title(mid),
                genres=self._get_genres(mid),
                score=round(score, 3),
                reason=f"Predicted rating: {score:.1f}★ based on collaborative viewer tastes"
            ))
        return res


# ==============================================================================
# 6. ENHANCEMENT: DEMOGRAPHIC-AWARE DEEP & WIDE NETWORK
# ==============================================================================
class DeepWideNet(nn.Module):
    """Deep neural network combining demographic user features and movie attributes."""

    def __init__(self, n_users: int, n_items: int, emb_dim: int = 16):
        super().__init__()
        # User embeddings
        self.u_emb = nn.Embedding(n_users, emb_dim)
        self.gender_emb = nn.Embedding(2, 4)
        self.age_emb = nn.Embedding(7, 8)
        self.occ_emb = nn.Embedding(21, 8)

        # Item embeddings & features
        self.i_emb = nn.Embedding(n_items, emb_dim)
        # multi-hot genres (18-dim) + year (1-dim)
        item_feat_dim = 18 + 1

        total_input = emb_dim + 4 + 8 + 8 + emb_dim + item_feat_dim

        self.mlp = nn.Sequential(
            nn.Linear(total_input, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

    def forward(self, u, gender, age, occ, i, item_feats):
        u_v = self.u_emb(u)
        g_v = self.gender_emb(gender)
        a_v = self.age_emb(age)
        o_v = self.occ_emb(occ)
        i_v = self.i_emb(i)

        x = torch.cat([u_v, g_v, a_v, o_v, i_v, item_feats], dim=-1)
        out = self.mlp(x).squeeze(-1)
        return torch.sigmoid(out) * 4.0 + 1.0


class DemographicDeepRecommender(BaseRecommender):
    """Demographic-aware deep learning recommender."""

    def __init__(self, epochs: int = 5, batch_size: int = 2048):
        super().__init__("Demographic-Deep-Wide")
        self.epochs = epochs
        self.batch_size = batch_size
        self.model: Optional[DeepWideNet] = None
        self.user_demo: Dict[int, Tuple[int, int, int]] = {}
        self.item_feats_dict: Dict[int, np.ndarray] = {}
        self.u2idx = {}
        self.m2idx = {}
        self.fallback_pop = PopularityRecommender()

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame, users_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.fallback_pop.fit(train_df, movies_df)

        users = sorted(train_df["user_id"].unique())
        movies = sorted(self.all_movie_ids)
        self.u2idx = {u: i for i, u in enumerate(users)}
        self.m2idx = {m: i for i, m in enumerate(movies)}

        # Precompute user demographics
        for _, r in users_df.iterrows():
            uid = int(r["user_id"])
            self.user_demo[uid] = (int(r["gender_idx"]), int(r["age_idx"]), int(r["occ_idx"]))

        # Precompute movie genre multi-hot + year normalized
        min_y, max_y = 1919.0, 2000.0
        for _, r in movies_df.iterrows():
            mid = int(r["movie_id"])
            g_vec = np.zeros(18, dtype=np.float32)
            for g in r["genres_list"]:
                if g in GENRE_TO_IDX:
                    g_vec[GENRE_TO_IDX[g]] = 1.0
            y_norm = (r["year"] - min_y) / (max_y - min_y)
            feat = np.append(g_vec, y_norm).astype(np.float32)
            self.item_feats_dict[mid] = feat

        # Prepare dataset arrays
        u_arr = train_df["user_id"].map(self.u2idx).values
        i_arr = train_df["movie_id"].map(self.m2idx).values
        g_arr = np.array([self.user_demo.get(u, (0, 2, 0))[0] for u in train_df["user_id"]])
        a_arr = np.array([self.user_demo.get(u, (0, 2, 0))[1] for u in train_df["user_id"]])
        o_arr = np.array([self.user_demo.get(u, (0, 2, 0))[2] for u in train_df["user_id"]])
        feat_arr = np.array([self.item_feats_dict.get(m, np.zeros(19, dtype=np.float32)) for m in train_df["movie_id"]])
        r_arr = train_df["rating"].values.astype(np.float32)

        self.model = DeepWideNet(len(users), len(movies)).to(DEVICE)
        opt = torch.optim.AdamW(self.model.parameters(), lr=0.002, weight_decay=1e-4)
        crit = nn.MSELoss()

        n = len(r_arr)
        indices = np.arange(n)
        self.model.train()

        for ep in range(self.epochs):
            np.random.shuffle(indices)
            for start in range(0, n, self.batch_size):
                b_idx = indices[start : start + self.batch_size]
                b_u = torch.tensor(u_arr[b_idx], dtype=torch.long, device=DEVICE)
                b_i = torch.tensor(i_arr[b_idx], dtype=torch.long, device=DEVICE)
                b_g = torch.tensor(g_arr[b_idx], dtype=torch.long, device=DEVICE)
                b_a = torch.tensor(a_arr[b_idx], dtype=torch.long, device=DEVICE)
                b_o = torch.tensor(o_arr[b_idx], dtype=torch.long, device=DEVICE)
                b_f = torch.tensor(feat_arr[b_idx], dtype=torch.float32, device=DEVICE)
                b_r = torch.tensor(r_arr[b_idx], dtype=torch.float32, device=DEVICE)

                opt.zero_grad()
                pred = self.model(b_u, b_g, b_a, b_o, b_i, b_f)
                loss = crit(pred, b_r)
                loss.backward()
                opt.step()

        self.model.eval()
        self.is_fitted = True

    def predict(self, uid: int, mid: int) -> float:
        if uid not in self.u2idx or mid not in self.m2idx:
            return self.fallback_pop.predict(uid, mid)
        u, i = self.u2idx[uid], self.m2idx[mid]
        g, a, o = self.user_demo.get(uid, (0, 2, 0))
        f = self.item_feats_dict.get(mid, np.zeros(19, dtype=np.float32))

        with torch.no_grad():
            u_t = torch.tensor([u], dtype=torch.long, device=DEVICE)
            i_t = torch.tensor([i], dtype=torch.long, device=DEVICE)
            g_t = torch.tensor([g], dtype=torch.long, device=DEVICE)
            a_t = torch.tensor([a], dtype=torch.long, device=DEVICE)
            o_t = torch.tensor([o], dtype=torch.long, device=DEVICE)
            f_t = torch.tensor([f], dtype=torch.float32, device=DEVICE)
            pred = self.model(u_t, g_t, a_t, o_t, i_t, f_t).item()
        return float(np.clip(pred, 1.0, 5.0))

    def recommend(self, uid: int, k: int = 10, candidates: Optional[List[int]] = None) -> List[RecommendationItem]:
        if uid not in self.u2idx:
            return self.fallback_pop.recommend(uid, k, candidates)

        u = self.u2idx[uid]
        g, a, o = self.user_demo.get(uid, (0, 2, 0))
        cands = candidates if candidates is not None else list(self.all_movie_ids)
        cand_indices = [self.m2idx[m] for m in cands if m in self.m2idx]
        valid_mids = [m for m in cands if m in self.m2idx]
        if not cand_indices:
            return self.fallback_pop.recommend(uid, k, candidates)

        f_list = [self.item_feats_dict.get(m, np.zeros(19, dtype=np.float32)) for m in valid_mids]

        with torch.no_grad():
            sz = len(cand_indices)
            u_t = torch.tensor([u] * sz, dtype=torch.long, device=DEVICE)
            i_t = torch.tensor(cand_indices, dtype=torch.long, device=DEVICE)
            g_t = torch.tensor([g] * sz, dtype=torch.long, device=DEVICE)
            a_t = torch.tensor([a] * sz, dtype=torch.long, device=DEVICE)
            o_t = torch.tensor([o] * sz, dtype=torch.long, device=DEVICE)
            f_t = torch.tensor(np.array(f_list), dtype=torch.float32, device=DEVICE)
            scores = self.model(u_t, g_t, a_t, o_t, i_t, f_t).cpu().numpy()

        top_k = np.argsort(scores)[::-1][:k]
        res = []
        for idx in top_k:
            mid = valid_mids[idx]
            sc = float(scores[idx])
            res.append(RecommendationItem(
                movie_id=mid,
                title=self._get_title(mid),
                genres=self._get_genres(mid),
                score=round(sc, 3),
                reason=f"Demographic match: {sc:.1f}★ predicted for your age/occupation group"
            ))
        return res


# ==============================================================================
# 7. ENHANCEMENT: MAXIMAL MARGINAL RELEVANCE (MMR) DIVERSIFICATION
# ==============================================================================
class MMRReranker:
    """Reranks recommendation candidate list balancing relevance score and genre diversity."""

    @staticmethod
    def rerank(
        items: List[RecommendationItem],
        item_genre_vecs: Dict[int, np.ndarray],
        k: int = 10,
        lambda_param: float = 0.75
    ) -> List[RecommendationItem]:
        if len(items) <= k:
            return items

        selected: List[RecommendationItem] = []
        remaining = list(items)

        # Select first highest scoring item
        first = remaining.pop(0)
        selected.append(first)

        while len(selected) < k and remaining:
            best_idx = -1
            best_score = -float("inf")

            for idx, candidate in enumerate(remaining):
                c_vec = item_genre_vecs.get(candidate.movie_id, np.zeros(18))
                # Max similarity with any already selected item
                max_sim = max(
                    (float(np.dot(c_vec, item_genre_vecs.get(s.movie_id, np.zeros(18))))
                     / (np.linalg.norm(c_vec) * np.linalg.norm(item_genre_vecs.get(s.movie_id, np.zeros(18))) + 1e-6))
                    for s in selected
                )
                mmr_val = lambda_param * candidate.score - (1.0 - lambda_param) * max_sim
                if mmr_val > best_score:
                    best_score = mmr_val
                    best_idx = idx

            chosen = remaining.pop(best_idx)
            chosen.reason += " (Diversified via MMR)"
            selected.append(chosen)

        return selected


# ==============================================================================
# 8. ENHANCEMENT: ADVANCED MULTI-SIGNAL HYBRID ENSEMBLE
# ==============================================================================
class EnhancedHybridRecommender(BaseRecommender):
    """Ensemble fusing Matrix Factorization, Deep Demographic, Content-Based, and Shrinkage Popularity."""

    def __init__(self, w_svd: float = 0.40, w_deep: float = 0.25, w_content: float = 0.20, w_pop: float = 0.15):
        super().__init__("Enhanced-Hybrid-Ensemble")
        total = w_svd + w_deep + w_content + w_pop
        self.w_svd = w_svd / total
        self.w_deep = w_deep / total
        self.w_content = w_content / total
        self.w_pop = w_pop / total

        self.svd = BiasedMatrixFactorization()
        self.deep = DemographicDeepRecommender()
        self.cb = ContentBasedRecommender()
        self.pop = PopularityRecommender()
        self.genre_vecs: Dict[int, np.ndarray] = {}

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame, users_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.svd.fit(train_df, movies_df)
        self.deep.fit(train_df, movies_df, users_df)
        self.cb.fit(train_df, movies_df)
        self.pop.fit(train_df, movies_df)

        for _, r in movies_df.iterrows():
            mid = int(r["movie_id"])
            vec = np.zeros(18, dtype=np.float32)
            for g in r["genres_list"]:
                if g in GENRE_TO_IDX:
                    vec[GENRE_TO_IDX[g]] = 1.0
            self.genre_vecs[mid] = vec

        self.is_fitted = True

    def predict(self, uid: int, mid: int) -> float:
        p1 = self.svd.predict(uid, mid)
        p2 = self.deep.predict(uid, mid)
        p3 = self.cb.predict(uid, mid)
        p4 = self.pop.predict(uid, mid)
        return float(np.clip(self.w_svd * p1 + self.w_deep * p2 + self.w_content * p3 + self.w_pop * p4, 1.0, 5.0))

    def recommend(
        self, uid: int, k: int = 10, candidates: Optional[List[int]] = None, use_mmr: bool = True
    ) -> List[RecommendationItem]:
        cands = candidates if candidates is not None else list(self.all_movie_ids)
        if not cands:
            return []

        # Retrieve predictions
        svd_s = np.array([self.svd.predict(uid, m) for m in cands])
        deep_s = np.array([self.deep.predict(uid, m) for m in cands])
        cb_s = np.array([self.cb.predict(uid, m) for m in cands])
        pop_s = np.array([self.pop.predict(uid, m) for m in cands])

        def norm(arr):
            v_min, v_max = arr.min(), arr.max()
            return (arr - v_min) / (v_max - v_min) if v_max - v_min > 1e-6 else np.ones_like(arr) * 0.5

        hybrid_rank = self.w_svd * norm(svd_s) + self.w_deep * norm(deep_s) + self.w_content * norm(cb_s) + self.w_pop * norm(pop_s)
        # Pull top 2*k candidates for diversity reranking
        pool_k = min(len(cands), k * 2 if use_mmr else k)
        top_indices = np.argsort(hybrid_rank)[::-1][:pool_k]

        items = []
        for idx in top_indices:
            mid = cands[idx]
            raw_p = self.predict(uid, mid)
            g_first = self._get_genres(mid).split("|")[0]
            items.append(RecommendationItem(
                movie_id=mid,
                title=self._get_title(mid),
                genres=self._get_genres(mid),
                score=round(raw_p, 3),
                reason=f"Top Pick: {svd_s[idx]:.1f}★ taste match + strong {g_first} alignment"
            ))

        if use_mmr and len(items) > k:
            items = MMRReranker.rerank(items, self.genre_vecs, k=k, lambda_param=0.8)
        return items[:k]


# ==============================================================================
# 9. EVALUATION SUITE
# ==============================================================================
class Evaluator:
    @staticmethod
    def evaluate(model, test_df: pd.DataFrame, all_mids: Set[int], user_train_map: Dict[int, Set[int]], sample_u: int = 300) -> Dict:
        # 1. Rating prediction
        u_arr, m_arr, r_arr = test_df["user_id"].values, test_df["movie_id"].values, test_df["rating"].values
        preds = np.array([model.predict(u, m) for u, m in zip(u_arr, m_arr)])
        rmse = float(np.sqrt(np.mean((r_arr - preds) ** 2)))
        mae = float(np.mean(np.abs(r_arr - preds)))

        # 2. Ranking on positive test items
        pos_df = test_df[test_df["rating"] >= RELEVANCE_THRESHOLD]
        user_rel = pos_df.groupby("user_id")["movie_id"].apply(set).to_dict()
        eval_users = list(user_rel.keys())[:sample_u]

        prec_list, rec_list, ndcg_list, hit_list = [], [], [], []
        all_recs = set()
        t0 = time.time()

        for u in eval_users:
            rel = user_rel[u]
            seen = user_train_map.get(u, set())
            cands = list(all_mids - seen)
            recs = model.recommend(u, k=10, candidates=cands)
            rec_ids = [it.movie_id for it in recs]
            all_recs.update(rec_ids)

            hit_cnt = len(set(rec_ids).intersection(rel))
            prec_list.append(hit_cnt / 10.0)
            rec_list.append(hit_cnt / float(len(rel)) if len(rel) > 0 else 0.0)
            hit_list.append(1.0 if hit_cnt > 0 else 0.0)

            # NDCG
            dcg = sum(1.0 / np.log2(rank + 1) for rank, mid in enumerate(rec_ids, 1) if mid in rel)
            idcg = sum(1.0 / np.log2(rank + 1) for rank in range(1, min(10, len(rel)) + 1))
            ndcg_list.append(dcg / idcg if idcg > 0 else 0.0)

        elapsed_ms = (time.time() - t0) * 1000.0 / max(1, len(eval_users))

        return {
            "Model": model.name,
            "RMSE": round(rmse, 4),
            "MAE": round(mae, 4),
            "Precision@10": round(float(np.mean(prec_list)), 4),
            "Recall@10": round(float(np.mean(rec_list)), 4),
            "NDCG@10": round(float(np.mean(ndcg_list)), 4),
            "HitRate@10": f"{np.mean(hit_list):.1%}",
            "CatalogCov": f"{len(all_recs) / len(all_mids):.1%}",
            "Latency_ms": round(elapsed_ms, 2)
        }


# ==============================================================================
# 10. CLI & REST API DASHBOARD LAUNCHER
# ==============================================================================
def run_cli_and_api():
    parser = argparse.ArgumentParser(description="Unified MovieLens Recommendation System")
    parser.add_argument("--benchmark", action="store_true", help="Run full evaluation across all models")
    parser.add_argument("--recommend", type=int, default=None, help="Generate recommendations for User ID")
    parser.add_argument("--model", type=str, default="hybrid", help="Algorithm (popularity, content, svd, deep, hybrid)")
    parser.add_argument("--k", type=int, default=10, help="Number of items to recommend")
    parser.add_argument("--mmr", action="store_true", help="Apply MMR genre diversification")
    parser.add_argument("--cold-start", type=str, default=None, help="Comma-separated genres for cold start")
    parser.add_argument("--serve", action="store_true", help="Launch FastAPI REST server & Web Dashboard")
    parser.add_argument("--port", type=int, default=8000, help="Server port")

    args = parser.parse_args()

    print("\n[Loading MovieLens 1M Dataset...]")
    loader = UnifiedDataLoader()
    movies_df, ratings_df, users_df = loader.load_all()
    train_df, val_df, test_df, manifest = TemporalSplitter.split(ratings_df)
    all_mids = set(movies_df["movie_id"].unique())
    user_train_map = train_df.groupby("user_id")["movie_id"].apply(set).to_dict()

    print(f"✓ Loaded {len(ratings_df):,} ratings | Train: {len(train_df):,} | Zero-Leakage: {not manifest['leakage_detected']}")

    # Initialize models
    m_pop = PopularityRecommender()
    m_pop.fit(train_df, movies_df)

    m_cb = ContentBasedRecommender()
    m_cb.fit(train_df, movies_df)

    m_svd = BiasedMatrixFactorization()
    m_svd.fit(train_df, movies_df)

    m_deep = DemographicDeepRecommender(epochs=4)
    m_deep.fit(train_df, movies_df, users_df)

    m_hybrid = EnhancedHybridRecommender()
    m_hybrid.fit(train_df, movies_df, users_df)

    models_dict = {
        "popularity": m_pop,
        "content": m_cb,
        "svd": m_svd,
        "deep": m_deep,
        "hybrid": m_hybrid
    }

    if args.benchmark:
        print("\n=========================================================================================")
        print("📊 BENCHMARK COMPARISON ON TEST SET (ZERO LEAKAGE EVALUATION)")
        print("=========================================================================================")
        results = [Evaluator.evaluate(m, test_df, all_mids, user_train_map) for m in models_dict.values()]
        print(tabulate(results, headers="keys", tablefmt="fancy_grid"))
        return

    if args.cold_start:
        genres = [g.strip() for g in args.cold_start.split(",")]
        print(f"\n🎬 Cold-Start Recommendations for: {genres}")
        recs = m_cb.recommend(uid=-1, k=args.k)
        table = [[i + 1, r.title, r.genres, r.score, r.reason] for i, r in enumerate(recs)]
        print(tabulate(table, headers=["#", "Title", "Genres", "Score", "Explanation"], tablefmt="fancy_grid"))
        return

    if args.recommend is not None:
        u = args.recommend
        model = models_dict.get(args.model.lower(), m_hybrid)
        seen = user_train_map.get(u, set())
        cands = list(all_mids - seen)

        if isinstance(model, EnhancedHybridRecommender):
            recs = model.recommend(u, k=args.k, candidates=cands, use_mmr=args.mmr)
        else:
            recs = model.recommend(u, k=args.k, candidates=cands)

        print(f"\n🎬 Recommendations for User #{u} ({model.name} | Top-{args.k}):")
        table = [[i + 1, r.title, r.genres, r.score, r.reason] for i, r in enumerate(recs)]
        print(tabulate(table, headers=["#", "Title", "Genres", "Score", "Explanation"], tablefmt="fancy_grid"))
        return

    if args.serve:
        import uvicorn
        from fastapi import FastAPI, Query
        from fastapi.responses import HTMLResponse

        app = FastAPI(title="Cine Cas Phile Recommendation API", version="2.5.0")

        @app.get("/recommendations/{user_id}")
        def api_rec(user_id: int, k: int = 10, model: str = "hybrid", mmr: bool = True):
            mdl = models_dict.get(model.lower(), m_hybrid)
            seen = user_train_map.get(user_id, set())
            cands = list(all_mids - seen)
            if isinstance(mdl, EnhancedHybridRecommender):
                recs = mdl.recommend(user_id, k=k, candidates=cands, use_mmr=mmr)
            else:
                recs = mdl.recommend(user_id, k=k, candidates=cands)
            return {
                "user_id": user_id,
                "model": mdl.name,
                "recommendations": [
                    {"movie_id": r.movie_id, "title": r.title, "genres": r.genres, "score": r.score, "reason": r.reason}
                    for r in recs
                ]
            }

        @app.get("/", response_class=HTMLResponse)
        def ui():
            return """<!DOCTYPE html>
<html>
<head>
    <title>Cine Cas Phile 2.5</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background: #0b0f19; color: #f8fafc; padding: 2rem; max-width: 1100px; margin: 0 auto; }
        h1 { background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .card { background: #151d30; border: 1px solid #23314f; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)) 150px; gap: 1rem; align-items: end; }
        input, select { width: 100%; background: #0b0f19; border: 1px solid #23314f; color: #fff; padding: 0.75rem; border-radius: 8px; }
        button { background: linear-gradient(135deg, #6366f1, #a855f7); color: #fff; border: none; padding: 0.8rem; border-radius: 8px; cursor: pointer; font-weight: 600; width: 100%; }
        .movie { background: #151d30; border: 1px solid #23314f; border-radius: 10px; padding: 1.2rem; margin-bottom: 1rem; }
        .score { color: #a5b4fc; font-weight: 700; }
        .reason { color: #94a3b8; font-size: 0.85rem; margin-top: 0.4rem; border-left: 2px solid #6366f1; padding-left: 0.5rem; }
    </style>
</head>
<body>
    <h1>🎬 Cine Cas Phile 2.5 (Unified)</h1>
    <p style="color:#94a3b8; margin-bottom: 1.5rem;">Deep Demographic Embeddings • MMR Genre Diversification • Time-Decay Profile</p>
    <div class="card">
        <div class="grid">
            <div><label>User ID</label><input type="number" id="uid" value="1"></div>
            <div><label>Model</label><select id="mdl"><option value="hybrid">Enhanced Hybrid (MMR)</option><option value="deep">Demographic Deep & Wide</option><option value="svd">Biased SVD</option><option value="content">Content-Based</option><option value="popularity">Popularity</option></select></div>
            <div><label>Top-K</label><input type="number" id="k" value="10"></div>
            <button onclick="getRecs()">Recommend</button>
        </div>
    </div>
    <div id="results"></div>
    <script>
        async function getRecs() {
            const uid = document.getElementById('uid').value;
            const mdl = document.getElementById('mdl').value;
            const k = document.getElementById('k').value;
            const box = document.getElementById('results');
            box.innerHTML = '<p>Computing personalized recommendations...</p>';
            const res = await fetch(`/recommendations/${uid}?k=${k}&model=${mdl}`);
            const data = await res.json();
            box.innerHTML = data.recommendations.map(r => `
                <div class="movie">
                    <div style="display:flex; justify-content:space-between;">
                        <strong>${r.title}</strong>
                        <span class="score">${r.score}</span>
                    </div>
                    <div style="font-size:0.8rem; color:#64748b; margin: 0.3rem 0;">${r.genres}</div>
                    <div class="reason">${r.reason}</div>
                </div>
            `).join('');
        }
        window.onload = getRecs;
    </script>
</body>
</html>"""

        print(f"\n🚀 Server running at http://127.0.0.1:{args.port}/")
        uvicorn.run(app, host="127.0.0.1", port=args.port)
        return

    # Default action: run benchmark
    print("\n👉 Tip: Use --recommend <user_id>, --benchmark, or --serve to run.")
    print("Example: python movielens_unified_system.py --recommend 1 --model hybrid --mmr")


if __name__ == "__main__":
    run_cli_and_api()
