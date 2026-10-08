"""Paths are relative to the project, never to a particular developer's home."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("CINE_DATA_DIR", ROOT / "data" / "raw"))
ARTIFACT = ROOT / "artifacts" / "engine.npz"
DATABASE = Path(os.environ.get("CINE_DB_PATH", ROOT / "runtime" / "profiles.sqlite3"))
VERSION = "1.0.0"
