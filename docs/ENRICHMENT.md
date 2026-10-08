# Film metadata, posters, ratings and scene search

The base is the user's 3,883-film MovieLens catalog. Supplemental titles in `data/raw/catalog_extra.csv` use reserved IDs ≥1,000,000; source provenance is in `data/enrichment/editorial.json`. UTF-8 titles retain their accents. Series are labeled explicitly; La Mesías (2023) has seven episodes. Metadata is separate from historical train ratings and never becomes fabricated user interactions.

The MUBI and Letterboxd import reads public film metadata, artwork and rating aggregates. It does not copy reviews, plot text, video streams or account data. Letterboxd IMDb-ID links are documented at https://letterboxd.com/about/film-data/. IMDb ID and release year must agree before an existing catalog item receives Letterboxd artwork. The frontend prefers Letterboxd, then MUBI, PhimMoi and FshareTV, and falls back to original illustration if remote images fail. A source site's image can itself be incorrect; source links remain visible for inspection.

All 3,883 original films were checked against the two user-selected FshareTV / PhimMoi sources. Only 1,011 have verified exact title/year matches there (802 FshareTV, 234 PhimMoi, overlapping). Those sites do not contain matching metadata for the entire catalog. Counts of imported metadata and successful reference-image downloads are different; remote images require Internet and may change.

External scores retain provider, audience/critics category, original scale, count, page URL and date checked. Letterboxd and MUBI use /5; IMDb uses /10; Rotten Tomatoes critic Tomatometer and audience Popcornmeter are percentages of positive ratings; Metacritic Metascore is /100 and user score is /10. They are not averaged into one score or mixed with historical MovieLens ratings. Missing data displays an em dash and a missing-data label.

IMDb snapshots are published by FshareTV and explicitly marked “via FshareTV”; they are not represented as a live official IMDb API. Rotten Tomatoes and Metacritic imports cover a small verified set of titles. `verified_audience.json` preserves manually verified Metacritic user scores when the public HTML lacks that hydrated field; the original checked date is retained. A cached primary page was used to verify The Matrix's user score: https://www.metacritic.com/movie/the-matrix/. Reports record errors rather than inventing values. The fetch cache preserves snapshots; remove selected cached HTML files before an intentional refresh. Sources are not guaranteed to be current at runtime.

## Update commands

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

The original Mirella font is preserved at `web/assets/fonts/mirella/Mirella.ttf`. The header brand uses its previous Arial stack and the silhouette logo retains Operation Napalm outlines. The downloaded Mirella has 94 characters and lacks Vietnamese accents. To fix inconsistent fallback glyphs, `tools/build_mirella_vi.py` makes a personal project companion, `Mirella-CCP-Personal.ttf`, preserving the original Latin glyphs and adding drawn geometric diacritics and Đ/đ. This is a local adaptation, not an official Vietnamese Mirella release. The font remains under the original personal-use terms, with the author's original README preserved. Source: https://www.1001fonts.com/mirella-font.html. Letter spacing is natural, hard line breaks are removed and text wraps according to available width. The slogan is “One film, one fish fillet.” with “(Un film, un filet de poisson.)”. There is no separate MUBI/Letterboxd navigation shelf; imported movies remain in the shared catalog.
