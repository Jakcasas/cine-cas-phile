"""SQLite profiles for local use. All SQL values are parameterized."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


class ProfileStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY, genres TEXT NOT NULL DEFAULT '[]');
                CREATE TABLE IF NOT EXISTS ratings(profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                    movie_id INTEGER, rating REAL CHECK(rating >= 1 AND rating <= 5), PRIMARY KEY(profile_id, movie_id));
                CREATE TABLE IF NOT EXISTS watchlist(profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                    movie_id INTEGER, PRIMARY KEY(profile_id, movie_id));
            """)

    def create(self):
        profile_id = str(uuid.uuid4())
        with self.connection() as db:
            db.execute("INSERT INTO profiles(id) VALUES (?)", (profile_id,))
        return self.get(profile_id)

    def get(self, profile_id):
        with self.connection() as db:
            row = db.execute("SELECT genres FROM profiles WHERE id=?", (profile_id,)).fetchone()
            if row is None:
                return None
            ratings = dict(db.execute("SELECT movie_id,rating FROM ratings WHERE profile_id=? ORDER BY movie_id", (profile_id,)).fetchall())
            watchlist = [row[0] for row in db.execute("SELECT movie_id FROM watchlist WHERE profile_id=? ORDER BY rowid DESC", (profile_id,))]
        return {"profile_id": profile_id, "genres": json.loads(row[0]), "ratings": ratings, "watchlist": watchlist}

    def preferences(self, profile_id, genres):
        with self.connection() as db:
            db.execute("UPDATE profiles SET genres=? WHERE id=?", (json.dumps(genres), profile_id))

    def rate(self, profile_id, movie_id, rating):
        with self.connection() as db:
            db.execute("INSERT INTO ratings VALUES (?,?,?) ON CONFLICT(profile_id,movie_id) DO UPDATE SET rating=excluded.rating", (profile_id, movie_id, rating))

    def unrate(self, profile_id, movie_id):
        with self.connection() as db:
            db.execute("DELETE FROM ratings WHERE profile_id=? AND movie_id=?", (profile_id, movie_id))

    def watchlist(self, profile_id, movie_id, saved):
        with self.connection() as db:
            if saved:
                db.execute("INSERT OR IGNORE INTO watchlist VALUES (?,?)", (profile_id, movie_id))
            else:
                db.execute("DELETE FROM watchlist WHERE profile_id=? AND movie_id=?", (profile_id, movie_id))
