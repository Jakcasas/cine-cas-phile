"""PyTorch Dataset and sparse utilities for collaborative filtering."""

import torch
from torch.utils.data import Dataset
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from typing import Tuple


class RatingDataset(Dataset):
    """PyTorch Dataset for user-item ratings."""

    def __init__(self, user_indices: np.ndarray, movie_indices: np.ndarray, ratings: np.ndarray):
        self.users = torch.tensor(user_indices, dtype=torch.long)
        self.movies = torch.tensor(movie_indices, dtype=torch.long)
        self.ratings = torch.tensor(ratings, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.ratings)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.users[idx], self.movies[idx], self.ratings[idx]


def create_sparse_matrix(
    df: pd.DataFrame, n_users: int, n_movies: int
) -> csr_matrix:
    """Creates a scipy CSR sparse matrix from interactions."""
    return csr_matrix(
        (df["rating"].values, (df["user_idx"].values, df["movie_idx"].values)),
        shape=(n_users, n_movies),
        dtype=np.float32,
    )
