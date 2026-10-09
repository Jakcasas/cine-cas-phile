# Cinema listings — version 1.0

Snapshot checked 9 October 2026. The public website provides country and release-state filters, cinema source links and checking dates. It does not sell tickets or claim complete nationwide showtime coverage.

| Market | Cinema source | Scope |
|---|---|---|
| Vietnam | [Galaxy Cinema](https://www.galaxycine.vn/) | Home-page now-playing / coming-soon cards |
| United States | [Harkins Theatres](https://www.harkins.com/movies) | Chain now-playing / coming-soon lists and film detail pages |
| United Kingdom | [Everyman](https://www.everymancinema.com/film-listing/) | Now-playing at The Whiteley, London, 8–9 October; chain coming-soon / prebooking listings |
| France | [Pathé](https://www.pathe.fr/) | Home-page now-playing / upcoming lists and film detail pages |
| Japan | [TOHO Cinemas](https://hlo.tohotheater.jp/net/movie/TNPI3090J01.do) | Chain now-playing / upcoming lists |
| South Korea | [Megabox](https://www.megabox.co.kr/movie) | Box office and coming-soon cards; future opening dates classified as presales |

The reviewed snapshot has 98 matched films, including 20 newly added catalog films, and 180 source listings. Multiple listings may refer to one film, different markets or special screenings. Unmatched names, ambiguous reissues and event programmes are recorded in `reports/cinema_sync.json`, rather than assigned an unverified film ID. Original release years are kept separate from market dates: *Avengers: Endgame* stays 2019 and *Obsession* stays 2025.

“Đang chiếu” requires a fresh cinema listing, checked no more than seven days ago. Listings with a future opening or screening date cannot qualify. Market dates use local time zones. “Mới công chiếu” means a verified release date within 30 days and excludes marked reissues. “Sắp chiếu” includes cinema announcements with a future date or no date yet, plus verified future IMDb calendar events. “Đã phát hành” excludes films currently confirmed playing in the selected market. A date alone never proves current availability.

Snapshots are manually reviewed; this change does not configure an automatic refresh job. Open the source links for current showtimes, venue selection and schedule changes. Poster URLs are whitelisted and fall back to other verified sources or a title cover when unavailable. The new film metadata does not invent viewer scores.

## Refresh the project

Review film identity, original year, genres, market status, date and source URL first. Use the public JSON structure in `data/sources/cinema_snapshot.json`; append snapshots to version control only after review. Secrets never belong in those files.

```powershell
python -m tools.import_cinema_snapshot data/sources/cinema_snapshot.json
python -m src.cli train
python -m src.cli benchmark --users 200 --rating-pairs 10000
python -m tools.build_visual_index
python -m tools.build_netlify
npm run build
python -m pytest -q --basetemp=runtime/pytest-cinema
npm test
python -m tools.verify_netlify
```

When MongoDB and Netlify credentials are already configured, `node tools/import_mongodb_catalog.mjs` upserts film documents. Deploy with the production build context as described in `docs/DOMAIN.md`. Keep version 1.0.

## Opening date and cinema links

The upcoming filter defaults to opening-date order: the nearest recorded market date comes first, and films with no confirmed date stay at the end. Other status filters sort known past openings newest first. Dates are scoped to the selected release country; a screening day is never substituted for an opening date. Fresh cinema cards link directly to the official listing for that country.
