"""Optional display metadata; does not change model features or ratings."""
import json
import re
from urllib.parse import urlparse

IMAGE_HOSTS = {"m.media-amazon.com", "cdn.galaxycine.vn", "images.fsharetv.co", "fsharetv.com", "phimmoic.ws",
               "images.mubicdn.net", "assets.mubicdn.net", "a.ltrbxd.com", "s.ltrbxd.com"}
PAGE_HOSTS = {"fsharetv.com", "phimmoic.ws", "mubi.com", "letterboxd.com", "www.imdb.com", "www.galaxycine.vn"}
RATING_HOSTS = PAGE_HOSTS | {"www.imdb.com", "www.rottentomatoes.com", "www.metacritic.com"}
PROVIDERS = {"MUBI", "Letterboxd", "IMDb", "Rotten Tomatoes", "Metacritic"}


def safe_url(value, hosts):
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and parsed.hostname in hosts and not parsed.username and not parsed.password else None


class MovieEnrichment:
    def __init__(self, path):
        self.movies = {}
        self.updated_at = None
        data = {"movies": {}}
        for file in [path, path.parent / "editorial.json", path.parent / "ratings.json", path.parent / "imdb_releases.json", path.parent / "galaxy_releases.json"]:
            if not file.exists():continue
            payload = json.loads(file.read_text(encoding="utf-8"))
            self.updated_at = payload.get("updated_at")
            for mid, entry in payload.get("movies", {}).items():
                merged = data["movies"].setdefault(mid, {})
                for key, value in entry.items():
                    if key in {"poster_sources", "external_ratings", "catalog_sources", "releases", "title_aliases"}:
                        merged[key] = merged.get(key, []) + value
                    else:merged[key] = value
        for mid, entry in data.get("movies", {}).items():
            sources = []
            for source in entry.get("poster_sources", []):
                image = safe_url(source.get("image_url"), IMAGE_HOSTS)
                page = safe_url(source.get("page_url"), PAGE_HOSTS)
                if image and page and source.get("name") in {"FshareTV", "PhimMoi", "MUBI", "Letterboxd", "IMDb", "Galaxy Cinema"}:
                    sources.append({"name": source["name"], "image_url": image, "page_url": page,
                                    "fallback_url": safe_url(source.get("fallback_url"), IMAGE_HOSTS)})
            ratings=[]
            for rating in entry.get("external_ratings", []):
                try:
                    value,scale=float(rating["value"]),float(rating["scale"])
                except (KeyError,TypeError,ValueError):continue
                url=safe_url(rating.get("url"),RATING_HOSTS)
                if url and 0<=value<=scale and scale in {5,10,100} and rating.get("provider") in PROVIDERS and rating.get("audience") in {"audience","critics"}:
                    ratings.append({**rating,"url":url,"value":value,"scale":scale})
            metadata={key:entry[key] for key in ["catalog_sources","media_type","directors","imdb_id","episode_count"] if key in entry}
            cinema=entry.get('cinema_status',{})
            if isinstance(cinema,dict) and cinema.get('status')=='now' and cinema.get('region')=='VN' and safe_url(cinema.get('url'),{'www.galaxycine.vn'}):
                metadata['cinema_status']=cinema
            releases=[]
            for release in [entry.get('release',{}),*entry.get('releases',[])]:
                if (isinstance(release,dict) and release.get('region') in {'US','VN','GB','FR','JP','KR'}
                        and isinstance(release.get('date'),str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',release['date'])
                        and safe_url(release.get('url'),RATING_HOSTS) and release not in releases):
                    releases.append(release)
            if releases:metadata.update(release=releases[0],releases=releases)
            metadata['title_aliases']=[t[:200] for t in entry.get('title_aliases',[]) if isinstance(t,str)][:20]
            self.movies[int(mid)] = {**metadata,"title_vi": str(entry.get("title_vi", ""))[:200],
                                     "poster_sources": sources,"external_ratings":ratings,
                                     "still_urls":[url for value in entry.get("still_urls",[]) if (url:=safe_url(value,IMAGE_HOSTS))]}

    def enrich(self, movie):
        entry = self.movies.get(movie["movie_id"])
        if not entry:
            return movie
        # Prefer the newest requested source, then fall back to the other one.
        priority={"Letterboxd":0,"MUBI":1,"Galaxy Cinema":2,"IMDb":3,"PhimMoi":4,"FshareTV":5}
        sources = sorted(entry["poster_sources"], key=lambda item: priority[item["name"]])
        urls = list(dict.fromkeys(url for source in sources for url in
                    [source["image_url"], source["fallback_url"]] if url))
        return {**movie, **entry, "poster_sources": sources, "poster_urls": urls,
                "poster_updated_at": self.updated_at}
