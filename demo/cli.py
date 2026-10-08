"""Compatibility: python -m demo.cli --user 1 --k 10."""
import sys
from src.cli import main

if __name__ == "__main__":
    main(["recommend", *sys.argv[1:]])
