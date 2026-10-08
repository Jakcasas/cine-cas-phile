"""Interactive Command Line Interface for MovieLens Recommender System."""

import argparse
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from tabulate import tabulate
from src.api.service import RecommendationService


def main():
    parser = argparse.ArgumentParser(description="MovieLens Recommender CLI Demo")
    parser.add_argument("--user", type=int, default=1, help="Target user ID (e.g. 1)")
    parser.add_argument(
        "--model",
        type=str,
        default="hybrid",
        choices=["popularity", "content", "svd", "neural", "hybrid"],
        help="Recommendation algorithm to use",
    )
    parser.add_argument("--k", type=int, default=10, help="Number of recommendations")
    parser.add_argument(
        "--genres",
        type=str,
        default=None,
        help="Comma-separated genres for cold-start (e.g. 'Action,Sci-Fi')",
    )

    args = parser.parse_args()

    service = RecommendationService.get_instance()
    service.initialize()

    if args.genres:
        genre_list = [g.strip() for g in args.genres.split(",")]
        print(f"\n=======================================================")
        print(f"🎬 Cold-Start Recommendations for Genres: {genre_list}")
        print(f"=======================================================")
        recs = service.cold_start_by_genres(genre_list, k=args.k)
        table = [
            [i + 1, item.title, item.genres, item.score, item.reason]
            for i, item in enumerate(recs)
        ]
        print(
            tabulate(
                table,
                headers=["#", "Title", "Genres", "Score", "Reason"],
                tablefmt="fancy_grid",
            )
        )
    else:
        print(f"\n=======================================================")
        print(f"🎬 Personalized Recommendations for User #{args.user}")
        print(f"Algorithm: {args.model.upper()} | Top-{args.k}")
        print(f"=======================================================")

        res = service.recommend_for_user(user_id=args.user, k=args.k, model_name=args.model)
        table = [
            [i + 1, item.title, item.genres, item.score, item.reason]
            for i, item in enumerate(res.recommendations)
        ]
        print(
            tabulate(
                table,
                headers=["#", "Title", "Genres", "Score", "Reason"],
                tablefmt="fancy_grid",
            )
        )
        print(f"\n⚡ Latency: {res.latency_ms} ms | Fallback Triggered: {res.is_fallback}\n")


if __name__ == "__main__":
    main()
