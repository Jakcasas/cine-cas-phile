# Cine (cas) phile. 1.0 on Netlify

Live website: **https://cinecasphile.netlify.app/**.

Public source: **https://github.com/Jakcasas/cine-cas-phile**.

Netlify site ID: `00750758-f294-4229-bdd8-865b45c6382d`.

## Build and deploy from source

Use Node.js 22 or newer. Configure MongoDB and OAuth credentials in the Netlify production context as described in [ONLINE_SETUP.md](ONLINE_SETUP.md). Redeploy whenever function variables change.

```bash
npm ci
netlify deploy --prod --build --context production --site 00750758-f294-4229-bdd8-865b45c6382d --dir dist/netlify --functions netlify/functions
```

The build runs `npm run build`. Explicit production context ensures that the function bundle receives production environment variables. Do not add `--no-build` to this command. The site ID belongs to the original owner; use your own site ID for a separate deployment.

Deployment currently uses the authenticated Netlify CLI. Git-based continuous deployment is not connected. Dropping only the static folder omits the API and account functions.

After changing training data or the visual index, rebuild the Python artifacts and run `python -m tools.build_netlify`, then deploy. `python -m tools.verify_netlify` checks the exported research engine against Python; `npm test` checks browser profiles and the MongoDB community API.

## Online behavior

- Four main sections: discovery, recommendations, watchlist and collection. The audience survey uses genres, era, mood and favorite films, with an explanation for each suggestion.
- Email accounts, Google login and online guests use server sessions and MongoDB profiles. Watchlist, watched films, half-star ratings and survey answers synchronize online. Offline guests retain a separate device profile.
- Chat, reviews, blogs, likes, reports and feedback use MongoDB. Blogs publish immediately with reporting. No fabricated community activity is included.
- Facebook credentials and callback are configured, but the public button stays hidden until Meta's identity/business verification and publication requirements are completed. Set `FACEBOOK_LOGIN_ENABLED=true` only after approval.
- Scene recognition runs in browser WASM. User images are not uploaded. The current index contains 1,365 reference images covering 1,330 films, including 35 scene stills. It searches this reference set rather than the entire web. First use downloads roughly 110 MB of model/runtime files.
- Public metadata contains 3,920 films. Films without verified poster matches use a named fallback cover. External ratings retain their source, scale and verification date.

## Address and version

Canonical metadata, footer, robots.txt and sitemap use **https://cinecasphile.netlify.app/**. Version remains **1.0**.

Secrets in `.env`, local sessions and runtime files are excluded from Git and release ZIPs. Online setup and provider limitations are documented in [ONLINE_SETUP.md](ONLINE_SETUP.md).
