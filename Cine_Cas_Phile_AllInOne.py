"""Compatible launcher; implementation now lives in the modular src package."""
import argparse
from src.cli import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cine (cas) phile. 1.0 launcher")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--recommend", type=int)
    parser.add_argument("--cold-start")
    parser.add_argument("--model", default="hybrid")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--mmr", action="store_true", help="Diversity is enabled by default in 1.0")
    args = parser.parse_args()
    if args.train:
        main(["train"])
    elif args.benchmark:
        main(["benchmark"])
    elif args.recommend is not None:
        main(["recommend", "--user", str(args.recommend), "--model", args.model])
    elif args.cold_start:
        main(["recommend", "--genres", args.cold_start])
    else:
        main(["serve", "--port", str(args.port)])
