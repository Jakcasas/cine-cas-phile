"""Recommenders package exposing base and implementations."""

from src.recommenders.base import BaseRecommender, RecommendationItem
from src.recommenders.popularity import PopularityRecommender
from src.recommenders.content_based import ContentBasedRecommender
from src.recommenders.collaborative_filtering import ItemBasedCFRecommender
from src.recommenders.matrix_factorization import BiasedMatrixFactorization
from src.recommenders.hybrid import HybridRecommender

__all__ = [
    "BaseRecommender",
    "RecommendationItem",
    "PopularityRecommender",
    "ContentBasedRecommender",
    "ItemBasedCFRecommender",
    "BiasedMatrixFactorization",
    "NeuralMFRecommender",
    "HybridRecommender",
]


def __getattr__(name):
    if name == "NeuralMFRecommender":
        from src.recommenders.neural_mf import NeuralMFRecommender
        return NeuralMFRecommender
    raise AttributeError(name)
