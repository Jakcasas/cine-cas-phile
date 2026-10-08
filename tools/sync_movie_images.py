"""Fetch public poster metadata from the two user-selected sites.

No media downloads or video/player requests. pip install beautifulsoup4
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import time
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from src.data.loader import MovieLensLoader
from src import settings

CACHE = settings.ROOT / "runtime" / "source-cache"


def fetch(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    file = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".html")
    if file.exists():
        return BeautifulSoup(file.read_text(encoding="utf-8"), "html.parser")
    request = Request(url, headers={"User-Agent": "CineCasPhile/3.0 (local poster metadata project)"})
    with urlopen(request, timeout=20) as response:
        html = response.read(5_000_000).decode("utf-8", errors="replace")
    file.write_text(html, encoding="utf-8")
    return BeautifulSoup(html, "html.parser")


def normalize(title):
    title = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
    title = re.sub(r"^(.+),\s*(The|A|An|La|Le|Les|El|Il)$", r"\2 \1", title, flags=re.I)
    title = unicodedata.normalize("NFKD", title.casefold())
    title = "".join(c for c in title if not unicodedata.combining(c))
    tokens = re.findall(r"[a-z0-9]+", title)
    return " ".join(t for t in tokens if t not in {"the", "a", "an"})


def aliases(title):
    clean = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
    parts = [clean, re.sub(r"\([^)]*\)", "", clean)]
    parts += re.findall(r"\(([^)]+)\)", clean)
    return {normalize(p) for p in parts if normalize(p)}


def parse_fshare(soup, page_url):
    for item in soup.select(".movie-item"):
        title = item.find("b")
        image = item.find("img")
        link = item.select_one('a[href^="/movie/"]')
        if not title or not image or not link:
            continue
        match = re.match(r"(.+)\s+\((\d{4})\)$", title.get_text(strip=True))
        if not match:
            continue
        fallback = re.search(r"this.src='([^']+)'", image.get("onerror", ""))
        vi = item.select_one("span.text-gray")
        yield {"title": match[1], "year": int(match[2]), "title_vi": vi.get_text(strip=True) if vi else "",
               "source": {"name": "FshareTV", "page_url": urljoin(page_url, link["href"]),
                          "image_url": image.get("src"),
                          "fallback_url": fallback[1] if fallback else None}}


def parse_phimmoi(soup, page_url):
    # A release year is read from the film's visible information panel, never
    # datePublished (which is the date the website uploaded its page).
    heading = soup.find("h1")
    if not heading:
        return None
    panel = heading.parent.get_text(" ", strip=True)
    year = re.search(r"Năm sản xuất:\s*(\d{4})", panel)
    if not year:
        return None
    names = [heading.get_text(strip=True)]
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            obj = json.loads(script.get_text())
        except (ValueError, TypeError):
            continue
        if obj.get("@type") == "Movie":
            names.extend([obj.get("name", ""), obj.get("alternateName", "")])
    subtitle = heading.find_next_sibling("p")
    if subtitle:
        names.append(subtitle.get_text(strip=True))
    image = soup.select_one('meta[property="og:image"]')
    if not image:
        return None
    return {"names": names, "year": int(year[1]), "title_vi": names[0],
            "source": {"name": "PhimMoi", "page_url": page_url,
                       "image_url": urljoin(page_url, image["content"]), "fallback_url": None}}


def phimmoi_for(movie):
    title = re.sub(r"\s*\(\d{4}\)\s*$", "", movie.title)
    title = re.sub(r",\s*(The|A|An)$", r" \1", title, flags=re.I)
    title = re.sub(r"\s*\([^)]*\)", "", title).strip()
    search_url = "https://phimmoic.ws/search?" + urlencode({"q": title})
    soup = fetch(search_url)
    targets = []
    desired = aliases(movie.title)
    for link in soup.select('a[href^="/phim/"][title]'):
        container = link.parent
        names = [link.get("title", "")]
        names.extend(p.get_text(strip=True) for p in container.find_all(["h3", "p"]))
        if any(aliases(n) & desired for n in names):
            url = urljoin(search_url, link["href"])
            if url not in targets:
                targets.append(url)
    for url in targets[:3]:
        item = parse_phimmoi(fetch(url), url)
        if item and item["year"] == int(movie.year) and any(aliases(n) & desired for n in item["names"]):
            return int(movie.movie_id), item
    return int(movie.movie_id), None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fshare-pages", type=int, default=8)
    parser.add_argument("--phimmoi-limit", type=int, default=40)
    parser.add_argument("--missing-only", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--unrated-only", action="store_true")
    args = parser.parse_args()
    movies = MovieLensLoader(raw_movies_path=str(settings.DATA_DIR / "movies.csv")).load_movies()
    index = {}
    for movie in movies.itertuples():
        for title in aliases(movie.title):
            index.setdefault((title, int(movie.year)), set()).add(int(movie.movie_id))
    output = settings.ROOT / "data" / "enrichment" / "movie_images.json"
    previous = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    enriched = previous.get("movies", {})
    errors = []

    def save():
        counts = {name: sum(any(s["name"] == name for s in entry["poster_sources"]) for entry in enriched.values())
                  for name in ["FshareTV", "PhimMoi"]}
        data = {"updated_at": datetime.now(timezone.utc).isoformat(), "sources": counts,
                "match_rule": "normalized exact title alias AND exact release year; ambiguous matches skipped",
                "movies": enriched}
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(output)
        return counts

    def add(mid, item):
        entry = enriched.setdefault(str(mid), {"title_vi": "", "poster_sources": []})
        if item.get("title_vi"):
            entry["title_vi"] = item["title_vi"]
        source = item["source"]
        entry["poster_sources"] = [s for s in entry["poster_sources"] if s["name"] != source["name"]] + [source]

    pages = ["https://fsharetv.com/"]
    for page in range(1, args.fshare_pages + 1):
        pages.append("https://fsharetv.com/filter?" + urlencode({"genre": "", "country": "", "year": "",
                     "sort_by": "imdb_votes", "sub": "", "year_range": "", "page": page}))
    # Film eras keep the enrichment focused on the 1919–2000 training catalog.
    for era in ["-1950", "1951-1960", "1961-1970", "1971-1980", "1981-1990", "1991-2000"]:
        pages.append("https://fsharetv.com/filter?" + urlencode({"genre": "", "country": "", "year": "",
                     "sort_by": "imdb_votes", "sub": "", "year_range": era, "page": 1}))
    def fshare_page(url):
        return list(parse_fshare(fetch(url), url))

    with ThreadPoolExecutor(max_workers=min(args.workers, 6)) as pool:
      futures = [(url, pool.submit(fshare_page, url)) for url in pages]
      for page_number, (url, future) in enumerate(futures, 1):
        try:
            for item in future.result():
                candidates = set().union(*(index.get((name, item["year"]), set()) for name in aliases(item["title"])))
                if len(candidates) == 1:
                    add(candidates.pop(), item)
        except Exception as error:
            errors.append({"source": "FshareTV", "url": url, "error": str(error)})
        if page_number % 20 == 0:
            save()
            print(f"FshareTV pages {page_number}/{len(pages)}: {len(enriched)} matches", flush=True)
    save()
    print(f"FshareTV: {len(enriched)} matched movies", flush=True)
    ratings = MovieLensLoader(raw_ratings_path=str(settings.DATA_DIR / "ratings.csv")).load_ratings()
    popular_ids = ratings.groupby("movie_id").size().reindex(movies.movie_id, fill_value=0).sort_values(ascending=False).head(args.phimmoi_limit).index
    selected = movies.set_index("movie_id", drop=False).loc[popular_ids]
    if args.unrated_only:
        rated_ids=set(ratings.movie_id)
        selected=selected[~selected.movie_id.isin(rated_ids)]
    if args.missing_only:
        selected = selected[~selected.movie_id.astype(str).isin(enriched)]
    print(f"PhimMoi: checking {len(selected)} remaining titles", flush=True)
    with ThreadPoolExecutor(max_workers=min(args.workers, 6)) as pool:
        futures = [(int(movie.movie_id), pool.submit(phimmoi_for, movie)) for movie in selected.itertuples(index=False)]
        for count, (mid, future) in enumerate(futures, 1):
            try:
                _, item = future.result()
                if item:
                    add(mid, item)
            except Exception as error:
                errors.append({"source": "PhimMoi", "movie_id": mid, "error": str(error)})
            if count % 100 == 0:
                save()
                print(f"PhimMoi {count}/{len(selected)} checked: {len(enriched)} total matches; {len(errors)} request errors", flush=True)
    counts = save()
    missing = [{"movie_id": int(m.movie_id), "title": m.title, "year": int(m.year)}
               for m in movies.itertuples() if str(m.movie_id) not in enriched]
    report = {"catalog_movies": len(movies), "matched_movies": len(enriched), "coverage": len(enriched)/len(movies),
              "sources": counts, "missing_movies": missing, "errors": errors}
    (settings.ROOT / "reports" / "poster_sync.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in {"missing_movies", "errors"}}, ensure_ascii=True), flush=True)
    print(f"Missing: {len(missing)}; request errors: {len(errors)}. See reports/poster_sync.json", flush=True)


if __name__ == "__main__":
    main()
