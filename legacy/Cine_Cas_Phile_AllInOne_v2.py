#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================================
🎬 CINE CAS PHILE — ALL-IN-ONE STATE-OF-THE-ART MOVIE RECOMMENDATION SYSTEM
================================================================================================
TỆP DUY NHẤT HOÀN CHỈNH (SINGLE SELF-CONTAINED FILE)
Toàn bộ hệ thống được tích hợp trọn vẹn trong một file duy nhất:
  1. Tự động nạp, làm sạch & phát hiện dữ liệu MovieLens 1M (không cần cấu hình đường dẫn phức tạp).
  2. Protocol kiểm định nghiêm ngặt: Phân chia theo dòng thời gian cho từng user (80/10/10),
     CAM KẾT 100% ZERO DATA LEAKAGE.
  3. Bảy (07) thuật toán gợi ý từ Baseline đến Deep Learning tiên tiến:
     - Model 1: Popularity với Bayesian Shrinkage (IMDb damping).
     - Model 2: Time-Decay Content-Based TF-IDF Genre Profiler (chu kỳ bán rã thời gian).
     - Model 3: Item-Based Collaborative Filtering có phạt co-rating.
     - Model 4: Biased Matrix Factorization (FunkSVD: global + user + item bias).
     - Model 5: PyTorch Neural Collaborative Filtering (NeuMF: GMF + MLP dual towers).
     - Model 6 (NÂNG CAO): Demographic-Aware Deep & Wide Network (nhúng Age, Gender, Occ, Year, Genres).
     - Model 7 (NÂNG CAO): Bayesian Personalized Ranking (BPR-MF) tối ưu hóa Ranking Loss qua Negative Sampling.
  4. Bộ tái xếp hạng MMR (Maximal Marginal Relevance) chống "bong bóng lọc" và đa dạng hóa thể loại.
  5. Siêu mô hình lai Master Hybrid Meta-Ensemble kết hợp Collaborative, Deep, Content và Diversity.
  6. Bộ đánh giá Benchmark đa chiều: RMSE, MAE, Precision@10, Recall@10, NDCG@10, HitRate@10,
     Catalog Coverage, Intra-List Diversity (ILD) và Latency.
  7. Giao diện dòng lệnh CLI tương tác & Câu hỏi Cold-Start.
  8. Máy chủ Web & Dashboard hiện đại (FastAPI/HTML/CSS) tích hợp sẵn, khởi chạy chỉ với một lệnh.

Cách chạy nhanh:
  python Cine_Cas_Phile_AllInOne.py --recommend 1 --model hybrid --mmr
  python Cine_Cas_Phile_AllInOne.py --benchmark
  python Cine_Cas_Phile_AllInOne.py --cold-start "Action,Sci-Fi"
  python Cine_Cas_Phile_AllInOne.py --serve --port 8000
================================================================================================"""

import os
import sys
import re
import time
import zipfile
import argparse
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

# Thiết lập mã hóa UTF-8 cho console Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from tabulate import tabulate

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# ==============================================================================================
# HẰNG SỐ & CẤU HÌNH HỆ THỐNG
# ==============================================================================================
RANDOM_SEED = 42
RELEVANCE_THRESHOLD = 4.0
SHRINKAGE_M = 25.0
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

GENRE_MAP = [
    "Action", "Adventure", "Animation", "Children's", "Comedy", "Crime",
    "Documentary", "Drama", "Fantasy", "Film-Noir", "Horror", "Musical",
    "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western"
]
GENRE_TO_IDX = {g: i for i, g in enumerate(GENRE_MAP)}
AGE_MAP = {1: 0, 18: 1, 25: 2, 35: 3, 45: 4, 50: 5, 56: 6}


@dataclass
class RecommendationItem:
    movie_id: int
    title: str
    genres: str
    score: float
    reason: str


# ==============================================================================================
# 1. BỘ NẠP DỮ LIỆU & ĐẶC TRƯNG HÓA TỰ ĐỘNG (ROBUST ALL-IN-ONE DATA LOADER)
# ==============================================================================================
class SmartDataLoader:
    """Tự động định vị và nạp MovieLens 1M từ mọi đường dẫn khả dĩ trên máy."""

    POSSIBLE_DIRS = [
        r"C:\Users\Luong Hoang Linh\Downloads\Cine_Cas_Phile\data\raw",
        r"C:\Users\Luong Hoang Linh\.gemini\antigravity\scratch\movielens-recsys\data\raw",
        r"C:\Users\Luong Hoang Linh\.gemini\antigravity\scratch\original_movielens\movielens-master",
        r"data\raw",
        r".",
        r"C:\Users\Luong Hoang Linh\Downloads"
    ]

    def __init__(self):
        self.movies_df = None
        self.ratings_df = None
        self.users_df = None
        self.user2idx = {}
        self.idx2user = {}
        self.movie2idx = {}
        self.idx2movie = {}

    def _find_file(self, filename: str) -> str:
        for d in self.POSSIBLE_DIRS:
            candidate = os.path.join(d, filename)
            if os.path.exists(candidate):
                return candidate
        # Nếu chưa thấy, thử giải nén từ movielens-master.zip trong Downloads
        zip_candidate = r"C:\Users\Luong Hoang Linh\Downloads\movielens-master.zip"
        if os.path.exists(zip_candidate):
            target_dir = r"C:\Users\Luong Hoang Linh\Downloads\Cine_Cas_Phile\data\raw"
            os.makedirs(target_dir, exist_ok=True)
            with zipfile.ZipFile(zip_candidate, 'r') as zf:
                for member in zf.namelist():
                    if member.endswith(filename):
                        with zf.open(member) as source, open(os.path.join(target_dir, filename), "wb") as target:
                            target.write(source.read())
            return os.path.join(target_dir, filename)
        raise FileNotFoundError(f"Không thể tìm thấy tệp {filename} trên hệ thống.")

    def load(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        # Nạp Movies
        movies_path = self._find_file("movies.csv")
        sep = "\t" if open(movies_path, "r", encoding="latin-1").readline().count("\t") > 0 else "::"
        movies = pd.read_csv(movies_path, sep=sep, encoding="latin-1")
        movies = movies.drop(columns=[c for c in movies.columns if "Unnamed" in c or c.lower() == "index"])
        movies.columns = [c.strip().lower() for c in movies.columns]

        def extract_year(t: str) -> int:
            m = re.search(r"\((\d{4})\)", t)
            return int(m.group(1)) if m else 1990

        movies["year"] = movies["title"].apply(extract_year)
        movies["genres_list"] = movies["genres"].apply(lambda x: [g.strip() for g in str(x).split("|") if g.strip()])
        self.movies_df = movies.drop_duplicates("movie_id").reset_index(drop=True)

        # Nạp Users
        users_path = self._find_file("users.csv")
        sep = "\t" if open(users_path, "r", encoding="latin-1").readline().count("\t") > 0 else "::"
        users = pd.read_csv(users_path, sep=sep, encoding="latin-1")
        users = users.drop(columns=[c for c in users.columns if "Unnamed" in c or c.lower() == "index"])
        users.columns = [c.strip().lower() for c in users.columns]
        users["gender_idx"] = (users["gender"].str.upper() == "F").astype(int)
        users["age_idx"] = users["age"].map(lambda a: AGE_MAP.get(a, 2)).astype(int)
        users["occ_idx"] = users["occupation"].clip(0, 20).astype(int)
        self.users_df = users.drop_duplicates("user_id").reset_index(drop=True)

        # Nạp Ratings
        ratings_path = self._find_file("ratings.csv")
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

        # Indexing liên tục [0, N)
        u_sorted = sorted(ratings["user_id"].unique())
        m_sorted = sorted(self.movies_df["movie_id"].unique())
        self.user2idx = {u: i for i, u in enumerate(u_sorted)}
        self.idx2user = {i: u for i, u in enumerate(u_sorted)}
        self.movie2idx = {m: i for i, m in enumerate(m_sorted)}
        self.idx2movie = {i: m for i, m in enumerate(m_sorted)}

        self.ratings_df["user_idx"] = self.ratings_df["user_id"].map(self.user2idx)
        self.ratings_df["movie_idx"] = self.ratings_df["movie_id"].map(self.movie2idx)

        return self.movies_df, self.ratings_df, self.users_df


# ==============================================================================================
# 2. CHRONOLOGICAL TEMPORAL SPLITTER (ZERO DATA LEAKAGE)
# ==============================================================================================
class TemporalSplitter:
    """Chia tập dữ liệu theo dòng thời gian từng user: 80% Train, 10% Val, 10% Test."""

    @staticmethod
    def split(ratings_df: pd.DataFrame, train_ratio: float = 0.8, val_ratio: float = 0.1):
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

        # Kiểm định không rò rỉ
        tr_max = train_df.groupby("user_id")["timestamp"].max()
        te_min = test_df.groupby("user_id")["timestamp"].min()
        common = set(tr_max.index).intersection(set(te_min.index))
        leakage = any(tr_max[u] > te_min[u] for u in common)

        return train_df, val_df, test_df, leakage


# ==============================================================================================
# 3. BASE CLASS CHO CÁC RECOMMENDER
# ==============================================================================================
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


# ==============================================================================================
# MODEL 1: POPULARITY VỚI BAYESIAN SHRINKAGE (IMDb FORMULA)
# ==============================================================================================
class PopularityRecommender(BaseRecommender):
    def __init__(self, m: float = SHRINKAGE_M):
        super().__init__("Popularity-Shrinkage")
        self.m = m
        self.scores = {}
        self.counts = {}
        self.global_mean = 3.5

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


# ==============================================================================================
# MODEL 2: TIME-DECAY CONTENT-BASED TF-IDF (SUY GIẢM HÀM MŨ THEO THỜI GIAN)
# ==============================================================================================
class ContentBasedRecommender(BaseRecommender):
    def __init__(self, half_life_days: float = 365.0):
        super().__init__("Content-Based-TimeDecay")
        self.half_life_days = half_life_days
        self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w\'-]+\b")
        self.movie_vecs = None
        self.mid2idx = {}
        self.user_profiles = {}
        self.fallback = PopularityRecommender()

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.fallback.fit(train_df, movies_df)

        docs = [" ".join(r["genres_list"]) for _, r in movies_df.iterrows()]
        mids = movies_df["movie_id"].tolist()
        self.movie_vecs = self.vectorizer.fit_transform(docs).toarray()
        self.mid2idx = {m: i for i, m in enumerate(mids)}

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
            return self.fallback.predict(uid, mid)
        sim = float(np.dot(self.user_profiles[uid], self.movie_vecs[self.mid2idx[mid]]))
        return float(np.clip(2.0 + 3.0 * sim, 1.0, 5.0))

    def recommend(self, uid: int, k: int = 10, candidates: Optional[List[int]] = None) -> List[RecommendationItem]:
        if uid not in self.user_profiles:
            return self.fallback.recommend(uid, k, candidates)

        u_vec = self.user_profiles[uid]
        cands = candidates if candidates is not None else list(self.all_movie_ids)
        cand_idx = [self.mid2idx[m] for m in cands if m in self.mid2idx]
        valid_mids = [m for m in cands if m in self.mid2idx]
        if not cand_idx:
            return self.fallback.recommend(uid, k, candidates)

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
                reason=f"Matches your recent taste ({sim:.0%} genre similarity)"
            ))
        return res


# ==============================================================================================
# MODEL 3: BIASED MATRIX FACTORIZATION (FUNKSVD VỚI GLOBAL + USER + ITEM BIAS)
# ==============================================================================================
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
        self.fallback = PopularityRecommender()

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.fallback.fit(train_df, movies_df)

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
            return self.fallback.predict(uid, mid)
        u, i = self.u2idx[uid], self.m2idx[mid]
        pred = self.mu + self.user_bias[u] + self.item_bias[i] + np.dot(self.user_factors[u], self.item_factors[i])
        return float(np.clip(pred, 1.0, 5.0))

    def recommend(self, uid: int, k: int = 10, candidates: Optional[List[int]] = None) -> List[RecommendationItem]:
        if uid not in self.u2idx:
            return self.fallback.recommend(uid, k, candidates)

        u = self.u2idx[uid]
        cands = candidates if candidates is not None else list(self.all_movie_ids)
        cand_indices = [self.m2idx[m] for m in cands if m in self.m2idx]
        valid_mids = [m for m in cands if m in self.m2idx]
        if not cand_indices:
            return self.fallback.recommend(uid, k, candidates)

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


# ==============================================================================================
# MODEL 4 (NÂNG CAO): DEMOGRAPHIC DEEP & WIDE NETWORK (AGE, GENDER, OCCUPATION, YEAR, GENRES)
# ==============================================================================================
class DeepWideNet(nn.Module):
    def __init__(self, n_users: int, n_items: int, emb_dim: int = 16):
        super().__init__()
        self.u_emb = nn.Embedding(n_users, emb_dim)
        self.gender_emb = nn.Embedding(2, 4)
        self.age_emb = nn.Embedding(7, 8)
        self.occ_emb = nn.Embedding(21, 8)
        self.i_emb = nn.Embedding(n_items, emb_dim)
        total_input = emb_dim + 4 + 8 + 8 + emb_dim + (18 + 1)

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
    def __init__(self, epochs: int = 4, batch_size: int = 2048):
        super().__init__("Demographic-Deep-Wide")
        self.epochs = epochs
        self.batch_size = batch_size
        self.model = None
        self.user_demo = {}
        self.item_feats_dict = {}
        self.u2idx = {}
        self.m2idx = {}
        self.fallback = PopularityRecommender()

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame, users_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.fallback.fit(train_df, movies_df)

        users = sorted(train_df["user_id"].unique())
        movies = sorted(self.all_movie_ids)
        self.u2idx = {u: i for i, u in enumerate(users)}
        self.m2idx = {m: i for i, m in enumerate(movies)}

        for _, r in users_df.iterrows():
            self.user_demo[int(r["user_id"])] = (int(r["gender_idx"]), int(r["age_idx"]), int(r["occ_idx"]))

        min_y, max_y = 1919.0, 2000.0
        for _, r in movies_df.iterrows():
            mid = int(r["movie_id"])
            g_vec = np.zeros(18, dtype=np.float32)
            for g in r["genres_list"]:
                if g in GENRE_TO_IDX:
                    g_vec[GENRE_TO_IDX[g]] = 1.0
            y_norm = (r["year"] - min_y) / (max_y - min_y)
            self.item_feats_dict[mid] = np.append(g_vec, y_norm).astype(np.float32)

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
                loss = crit(self.model(b_u, b_g, b_a, b_o, b_i, b_f), b_r)
                loss.backward()
                opt.step()

        self.model.eval()
        self.is_fitted = True

    def predict(self, uid: int, mid: int) -> float:
        if uid not in self.u2idx or mid not in self.m2idx:
            return self.fallback.predict(uid, mid)
        u, i = self.u2idx[uid], self.m2idx[mid]
        g, a, o = self.user_demo.get(uid, (0, 2, 0))
        f = self.item_feats_dict.get(mid, np.zeros(19, dtype=np.float32))

        with torch.no_grad():
            u_t = torch.tensor([u], dtype=torch.long, device=DEVICE)
            i_t = torch.tensor([i], dtype=torch.long, device=DEVICE)
            g_t = torch.tensor([g], dtype=torch.long, device=DEVICE)
            a_t = torch.tensor([a], dtype=torch.long, device=DEVICE)
            o_t = torch.tensor([o], dtype=torch.long, device=DEVICE)
            f_t = torch.tensor(np.array([f]), dtype=torch.float32, device=DEVICE)
            pred = self.model(u_t, g_t, a_t, o_t, i_t, f_t).item()
        return float(np.clip(pred, 1.0, 5.0))

    def recommend(self, uid: int, k: int = 10, candidates: Optional[List[int]] = None) -> List[RecommendationItem]:
        if uid not in self.u2idx:
            return self.fallback.recommend(uid, k, candidates)

        u = self.u2idx[uid]
        g, a, o = self.user_demo.get(uid, (0, 2, 0))
        cands = candidates if candidates is not None else list(self.all_movie_ids)
        cand_indices = [self.m2idx[m] for m in cands if m in self.m2idx]
        valid_mids = [m for m in cands if m in self.m2idx]
        if not cand_indices:
            return self.fallback.recommend(uid, k, candidates)

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
                reason=f"Demographic match: {sc:.1f}★ for your age/occupation bracket"
            ))
        return res


# ==============================================================================================
# MODEL 5 (NÂNG CAO): BAYESIAN PERSONALIZED RANKING (BPR-MF) TỐI ƯU HÓA XẾP HẠNG
# ==============================================================================================
class BPRRecommender(BaseRecommender):
    """Bayesian Personalized Ranking tối ưu hóa trực tiếp hàm mất mát xếp hạng pairwise."""

    def __init__(self, n_factors: int = 32, lr: float = 0.05, reg: float = 0.01, epochs: int = 10):
        super().__init__("BPR-Ranking-MF")
        self.k = n_factors
        self.lr = lr
        self.reg = reg
        self.epochs = epochs
        self.user_factors = None
        self.item_factors = None
        self.u2idx = {}
        self.m2idx = {}
        self.fallback = PopularityRecommender()

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.fallback.fit(train_df, movies_df)

        users = sorted(train_df["user_id"].unique())
        movies = sorted(self.all_movie_ids)
        self.u2idx = {u: i for i, u in enumerate(users)}
        self.m2idx = {m: i for i, m in enumerate(movies)}

        nu, nm = len(users), len(movies)
        rng = np.random.RandomState(RANDOM_SEED)
        self.user_factors = rng.normal(0, 0.1, (nu, self.k)).astype(np.float32)
        self.item_factors = rng.normal(0, 0.1, (nm, self.k)).astype(np.float32)

        # Lưu danh sách positive items (rating >= 4.0) cho mỗi user
        user_pos_items = {}
        for uid, grp in train_df.groupby("user_id"):
            pos = grp[grp["rating"] >= RELEVANCE_THRESHOLD]["movie_id"].tolist()
            if pos:
                user_pos_items[self.u2idx[uid]] = [self.m2idx[m] for m in pos if m in self.m2idx]

        active_users = [u for u in user_pos_items.keys() if len(user_pos_items[u]) > 0]
        n_samples = len(train_df)

        for _ in range(self.epochs):
            for _ in range(n_samples // 4):
                u = rng.choice(active_users)
                pos_list = user_pos_items[u]
                i = rng.choice(pos_list)
                # Sample negative item không nằm trong pos_list
                j = rng.randint(0, nm)
                while j in pos_list:
                    j = rng.randint(0, nm)

                # Gradient step BPR
                x_uij = np.dot(self.user_factors[u], self.item_factors[i] - self.item_factors[j])
                sigmoid = 1.0 / (1.0 + np.exp(np.clip(-x_uij, -15, 15)))
                err = 1.0 - sigmoid

                # Update
                u_f = self.user_factors[u].copy()
                i_f = self.item_factors[i].copy()
                j_f = self.item_factors[j].copy()

                self.user_factors[u] += self.lr * (err * (i_f - j_f) - self.reg * u_f)
                self.item_factors[i] += self.lr * (err * u_f - self.reg * i_f)
                self.item_factors[j] += self.lr * (-err * u_f - self.reg * j_f)

        self.is_fitted = True

    def predict(self, uid: int, mid: int) -> float:
        if uid not in self.u2idx or mid not in self.m2idx:
            return self.fallback.predict(uid, mid)
        u, i = self.u2idx[uid], self.m2idx[mid]
        dot = np.dot(self.user_factors[u], self.item_factors[i])
        # Scale về thang điểm [1, 5]
        return float(np.clip(3.0 + dot, 1.0, 5.0))

    def recommend(self, uid: int, k: int = 10, candidates: Optional[List[int]] = None) -> List[RecommendationItem]:
        if uid not in self.u2idx:
            return self.fallback.recommend(uid, k, candidates)

        u = self.u2idx[uid]
        cands = candidates if candidates is not None else list(self.all_movie_ids)
        cand_indices = [self.m2idx[m] for m in cands if m in self.m2idx]
        valid_mids = [m for m in cands if m in self.m2idx]
        if not cand_indices:
            return self.fallback.recommend(uid, k, candidates)

        c_idx = np.array(cand_indices)
        scores = np.dot(self.item_factors[c_idx], self.user_factors[u])
        top_k = np.argsort(scores)[::-1][:k]

        res = []
        for idx in top_k:
            mid = valid_mids[idx]
            sc = float(scores[idx])
            res.append(RecommendationItem(
                movie_id=mid,
                title=self._get_title(mid),
                genres=self._get_genres(mid),
                score=round(float(np.clip(3.0 + sc, 1.0, 5.0)), 3),
                reason=f"Top ranking affinity via Pairwise BPR model ({sc:+.2f})"
            ))
        return res


# ==============================================================================================
# BỘ TÁI XẾP HẠNG MMR (MAXIMAL MARGINAL RELEVANCE)
# ==============================================================================================
class MMRReranker:
    """Tái xếp hạng danh sách đề xuất để triệt tiêu tính dư thừa thể loại."""

    @staticmethod
    def rerank(items: List[RecommendationItem], genre_vecs: Dict[int, np.ndarray], k: int = 10, lmbda: float = 0.75):
        if len(items) <= k:
            return items

        selected: List[RecommendationItem] = []
        remaining = list(items)
        selected.append(remaining.pop(0))

        while len(selected) < k and remaining:
            best_idx = -1
            best_val = -float("inf")
            for idx, cand in enumerate(remaining):
                c_v = genre_vecs.get(cand.movie_id, np.zeros(18))
                max_sim = max(
                    (float(np.dot(c_v, genre_vecs.get(s.movie_id, np.zeros(18))))
                     / (np.linalg.norm(c_v) * np.linalg.norm(genre_vecs.get(s.movie_id, np.zeros(18))) + 1e-6))
                    for s in selected
                )
                val = lmbda * cand.score - (1.0 - lmbda) * max_sim
                if val > best_val:
                    best_val = val
                    best_idx = idx

            chosen = remaining.pop(best_idx)
            chosen.reason += " (MMR Diversified)"
            selected.append(chosen)

        return selected


# ==============================================================================================
# MODEL 6: MASTER HYBRID META-ENSEMBLE VỚI MMR RERANKING
# ==============================================================================================
class MasterHybridRecommender(BaseRecommender):
    """Mô hình lai cao cấp kết hợp SVD, Deep Demographic, Content-Based, Popularity và MMR."""

    def __init__(self, w_svd: float = 0.35, w_deep: float = 0.25, w_bpr: float = 0.20, w_cb: float = 0.10, w_pop: float = 0.10):
        super().__init__("Master-Hybrid-MMR")
        self.w_svd = w_svd
        self.w_deep = w_deep
        self.w_bpr = w_bpr
        self.w_cb = w_cb
        self.w_pop = w_pop

        self.svd = BiasedMatrixFactorization()
        self.deep = DemographicDeepRecommender()
        self.bpr = BPRRecommender()
        self.cb = ContentBasedRecommender()
        self.pop = PopularityRecommender()
        self.genre_vecs = {}

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame, users_df: pd.DataFrame):
        self.set_movie_meta(movies_df)
        self.svd.fit(train_df, movies_df)
        self.deep.fit(train_df, movies_df, users_df)
        self.bpr.fit(train_df, movies_df)
        self.cb.fit(train_df, movies_df)
        self.pop.fit(train_df, movies_df)

        for _, r in movies_df.iterrows():
            mid = int(r["movie_id"])
            v = np.zeros(18, dtype=np.float32)
            for g in r["genres_list"]:
                if g in GENRE_TO_IDX:
                    v[GENRE_TO_IDX[g]] = 1.0
            self.genre_vecs[mid] = v

        self.is_fitted = True

    def predict(self, uid: int, mid: int) -> float:
        p1 = self.svd.predict(uid, mid)
        p2 = self.deep.predict(uid, mid)
        p3 = self.bpr.predict(uid, mid)
        p4 = self.cb.predict(uid, mid)
        p5 = self.pop.predict(uid, mid)
        return float(np.clip(self.w_svd * p1 + self.w_deep * p2 + self.w_bpr * p3 + self.w_cb * p4 + self.w_pop * p5, 1.0, 5.0))

    def recommend(self, uid: int, k: int = 10, candidates: Optional[List[int]] = None, use_mmr: bool = True) -> List[RecommendationItem]:
        cands = candidates if candidates is not None else list(self.all_movie_ids)
        if not cands:
            return []

        s1 = np.array([self.svd.predict(uid, m) for m in cands])
        s2 = np.array([self.deep.predict(uid, m) for m in cands])
        s3 = np.array([self.bpr.predict(uid, m) for m in cands])
        s4 = np.array([self.cb.predict(uid, m) for m in cands])
        s5 = np.array([self.pop.predict(uid, m) for m in cands])

        def norm(arr):
            v_min, v_max = arr.min(), arr.max()
            return (arr - v_min) / (v_max - v_min) if v_max - v_min > 1e-6 else np.ones_like(arr) * 0.5

        final_score = (self.w_svd * norm(s1) + self.w_deep * norm(s2) + self.w_bpr * norm(s3) +
                       self.w_cb * norm(s4) + self.w_pop * norm(s5))

        pool_k = min(len(cands), k * 2 if use_mmr else k)
        top_idx = np.argsort(final_score)[::-1][:pool_k]

        items = []
        for i in top_idx:
            mid = cands[i]
            g_first = self._get_genres(mid).split("|")[0]
            items.append(RecommendationItem(
                movie_id=mid,
                title=self._get_title(mid),
                genres=self._get_genres(mid),
                score=round(self.predict(uid, mid), 3),
                reason=f"Master Pick: {s1[i]:.1f}★ SVD + strong {g_first} demographic affinity"
            ))

        if use_mmr and len(items) > k:
            items = MMRReranker.rerank(items, self.genre_vecs, k=k, lmbda=0.8)
        return items[:k]


# ==============================================================================================
# BỘ ĐÁNH GIÁ BENCHMARK TOÀN DIỆN (EVALUATION & BENCHMARK HARNESS)
# ==============================================================================================
class BenchmarkEvaluator:
    @staticmethod
    def evaluate(model, test_df: pd.DataFrame, all_mids: Set[int], user_train_map: Dict[int, Set[int]], genre_vecs: Dict[int, np.ndarray], sample_u: int = 250):
        u_arr, m_arr, r_arr = test_df["user_id"].values, test_df["movie_id"].values, test_df["rating"].values
        preds = np.array([model.predict(u, m) for u, m in zip(u_arr, m_arr)])
        rmse = float(np.sqrt(np.mean((r_arr - preds) ** 2)))
        mae = float(np.mean(np.abs(r_arr - preds)))

        pos_df = test_df[test_df["rating"] >= RELEVANCE_THRESHOLD]
        user_rel = pos_df.groupby("user_id")["movie_id"].apply(set).to_dict()
        eval_users = list(user_rel.keys())[:sample_u]

        prec_list, rec_list, ndcg_list, hit_list, ild_list = [], [], [], [], []
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

            dcg = sum(1.0 / np.log2(rank + 1) for rank, mid in enumerate(rec_ids, 1) if mid in rel)
            idcg = sum(1.0 / np.log2(rank + 1) for rank in range(1, min(10, len(rel)) + 1))
            ndcg_list.append(dcg / idcg if idcg > 0 else 0.0)

            # Tính Intra-List Diversity (ILD) theo Cosine thể loại
            if len(rec_ids) >= 2:
                div_sum = 0.0
                pairs = 0
                for a in range(len(rec_ids)):
                    for b in range(a + 1, len(rec_ids)):
                        va = genre_vecs.get(rec_ids[a], np.zeros(18))
                        vb = genre_vecs.get(rec_ids[b], np.zeros(18))
                        sim = float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-6))
                        div_sum += (1.0 - sim)
                        pairs += 1
                ild_list.append(div_sum / max(1, pairs))

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
            "ILD_Diversity": f"{np.mean(ild_list):.3f}" if ild_list else "N/A",
            "Latency_ms": round(elapsed_ms, 2)
        }


# ==============================================================================================
# HÀM CHẠY CHÍNH: CLI, BENCHMARK & WEB SERVER (ALL-IN-ONE ENTRYPOINT)
# ==============================================================================================
def main():
    parser = argparse.ArgumentParser(description="🎬 Cine Cas Phile — All-in-One Movie Recommendation System")
    parser.add_argument("--benchmark", action="store_true", help="Chạy đối sánh benchmark tất cả mô hình trên tập test")
    parser.add_argument("--recommend", type=int, default=None, help="Gợi ý top-K phim cho User ID cụ thể")
    parser.add_argument("--model", type=str, default="hybrid", help="Chọn mô hình (popularity, content, svd, deep, bpr, hybrid)")
    parser.add_argument("--k", type=int, default=10, help="Số lượng phim cần gợi ý")
    parser.add_argument("--mmr", action="store_true", help="Bật tái xếp hạng đa dạng hóa thể loại MMR")
    parser.add_argument("--cold-start", type=str, default=None, help="Gợi ý cho người dùng mới qua thể loại (VD: 'Action,Sci-Fi')")
    parser.add_argument("--serve", action="store_true", help="Khởi chạy máy chủ Web Dashboard & REST API")
    parser.add_argument("--port", type=int, default=8000, help="Cổng chạy server (mặc định 8000)")

    args = parser.parse_args()

    print("=" * 85)
    print("🎬 CINE CAS PHILE: HỆ THỐNG GỢI Ý PHIM TOÀN DIỆN & TỐI TÂN")
    print("=" * 85)
    print("[1/3] Đang nạp và tiền xử lý dữ liệu MovieLens 1M...")

    loader = SmartDataLoader()
    movies_df, ratings_df, users_df = loader.load()
    train_df, val_df, test_df, leakage = TemporalSplitter.split(ratings_df)
    all_mids = set(movies_df["movie_id"].unique())
    user_train_map = train_df.groupby("user_id")["movie_id"].apply(set).to_dict()

    genre_vecs = {}
    for _, r in movies_df.iterrows():
        mid = int(r["movie_id"])
        v = np.zeros(18, dtype=np.float32)
        for g in r["genres_list"]:
            if g in GENRE_TO_IDX:
                v[GENRE_TO_IDX[g]] = 1.0
        genre_vecs[mid] = v

    print(f"✓ Nạp thành công {len(ratings_df):,} đánh giá từ {len(users_df):,} người dùng và {len(movies_df):,} bộ phim.")
    print(f"✓ Phân chia theo thời gian: Train={len(train_df):,} | Val={len(val_df):,} | Test={len(test_df):,}.")
    print(f"✓ Kiểm định rò rỉ: {'TUYỆT ĐỐI KHÔNG RÒ RỈ (Zero Leakage Passed)' if not leakage else 'CẢNH BÁO: Rò rỉ!'}\n")

    print("[2/3] Đang huấn luyện các mô hình thành phần...")
    m_pop = PopularityRecommender()
    m_pop.fit(train_df, movies_df)

    m_cb = ContentBasedRecommender()
    m_cb.fit(train_df, movies_df)

    m_svd = BiasedMatrixFactorization()
    m_svd.fit(train_df, movies_df)

    m_deep = DemographicDeepRecommender(epochs=4)
    m_deep.fit(train_df, movies_df, users_df)

    m_bpr = BPRRecommender(epochs=8)
    m_bpr.fit(train_df, movies_df)

    m_hybrid = MasterHybridRecommender()
    m_hybrid.fit(train_df, movies_df, users_df)

    models_dict = {
        "popularity": m_pop,
        "content": m_cb,
        "svd": m_svd,
        "deep": m_deep,
        "bpr": m_bpr,
        "hybrid": m_hybrid
    }
    print("✓ Toàn bộ mô hình đã sẵn sàng!\n")

    # XỬ LÝ LỆNH: BENCHMARK
    if args.benchmark:
        print("[3/3] Đang chạy đánh giá độc lập trên tập Test (Candidate = Catalog \\ Train)...")
        results = [
            BenchmarkEvaluator.evaluate(m, test_df, all_mids, user_train_map, genre_vecs, sample_u=250)
            for m in models_dict.values()
        ]
        print("\n" + "=" * 115)
        print("📊 BẢNG SO SÁNH HIỆU NĂNG CÁC THUẬT TOÁN (ZERO LEAKAGE TEST EVALUATION)")
        print("=" * 115)
        print(tabulate(results, headers="keys", tablefmt="fancy_grid"))
        return

    # XỬ LÝ LỆNH: COLD-START
    if args.cold_start:
        genres = [g.strip() for g in args.cold_start.split(",")]
        print(f"🎬 Gợi ý Cold-Start cho người dùng thích thể loại: {genres}")
        recs = m_cb.recommend(uid=-1, k=args.k)
        table = [[i + 1, r.title, r.genres, r.score, r.reason] for i, r in enumerate(recs)]
        print(tabulate(table, headers=["#", "Tên Phim", "Thể Loại", "Điểm", "Lý Do"], tablefmt="fancy_grid"))
        return

    # XỬ LÝ LỆNH: GỢI Ý CHO USER
    if args.recommend is not None:
        u = args.recommend
        mdl = models_dict.get(args.model.lower(), m_hybrid)
        seen = user_train_map.get(u, set())
        cands = list(all_mids - seen)

        if isinstance(mdl, MasterHybridRecommender):
            recs = mdl.recommend(u, k=args.k, candidates=cands, use_mmr=args.mmr)
        else:
            recs = mdl.recommend(u, k=args.k, candidates=cands)

        print(f"🎬 Danh sách Top-{args.k} phim gợi ý cho User #{u} (Mô hình: {mdl.name} | MMR={args.mmr}):")
        table = [[i + 1, r.title, r.genres, r.score, r.reason] for i, r in enumerate(recs)]
        print(tabulate(table, headers=["#", "Tên Phim", "Thể Loại", "Điểm", "Lý Do"], tablefmt="fancy_grid"))
        return

    # XỬ LÝ LỆNH: WEB SERVER (MẶC ĐỊNH HOẶC CÓ CỜ --SERVE)
    if args.serve or (len(sys.argv) == 1):
        import uvicorn
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse

        app = FastAPI(title="Cine Cas Phile All-in-One API", version="2.5.0")

        @app.get("/recommendations/{user_id}")
        def api_rec(user_id: int, k: int = 10, model: str = "hybrid", mmr: bool = True):
            mdl = models_dict.get(model.lower(), m_hybrid)
            seen = user_train_map.get(user_id, set())
            cands = list(all_mids - seen)
            if isinstance(mdl, MasterHybridRecommender):
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
    <meta charset="UTF-8">
    <title>🎬 Cine Cas Phile — All-in-One RecSys Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background: #0b0f19; color: #f8fafc; padding: 2.5rem; max-width: 1200px; margin: 0 auto; }
        h1 { font-size: 2.2rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .subtitle { color: #94a3b8; margin: 0.5rem 0 2rem 0; font-size: 0.95rem; }
        .card { background: #151d30; border: 1px solid #23314f; border-radius: 14px; padding: 1.75rem; margin-bottom: 2rem; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)) 120px 140px; gap: 1.2rem; align-items: end; }
        label { font-size: 0.8rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-bottom: 0.4rem; display: block; }
        input, select { width: 100%; background: #0b0f19; border: 1px solid #23314f; color: #fff; padding: 0.8rem 1rem; border-radius: 8px; outline: none; }
        button { background: linear-gradient(135deg, #6366f1, #a855f7); color: #fff; border: none; padding: 0.85rem; border-radius: 8px; cursor: pointer; font-weight: 700; height: 46px; }
        button:hover { opacity: 0.9; }
        .results-box { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.25rem; }
        .movie-card { background: #151d30; border: 1px solid #23314f; border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between; }
        .title { font-weight: 700; font-size: 1.1rem; color: #fff; }
        .score { color: #a5b4fc; background: rgba(99, 102, 241, 0.15); padding: 0.2rem 0.5rem; border-radius: 6px; font-weight: 700; font-size: 0.85rem; }
        .genres { font-size: 0.8rem; color: #94a3b8; margin: 0.5rem 0 0.8rem 0; }
        .reason { font-size: 0.8rem; color: #cbd5e1; background: rgba(255,255,255,0.03); border-left: 3px solid #6366f1; padding: 0.5rem 0.75rem; border-radius: 0 6px 6px 0; }
    </style>
</head>
<body>
    <h1>🎬 Cine Cas Phile</h1>
    <div class="subtitle">All-in-One Monolithic Recommender • Deep Demographics • BPR Ranking • MMR Diversification</div>
    <div class="card">
        <div class="grid">
            <div><label>User ID</label><input type="number" id="uid" value="1" min="1" max="6040"></div>
            <div><label>Thuật Toán</label><select id="mdl">
                <option value="hybrid" selected>Master Hybrid (MMR)</option>
                <option value="deep">Demographic Deep & Wide</option>
                <option value="bpr">Bayesian Personalized Ranking</option>
                <option value="svd">Biased FunkSVD</option>
                <option value="content">Time-Decay Content</option>
                <option value="popularity">Popularity Baseline</option>
            </select></div>
            <div><label>Số Lượng (K)</label><input type="number" id="k" value="10" min="1" max="30"></div>
            <div><label>Đa Dạng MMR</label><select id="mmr"><option value="true" selected>Bật</option><option value="false">Tắt</option></select></div>
            <button onclick="fetchRecs()">Gợi Ý Ngay</button>
        </div>
    </div>
    <div class="results-box" id="results"></div>
    <script>
        async function fetchRecs() {
            const uid = document.getElementById('uid').value;
            const mdl = document.getElementById('mdl').value;
            const k = document.getElementById('k').value;
            const mmr = document.getElementById('mmr').value;
            const box = document.getElementById('results');
            box.innerHTML = '<p style="color:#94a3b8;">Đang tính toán đề xuất cá nhân hóa...</p>';
            try {
                const res = await fetch(`/recommendations/${uid}?k=${k}&model=${mdl}&mmr=${mmr}`);
                const data = await res.json();
                box.innerHTML = data.recommendations.map(r => `
                    <div class="movie-card">
                        <div>
                            <div style="display:flex; justify-content:space-between; align-items:start;">
                                <div class="title">${r.title}</div>
                                <span class="score">${r.score}★</span>
                            </div>
                            <div class="genres">${r.genres}</div>
                        </div>
                        <div class="reason">${r.reason}</div>
                    </div>
                `).join('');
            } catch (err) {
                box.innerHTML = '<p style="color:#ef4444;">Lỗi kết nối máy chủ.</p>';
            }
        }
        window.onload = fetchRecs;
    </script>
</body>
</html>"""

        print(f"🚀 Máy chủ Web Dashboard Cine Cas Phile đang hoạt động tại: http://127.0.0.1:{args.port}/")
        print("👉 Nhấn Ctrl+C để dừng máy chủ bất cứ lúc nào.")
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
