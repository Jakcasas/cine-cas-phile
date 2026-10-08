# Cine (cas) phile. 1.0 — online accounts and community

The website keeps version **1.0**. Production: https://cinecasphile.netlify.app.

## Environment variables

Copy `.env.example` to `.env`. Do not put secrets in source code, screenshots or GitHub.

| Variable | Purpose |
|---|---|
| `MONGODB_URI` | Atlas connection URI for the app database |
| `MONGODB_DB` | `cinecasphile` |
| `SITE_URL` | `https://cinecasphile.netlify.app` (no trailing slash) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google OAuth web client |
| `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` | Meta Login app credentials |
| `FACEBOOK_API_VERSION` | Supported Graph API version, currently configured as `v24.0` |
| `FACEBOOK_LOGIN_ENABLED` | `true` only after Meta Login is public and approved; otherwise `false` |
| `ADMIN_EMAIL` | Optional verified Google account for report access; not required to publish blogs |

Alternatively set `MONGODB_HOST`, `MONGODB_USER`, `MONGODB_PASSWORD` in local `.env`; the import script builds a URL-encoded URI. Quote a password containing `#` or whitespace. The Atlas account password and database user password are different.

Run `node tools/configure_netlify_env.mjs --check` to list key names only, then `node tools/configure_netlify_env.mjs` to copy non-empty keys to the Netlify **production** context. The script uses the authenticated Netlify API bundled with the local CLI and never prints values. Install its runtime with `npm install --prefix runtime/netlify-cli netlify-cli` if absent. Redeploy after changing function variables. Secret keys are marked as secrets. On plans that cannot restrict scopes, Netlify exposes them only to its execution systems; never reference them from frontend or build output.

## JSON first, then MongoDB

`data/catalog/movies.json` is the film metadata export. Its portable JSON Schema is `data/catalog/movie.schema.json`; portable personal collection schema is `docs/profile.schema.json`.

MongoDB validators live in `netlify/functions/data/club-schema.json`, using MongoDB's `$jsonSchema` dialect. `node tools/import_mongodb_catalog.mjs` applies validators and upserts film JSON records by `movie_id`. It does not delete user data. The API creates missing collections and indexes on first connection. Collections: films, users, profiles, sessions, oauth, posts, likes, reports, feedback, limits. Session and OAuth-state TTL indexes expire temporary credentials. MongoDB stores accounts and community records; public film discovery uses the bundled JSON export for low-latency queries without exposing credentials.

Use an Atlas application user restricted to `readWrite` on the Cine database after initial schema/index setup. Ensure Atlas network access allows your Netlify functions' outgoing addresses. A fixed egress gateway is preferable when an IP allowlist is required. Do not disable TLS or reuse passwords in code.

## Google / Facebook callbacks

Google authorized JavaScript origin: `https://cinecasphile.netlify.app`.

Google callback: `https://cinecasphile.netlify.app/club/auth/google/callback`.

Facebook callback: `https://cinecasphile.netlify.app/club/auth/facebook/callback`.

Only basic identity is requested: Google `openid email profile`; Facebook `public_profile,email`. Google uses state, nonce, PKCE and verified ID tokens. Facebook uses server-side token exchange and `appsecret_proof`. Both use server-side session cookies. Do not publish the Facebook app until Meta's required privacy, data-deletion and review steps are satisfied. Basic Google identity scopes do not require access to Gmail messages, Drive or contacts.

Email registration uses a hashed password and session; this release does not send verification or password-reset email. An email-password account does not receive admin access by matching `ADMIN_EMAIL`; optional admin access requires Google to verify that email. Provider identities are not automatically linked by email, avoiding unsafe account takeover.

## Guest and publishing behavior

Offline guests can choose a nickname or **Ẩn danh**, save/watch/rate films and export JSON. Online guests receive their own session and may chat, blog, review or send feedback. Anonymous posts hide the display name, not the server's ownership record. Logging out returns to the separate device guest profile. Profiles from different online accounts are not stored together in localStorage.

Blogs are **published immediately with reporting**, following the owner's latest decision. Only the author can remove their post; an optional verified admin can remove reported content. Spoilers are collapsed by default. Reports and feedback are stored for follow-up, not automatically treated as proven violations.

## Run and test in VS Code

`npm ci`, `npm run build`, `npm run dev`; open http://127.0.0.1:8001. F5 uses the first `full website` configuration. Local preview reads `.env` but uses `cinecasphile_dev`; override `PREVIEW_MONGODB_DB` to select another test database. Local OAuth requires adding local callbacks to the provider, and is not enabled just by a production client.

`npm test` runs viewer filters/profile persistence and actual MongoDB API integration in an isolated temporary database. The MongoDB test binary comes from the official MongoDB distribution and is cached locally; no test posts are published to Atlas. Python API/engine tests remain available via `python -m pytest -q` and `python -m tools.verify_netlify`.

Account secrets and online private data are excluded from project ZIPs. The Netlify prebuilt bundle includes its dependency manifest; use `npm ci --omit=dev` before CLI deployment to package MongoDB and OAuth libraries.
