# Film metadata, posters, ratings and scene search

The base is the user's 3,883-film MovieLens catalog. Supplemental titles in `data/raw/catalog_extra.csv` use reserved IDs ≥1,000,000; source provenance is in `data/enrichment/editorial.json`. UTF-8 titles retain their accents. Series are labeled explicitly; La Mesías (2023) has seven episodes. Metadata is separate from historical train ratings and never becomes fabricated user interactions.

The MUBI and Letterboxd import reads public film metadata, artwork and rating aggregates. It does not copy reviews, plot text, video streams or account data. Letterboxd IMDb-ID links are documented at https://letterboxd.com/about/film-data/. IMDb ID and release year must agree before an existing catalog item receives Letterboxd artwork. The frontend prefers Letterboxd, then MUBI, Galaxy, IMDb, PhimMoi and FshareTV, and falls back to original illustration if remote images fail. A source site's image can itself be incorrect; source links remain visible for inspection.

All 3,883 original films were checked against the two user-selected FshareTV / PhimMoi sources. Only 1,011 have verified exact title/year matches there (802 FshareTV, 234 PhimMoi, overlapping). Those sites do not contain matching metadata for the entire catalog. Counts of imported metadata and successful reference-image downloads are different; remote images require Internet and may change.

External scores retain provider, audience/critics category, original scale, count, page URL and date checked. Letterboxd and MUBI use /5; IMDb uses /10; Rotten Tomatoes critic Tomatometer and audience Popcornmeter are percentages of positive ratings; Metacritic Metascore is /100 and user score is /10. They are not averaged into one score or mixed with historical MovieLens ratings. Missing data displays an em dash and a missing-data label.

IMDb snapshots are published by FshareTV and explicitly marked “via FshareTV”; they are not represented as a live official IMDb API. Rotten Tomatoes and Metacritic imports cover a small verified set of titles. `verified_audience.json` preserves manually verified Metacritic user scores when the public HTML lacks that hydrated field; the original checked date is retained. A cached primary page was used to verify The Matrix's user score: https://www.metacritic.com/movie/the-matrix/. Reports record errors rather than inventing values. The fetch cache preserves snapshots; remove selected cached HTML files before an intentional refresh. Sources are not guaranteed to be current at runtime.

## Update commands

The 09 October 2026 update imports 138 new films from public IMDb release calendars for US, GB, FR, JP and KR, plus six from Galaxy Cinema detail pages (144 new titles, 4,064 catalog films). Reports `imdb_release_sync.json` and `galaxy_release_sync.json` record the selected scope. `imdb_releases.json` and `galaxy_releases.json` preserve IDs, poster provenance, market, dates and verification date; no reviews or unverified ratings are imported. The main opening date takes precedence over early screenings. These are snapshots, not a live showtimes service or confirmed nationwide availability. Galaxy's verified now-playing snapshot expires after seven days in the filter.

The Node website searches title aliases, director, year and IMDb ID with accent/punctuation normalization and optional typo suggestions. Minimum audience-star filters normalize /10 to /5 for filtering only; the card retains its original source and scale. Critic scores and approval percentages are not audience stars. Future releases are excluded from default personal recommendations; explicitly selecting an upcoming filter includes them.

The next cinema update adds 20 catalog films, bringing the catalog to 4,084 films. It matches 98 films to 180 cinema-source listings across all six markets. See [CINEMA_LISTINGS.md](CINEMA_LISTINGS.md) for sources, market scope and exclusions. Presales stay upcoming; now-playing listings expire after seven days. Original film years are kept separate from market opening and reissue dates.

To import a reviewed public JSON snapshot, use `python -m tools.import_imdb_calendar path/to/snapshot.json`, `python -m tools.import_galaxy_snapshot path/to/snapshot.json --now-slugs comma-separated-verified-slugs` or `python -m tools.import_cinema_snapshot data/sources/cinema_snapshot.json`. Never label a date as now-playing without checking the cinema listing. Retrain, benchmark and rebuild the visual index after catalog changes. The visual builder reuses exact ID/kind/URL vectors only when the encoder/preprocessing fingerprint agrees, then updates the catalog fingerprint. Current coverage: 1,490 films, 1,525 image references, including 35 stills.

Install `requirements-tools.txt` in the virtual environment, then run from the project root:

```powershell
$env:PYTHONPATH=(Get-Location).Path
.venv\Scripts\python.exe tools/sync_movie_images.py --fshare-pages 136 --phimmoi-limit 3883
.venv\Scripts\python.exe tools/sync_editorial.py
.venv\Scripts\python.exe tools/sync_external_ratings.py
.venv\Scripts\python.exe tools/sync_letterboxd_catalog.py
.venv\Scripts\python.exe -m src.cli train
.venv\Scripts\python.exe -m src.cli benchmark --users 200 --rating-pairs 10000
.venv\Scripts\python.exe tools/build_visual_index.py
```

Restart the server after updates. Respect source access rules; requests that require account access or security challenges are skipped. Sources retain their copyrights; public visibility does not grant a commercial redistribution license.

## Find a film from a scene screenshot

`src/api/vision.py` runs CLIP ViT-B/32 INT8 in ONNX Runtime on the CPU. It compares a screenshot's embedding with actual indexed MUBI stills and catalog poster embeddings. It returns distinct candidate films ranked by cosine similarity, plus the matching reference image. Similarity is not an identification probability. The scene library is small: scenes absent from the references can yield visually related but incorrect films. It is a local image-retrieval assistant, with narrower coverage than Google's web index.

Use the “Tìm bằng ảnh” button, select a JPEG/PNG/WebP screenshot under 8 MB and press the search button. Crop away large borders and subtitles. Input is decoded in memory, limited to 20 megapixels, processed locally and not saved or sent to third-party services. Reference downloads are only for indexing public film images; `runtime/reference-images/` is omitted from the ZIP. Model and safe NPZ index are included, so retrieval runs without external API keys.

Model source: https://huggingface.co/Xenova/clip-vit-base-patch32 (quantized ONNX conversion of OpenAI CLIP), file `onnx/vision_model_quantized.onnx`. CLIP upstream: https://github.com/openai/CLIP. `reports/visual_smoke.json` checks cropped/resized known stills; it does not measure accuracy on unseen scenes. Rebuild the index whenever the catalog or reference images change.

## Typography

The interface uses the original Noto Serif variable font with full Vietnamese glyph coverage, self-hosted under `web/assets/fonts/noto-serif/` with its SIL Open Font License. Source: https://github.com/google/fonts/tree/main/ofl/notoserif.

Mirella remains on the English/French slogan only. The original font has 94 characters and lacks Vietnamese support, so it is no longer used for Vietnamese controls or body text. The earlier private diacritic companion is retained as a project artifact but is not loaded by the interface. Header branding keeps its Arial stack and the silhouette logo retains Operation Napalm outlines. Text uses normal spacing, readable sizes and natural wrapping. The slogan remains “One film, one fish fillet. (Un film, un filet de poisson.)”.

The country selector denotes the release market, not the country of production. The same IMDb ID retains separate regional dates. Released means a recorded date on or before the local day, excluding verified now-playing entries in that market; recent openings are within 30 days. Upcoming uses a future date in the selected country. Unknown regional dates do not pass country filters. Now-playing requires a fresh cinema listing; IMDb calendar dates alone never assert current showtimes. Countries without verified cinema listings show a clear empty state instead of silently changing the selected filter.
