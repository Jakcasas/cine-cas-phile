# Model Card: MovieLens 1M Hybrid Recommender

## Model Details
- **Model Architecture**: Hybrid Ensemble (Biased FunkSVD + TF-IDF Content-Based + Bayesian Shrinkage Popularity)
- **Version**: 2.0.0
- **Framework**: Python 3.11, PyTorch 2.14, Scikit-Learn, NumPy, SciPy
- **Intended Use**: Personalized top-K movie recommendation with explainable reasons.
- **Cold-Start Strategy**: Two-level fallback (Content-based profile matching -> Bayesian popularity).
