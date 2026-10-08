"""Per-user temporal holdout with atomic timestamp groups.

This simulates continuation of each user's history, not a global-time deployment.
"""
import numpy as np
import pandas as pd


class TemporalSplitter:
    def __init__(self, train_ratio=.8, val_ratio=.1, test_ratio=.1, random_seed=42):
        ratios = np.array([train_ratio, val_ratio, test_ratio])
        if not np.isfinite(ratios).all() or (ratios <= 0).any() or not np.isclose(ratios.sum(), 1):
            raise ValueError("Split ratios must be positive and sum to one")
        self.train_ratio, self.val_ratio, self.test_ratio = ratios
        self.random_seed = random_seed

    def split(self, ratings_df):
        if ratings_df.duplicated(["user_id", "movie_id"]).any():
            raise ValueError("Deduplicate user/movie ratings before splitting")
        ordered = ratings_df.sort_values(["user_id", "timestamp", "movie_id"], kind="stable").reset_index(drop=True)
        partitions = [[], [], []]
        for _, group in ordered.groupby("user_id", sort=False):
            indices = group.index.to_numpy()
            times = group.timestamp.to_numpy()
            boundaries = np.flatnonzero(np.diff(times) != 0) + 1
            if len(indices) < 5 or not len(boundaries):
                partitions[0].extend(indices)
                continue
            train_end = int(boundaries[np.argmin(abs(boundaries - len(indices) * self.train_ratio))])
            later = boundaries[boundaries > train_end]
            val_end = int(later[np.argmin(abs(later - len(indices) * (self.train_ratio + self.val_ratio)))]) if len(later) else train_end
            partitions[0].extend(indices[:train_end])
            partitions[1].extend(indices[train_end:val_end])
            partitions[2].extend(indices[val_end:])
        train, val, test = [ordered.iloc[part].reset_index(drop=True) for part in partitions]
        leakage = False
        for early, late in ((train, val), (val, test), (train, test)):
            bounds = pd.concat([early.groupby("user_id").timestamp.max().rename("early"),
                                late.groupby("user_id").timestamp.min().rename("late")], axis=1).dropna()
            leakage |= bool((bounds.early >= bounds.late).any())
        pairs = [{tuple(pair) for pair in frame[["user_id", "movie_id"]].to_numpy()} for frame in (train, val, test)]
        leakage |= any(pairs[a] & pairs[b] for a, b in ((0, 1), (1, 2), (0, 2)))
        manifest = {"protocol": "temporal_per_user_atomic_timestamps", "train_ratio": float(self.train_ratio),
                    "val_ratio": float(self.val_ratio), "test_ratio": float(self.test_ratio),
                    "random_seed": self.random_seed, "n_total": len(ordered), "leakage_detected": bool(leakage),
                    "limitation": "Per-user time split; not a global chronological split. Catalog metadata is assumed available."}
        for name, frame in (("train", train), ("val", val), ("test", test)):
            manifest.update({f"n_{name}": len(frame), f"users_in_{name}": int(frame.user_id.nunique()),
                             f"items_in_{name}": int(frame.movie_id.nunique())})
        if leakage:
            raise ValueError("Overlapping holdout partitions")
        return train, val, test, manifest

    @staticmethod
    def get_user_train_items(train_df):
        return train_df.groupby("user_id").movie_id.apply(set).to_dict()

    @staticmethod
    def get_candidate_items(all_movie_ids, user_train_items):
        return sorted(all_movie_ids - user_train_items)
