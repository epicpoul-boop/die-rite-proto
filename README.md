# DIE RITE – swipe-to-roll dice sacrifice puzzle (prototype)
Single-file Three.js prototype (`index.html`). Portrait, swipe a die to roll it. Match N dice showing N to sink them as an offering; a lone **1** touching a sinking chain triggers **the Rite** – every 1 on the board is sacrificed.
Run locally: `python3 -m http.server` and open index.html. Test: `python3 test.py <url> [width height]` (Playwright).

Query flags: `?perf=1` fps overlay, `?lowfx=1` / `?hifx` force lower / full quality (quality also steps down automatically on slow phones; internal render width is 540 / 420 / 320 px).

Hosted on Railway (Dockerfile + Caddy). Pushes to main auto-deploy. The repo is private.

UI font: Press Start 2P (c) The Press Start 2P Project Authors, SIL OFL 1.1, embedded as base64 woff2 in index.html.

## Custom domain (die-rite.com) – not configured yet
When ready: Railway → service → Settings → Networking → **+ Custom Domain** → `die-rite.com` (and optionally `www.die-rite.com`; Hobby plan allows 2 custom domains). Railway then shows two records to create at the DNS provider (both required, or the domain 404s):
1. `CNAME` – name `@` (apex) → the `<id>.up.railway.app` target Railway displays. The apex needs a DNS host that supports CNAME flattening / ALIAS (Cloudflare, Namecheap, DNSimple…); Route 53, GoDaddy, Squarespace do not – in that case point the nameservers at Cloudflare.
2. `TXT` – name/value exactly as Railway displays (domain-ownership verification).
Optional: `CNAME www` → `die-rite.com` (or its own Railway target) plus a redirect www → apex. If Cloudflare proxying (orange cloud) is on, set SSL/TLS mode to **Full** (not Strict). SSL (Let's Encrypt) is issued automatically within about an hour of the records resolving.

## Board drafts (branch board-drafts, not deployed)
`?board=a|b|c` swaps in a stone-tile board + themed border (`&nodemo` hides the example pit + wall). Data-driven via `layout` (tile/pit) and `walls` (edge segments) inside `buildBoard()`.
