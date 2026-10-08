"""PyTorch Neural Collaborative Filtering (NeuMF) combining GMF and MLP."""

import time
import os
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from src.data.dataset import RatingDataset
from src.recommenders.base import BaseRecommender, RecommendationItem
from src.recommenders.popularity import PopularityRecommender


class NeuMFNet(nn.Module):
    """Neural Matrix Factorization architecture."""

    def __init__(
        self,
        n_users: int,
        n_items: int,
        latent_dim_gmf: int = 32,
        latent_dim_mlp: int = 32,
        mlp_layers: List[int] = [64, 32, 16],
        dropout: float = 0.1,
    ):
        super().__init__()
        # GMF embeddings
        self.user_embed_gmf = nn.Embedding(n_users, latent_dim_gmf)
        self.item_embed_gmf = nn.Embedding(n_items, latent_dim_gmf)

        # MLP embeddings
        self.user_embed_mlp = nn.Embedding(n_users, latent_dim_mlp)
        self.item_embed_mlp = nn.Embedding(n_items, latent_dim_mlp)

        # MLP layers
        mlp_modules = []
        input_size = latent_dim_mlp * 2
        for hidden_size in mlp_layers:
            mlp_modules.append(nn.Linear(input_size, hidden_size))
            mlp_modules.append(nn.BatchNorm1d(hidden_size))
            mlp_modules.append(nn.ReLU())
            mlp_modules.append(nn.Dropout(dropout))
            input_size = hidden_size
        self.mlp = nn.Sequential(*mlp_modules)

        # Final prediction layer
        final_input_size = latent_dim_gmf + mlp_layers[-1]
        self.predict_layer = nn.Linear(final_input_size, 1)

        # Weight initialization
        self._init_weights()

    def _init_weights(self):
        nn.init.normal_(self.user_embed_gmf.weight, std=0.01)
        nn.init.normal_(self.item_embed_gmf.weight, std=0.01)
        nn.init.normal_(self.user_embed_mlp.weight, std=0.01)
        nn.init.normal_(self.item_embed_mlp.weight, std=0.01)

        for m in self.mlp:
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)
        nn.init.kaiming_uniform_(self.predict_layer.weight, a=1, nonlinearity="sigmoid")

    def forward(self, user_indices: torch.Tensor, item_indices: torch.Tensor) -> torch.Tensor:
        # GMF branch
        u_gmf = self.user_embed_gmf(user_indices)
        i_gmf = self.item_embed_gmf(item_indices)
        phi_gmf = u_gmf * i_gmf

        # MLP branch
        u_mlp = self.user_embed_mlp(user_indices)
        i_mlp = self.item_embed_mlp(item_indices)
        phi_mlp = torch.cat([u_mlp, i_mlp], dim=-1)
        phi_mlp = self.mlp(phi_mlp)

        # Fusion
        fusion = torch.cat([phi_gmf, phi_mlp], dim=-1)
        output = self.predict_layer(fusion)
        # Scale through sigmoid to [1, 5]
        rating = torch.sigmoid(output).squeeze(-1) * 4.0 + 1.0
        return rating


class NeuralMFRecommender(BaseRecommender):
    """Wrapper for PyTorch NeuMF with early stopping and training lifecycle."""

    def __init__(
        self,
        latent_dim_gmf: int = 32,
        latent_dim_mlp: int = 32,
        mlp_layers: List[int] = [64, 32, 16],
        dropout: float = 0.1,
        lr: float = 0.001,
        batch_size: int = 1024,
        epochs: int = 8,
        device: str = "cpu",
        checkpoint_path: str = "artifacts/neural_mf.pt",
    ):
        super().__init__(name="Neural-MF-PyTorch")
        self.latent_dim_gmf = latent_dim_gmf
        self.latent_dim_mlp = latent_dim_mlp
        self.mlp_layers = mlp_layers
        self.dropout = dropout
        self.lr = lr
        self.batch_size = batch_size
        self.epochs = epochs
        self.device = torch.device(device)
        self.checkpoint_path = checkpoint_path

        self.model: Optional[NeuMFNet] = None
        self.user2idx: Dict[int, int] = {}
        self.movie2idx: Dict[int, int] = {}
        self.idx2movie: Dict[int, int] = {}
        self.training_time_sec: float = 0.0
        self.fallback_pop: Optional[PopularityRecommender] = None

    def fit(
        self,
        train_df: pd.DataFrame,
        movies_df: pd.DataFrame,
        val_df: Optional[pd.DataFrame] = None,
    ):
        start_time = time.time()
        self.set_movie_meta(movies_df)

        self.fallback_pop = PopularityRecommender()
        self.fallback_pop.fit(train_df, movies_df)

        unique_users = sorted(train_df["user_id"].unique())
        unique_movies = sorted(self.all_movie_ids)

        self.user2idx = {u: idx for idx, u in enumerate(unique_users)}
        self.movie2idx = {m: idx for idx, m in enumerate(unique_movies)}
        self.idx2movie = {idx: m for idx, m in enumerate(unique_movies)}

        n_users = len(unique_users)
        n_items = len(unique_movies)

        self.model = NeuMFNet(
            n_users=n_users,
            n_items=n_items,
            latent_dim_gmf=self.latent_dim_gmf,
            latent_dim_mlp=self.latent_dim_mlp,
            mlp_layers=self.mlp_layers,
            dropout=self.dropout,
        ).to(self.device)

        train_dataset = RatingDataset(
            user_indices=train_df["user_id"].map(self.user2idx).values,
            movie_indices=train_df["movie_id"].map(self.movie2idx).values,
            ratings=train_df["rating"].values,
        )
        train_loader = DataLoader(
            train_dataset, batch_size=self.batch_size, shuffle=True
        )

        val_loader = None
        if val_df is not None:
            # Filter known users/items
            valid_val = val_df[
                val_df["user_id"].isin(self.user2idx)
                & val_df["movie_id"].isin(self.movie2idx)
            ]
            if len(valid_val) > 0:
                val_dataset = RatingDataset(
                    user_indices=valid_val["user_id"].map(self.user2idx).values,
                    movie_indices=valid_val["movie_id"].map(self.movie2idx).values,
                    ratings=valid_val["rating"].values,
                )
                val_loader = DataLoader(
                    val_dataset, batch_size=self.batch_size, shuffle=False
                )

        criterion = nn.MSELoss()
        optimizer = torch.optim.AdamW(
            self.model.parameters(), lr=self.lr, weight_decay=1e-4
        )

        best_val_loss = float("inf")
        patience = 3
        patience_counter = 0

        self.model.train()
        for epoch in range(self.epochs):
            total_train_loss = 0.0
            for batch_users, batch_items, batch_ratings in train_loader:
                batch_users = batch_users.to(self.device)
                batch_items = batch_items.to(self.device)
                batch_ratings = batch_ratings.to(self.device)

                optimizer.zero_grad()
                preds = self.model(batch_users, batch_items)
                loss = criterion(preds, batch_ratings)
                loss.backward()
                optimizer.step()

                total_train_loss += loss.item() * len(batch_ratings)

            train_rmse = np.sqrt(total_train_loss / len(train_dataset))

            if val_loader:
                self.model.eval()
                total_val_loss = 0.0
                with torch.no_grad():
                    for v_users, v_items, v_ratings in val_loader:
                        v_users = v_users.to(self.device)
                        v_items = v_items.to(self.device)
                        v_ratings = v_ratings.to(self.device)
                        preds = self.model(v_users, v_items)
                        v_loss = criterion(preds, v_ratings)
                        total_val_loss += v_loss.item() * len(v_ratings)

                val_rmse = np.sqrt(total_val_loss / len(valid_val))
                self.model.train()

                if val_rmse < best_val_loss:
                    best_val_loss = val_rmse
                    patience_counter = 0
                    os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
                    torch.save(self.model.state_dict(), self.checkpoint_path)
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        break

        # Load best weights if saved
        if os.path.exists(self.checkpoint_path):
            self.model.load_state_dict(
                torch.load(self.checkpoint_path, map_location=self.device)
            )

        self.model.eval()
        self.training_time_sec = time.time() - start_time
        self.is_fitted = True

    def predict(self, user_id: int, movie_id: int) -> float:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        if user_id not in self.user2idx or movie_id not in self.movie2idx:
            return self.fallback_pop.predict(user_id, movie_id)

        u = self.user2idx[user_id]
        i = self.movie2idx[movie_id]

        with torch.no_grad():
            u_t = torch.tensor([u], dtype=torch.long, device=self.device)
            i_t = torch.tensor([i], dtype=torch.long, device=self.device)
            pred = self.model(u_t, i_t).item()

        return float(np.clip(pred, 1.0, 5.0))

    def recommend(
        self,
        user_id: int,
        k: int = 10,
        candidate_movie_ids: Optional[List[int]] = None,
    ) -> List[RecommendationItem]:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        if user_id not in self.user2idx:
            return self.fallback_pop.recommend(user_id, k, candidate_movie_ids)

        u = self.user2idx[user_id]
        candidates = (
            candidate_movie_ids
            if candidate_movie_ids is not None
            else list(self.all_movie_ids)
        )

        cand_indices = []
        valid_mids = []
        for mid in candidates:
            if mid in self.movie2idx:
                cand_indices.append(self.movie2idx[mid])
                valid_mids.append(mid)

        if not cand_indices:
            return self.fallback_pop.recommend(user_id, k, candidate_movie_ids)

        with torch.no_grad():
            u_t = torch.tensor([u] * len(cand_indices), dtype=torch.long, device=self.device)
            i_t = torch.tensor(cand_indices, dtype=torch.long, device=self.device)
            scores = self.model(u_t, i_t).cpu().numpy()

        top_k_indices = np.argsort(scores)[::-1][:k]

        results: List[RecommendationItem] = []
        for idx in top_k_indices:
            movie_id = valid_mids[idx]
            score = float(scores[idx])
            results.append(
                RecommendationItem(
                    movie_id=movie_id,
                    title=self._get_movie_title(movie_id),
                    genres=self._get_movie_genres(movie_id),
                    score=round(score, 3),
                    reason=f"Neural CF match: {score:.1f}★ predicted from deep embeddings",
                )
            )

        return results
