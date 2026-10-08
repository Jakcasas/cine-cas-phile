"""Train and measure the same cached engine used by the web app."""
from src.cli import train, benchmark

if __name__ == "__main__":
    train()
    benchmark()
