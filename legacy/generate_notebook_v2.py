"""Generate interactive MovieLens_RecSys_Enhanced.ipynb Jupyter Notebook."""

import json

notebook = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# 🎬 Cine Cas Phile: Movie Recommendation System\n",
                "### Modernized, Evaluated, and Deployable RecSys with Zero Data Leakage\n",
                "\n",
                "This notebook evolves the research code from `khanhnamle1994/movielens` into a production-grade recommender system.\n",
                "\n",
                "#### Key Enhancements:\n",
                "1. **Zero Data Leakage Protocol**: Chronological 80/10/10 split per user.\n",
                "2. **Demographic-Aware Deep & Wide Network**: Fuses user demographics (Age, Gender, Occupation) and movie attributes (Year, Genres, ID).\n",
                "3. **Time-Decay Recency Weighting**: Prioritizes recent user taste changes.\n",
                "4. **Maximal Marginal Relevance (MMR)**: Re-ranks top-K lists to prevent genre redundancy and filter bubbles.\n",
                "5. **Multi-Signal Hybrid Ensemble**: Combines collaborative filtering, deep demographics, TF-IDF content matching, and popularity."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import os, sys, re, time\n",
                "import numpy as np\n",
                "import pandas as pd\n",
                "import matplotlib.pyplot as plt\n",
                "from tabulate import tabulate\n",
                "import torch\n",
                "\n",
                "from movielens_unified_system import (\n",
                "    UnifiedDataLoader, TemporalSplitter,\n",
                "    PopularityRecommender, ContentBasedRecommender,\n",
                "    BiasedMatrixFactorization, DemographicDeepRecommender,\n",
                "    EnhancedHybridRecommender, Evaluator\n",
                ")\n",
                "print(f\"PyTorch: {torch.__version__} | Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}\")"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1. Data Loading & Chronological Splitting (Zero Leakage)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "loader = UnifiedDataLoader()\n",
                "movies_df, ratings_df, users_df = loader.load_all()\n",
                "train_df, val_df, test_df, manifest = TemporalSplitter.split(ratings_df)\n",
                "\n",
                "print(f\"Total Ratings: {len(ratings_df):,} | Users: {ratings_df['user_id'].nunique():,} | Movies: {len(movies_df):,}\")\n",
                "print(f\"Train: {len(train_df):,} | Val: {len(val_df):,} | Test: {len(test_df):,}\")\n",
                "print(f\"Temporal Leakage Check: {'PASSED (Zero Leakage)' if not manifest['leakage_detected'] else 'FAILED'}\")"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 2. Model Training & Fitting"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "print('Fitting models on train set...')\n",
                "m_pop = PopularityRecommender()\n",
                "m_pop.fit(train_df, movies_df)\n",
                "\n",
                "m_cb = ContentBasedRecommender()\n",
                "m_cb.fit(train_df, movies_df)\n",
                "\n",
                "m_svd = BiasedMatrixFactorization()\n",
                "m_svd.fit(train_df, movies_df)\n",
                "\n",
                "m_deep = DemographicDeepRecommender(epochs=4)\n",
                "m_deep.fit(train_df, movies_df, users_df)\n",
                "\n",
                "m_hybrid = EnhancedHybridRecommender()\n",
                "m_hybrid.fit(train_df, movies_df, users_df)\n",
                "print('All models trained successfully!')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 3. Comprehensive Zero-Leakage Benchmark"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "all_mids = set(movies_df['movie_id'].unique())\n",
                "user_train_map = train_df.groupby('user_id')['movie_id'].apply(set).to_dict()\n",
                "models = [m_pop, m_cb, m_svd, m_deep, m_hybrid]\n",
                "\n",
                "benchmark_results = [Evaluator.evaluate(m, test_df, all_mids, user_train_map, sample_u=200) for m in models]\n",
                "results_df = pd.DataFrame(benchmark_results)\n",
                "print(tabulate(results_df, headers='keys', tablefmt='pipe', showindex=False))"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 4. Personalized Recommendations with MMR Diversification"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "test_user = 1\n",
                "cands = list(all_mids - user_train_map.get(test_user, set()))\n",
                "recs = m_hybrid.recommend(test_user, k=10, candidates=cands, use_mmr=True)\n",
                "\n",
                "table = [[i + 1, r.title, r.genres, r.score, r.reason] for i, r in enumerate(recs)]\n",
                "print(f'\\nTop 10 Recommendations for User #{test_user}:\\n')\n",
                "print(tabulate(table, headers=['#', 'Title', 'Genres', 'Score', 'Explanation'], tablefmt='fancy_grid'))"
            ]
        }
    ],
    "metadata": {
        "language_info": {"name": "python"},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

with open("MovieLens_RecSys_Enhanced.ipynb", "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=2)

print("Created MovieLens_RecSys_Enhanced.ipynb successfully!")
