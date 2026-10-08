# Cine (cas) phile. on Netlify

Live website: **https://cinecasphile.netlify.app**.

GitHub source: **https://github.com/Jakcasas/cine-cas-phile** (public repository).

Netlify project: `cinecasphile`, site ID `00750758-f294-4229-bdd8-865b45c6382d`. Production includes the UI, all five recommendation modes, movie search, rating snapshots, personal watchlist and scene image retrieval. Credentials are managed outside this project and excluded from Git/releases.

## Rebuild and deploy

The trained recommendation artifact is inside `netlify/functions/data/`. The CLIP model and browser index exports are included. Use Node.js 22 or newer:

```bash
npm ci
npm run build
netlify deploy --prod --site 00750758-f294-4229-bdd8-865b45c6382d --dir dist/netlify --functions netlify/functions --no-build
```

`netlify.toml` supports `npm run build` for continuous deployment if the GitHub repository is connected to Netlify. The current deployment uses the CLI; Git-based continuous deployment has not been connected. Dropping only the static folder does not install the API functions.

After retraining or updating metadata/index, run `python tools/build_netlify.py` with the project dependencies installed to refresh the JavaScript model and browser index exports. This Python exporter expects `onnxruntime-web` installed under `runtime/browser-onnx/`; the Node build uses the normal root dependency. Run `tools/verify_netlify.py` to compare all five modes against Python. See `reports/netlify_parity.json`.

## Hosted behavior

- Recommendation inference runs in a Netlify function. Model arrays are outside the public static directory. Raw MovieLens CSV and local SQLite profiles are not published by the website.
- Watchlist, ratings and genres persist in each browser's localStorage; there is no cross-device sync. Selected ratings/genres are sent to the site's API for recommendations, without a persistent profile database on Netlify.
- CLIP runs in the browser via ONNX Runtime Web/WASM. First use downloads approximately 110 MB of model/runtime files. Input screenshots are never uploaded. Matching covers 1,045 referenced films and 35 scene images, not general web image search.
- The benchmark reports Python measurements and labels them. Actual Netlify latency is returned for each recommendation request.

## Official address

The official URL is **https://cinecasphile.netlify.app/**. Canonical metadata, footer, robots.txt and sitemap use this address. Version remains **1.0**.

## Optional local Python server deployment example

1. Put the project on your chosen server and install dependencies. Start the application on 127.0.0.1:8000, supervised by your host's process manager.
2. In your DNS provider, point the apex `@` A record at the server's public IPv4 address. Point `www` at the apex with a CNAME (or use the host's specified target). Add an AAAA record only if the server actually serves IPv6. Use the provider's documented targets when using managed hosting.
3. Copy `deploy/Caddyfile.example` to the server. Configure `CINE_ADMIN_USER` and a bcrypt password hash generated with `caddy hash-password`; never place a plaintext password in the repository.
4. Run Caddy with that file on a server reachable on ports 80 and 443. It obtains HTTPS certificates after DNS points to that server, redirects the apex to www and proxies requests to the local app.
5. Verify the actual HTTPS page, DNS records, redirect and certificate externally before calling the domain active.

This example uses a password gate for a private personal deployment because the current profiles use local UUIDs without account authorization. A public multi-user launch requires proper account authentication/profile authorization and production operations. The example has not been deployed or verified on a server. Caddy's official HTTPS requirements and DNS setup: https://caddyserver.com/docs/quick-starts/https.

Domain fees and font/artwork permissions are separate. The bundled Mirella is for personal use. No purchase has been performed. The source repository is public.
