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

## Endless mode (RITE I, II, III ...)
Bone dice (`?dice=classic` for the old ones, `?pipglow=1` makes only the pips glow while sinking) on a stone board. A new twist arrives every 150s (or at 1500/3500/6000/9000/12500 score), one at a time, each with a callout and a ~13s calmer breather:

| Rite | Arrives (time / score) | Twist | Hall |
|---|---|---|---|
| I | start | the game as before | A grey stone |
| II | 2:30 / 1500 | chained dice (immovable, match + sink normally, sinking frees them) | A |
| III | 5:00 / 3500 | slime dice (never roll, only slide until they hit something) | A |
| IV | 7:30 / 6000 | pits (no entry, spawns avoid them, shift each rite) | A |
| V | 10:00 / 9000 | walls on tile edges (block rolls/slides, not matches) | A |
| VI | 12:30 / 12500 | the twists mix; ramp begins | A morphs to C (mossy temple) in place |
| VII-VIII | every 2:00 / +4000 | ramp: more chained/slime/pits/walls, faster spawns | C |
| IX | 18:30 | second escalation: faster spawns | C morphs to B (dark basalt) |
| X+ | every 2:00 | ramp to its cap (rite XI), then terrain just shifts | B |

Caps: chained <=6, slime <=5, pits <=5, walls <=8, spawn interval >=1.5s. Hall changes are an in-place morph (a wave of tiles swapping, dice/pits/walls untouched). Debug: `?stage=N`, plus `__game.setStage / addStageTime / setTerrain / place(gx,gy,top,kind)` hooks. Tests: `test.py` (core) and `test_endless.py URL VW VH [shots]` (endless rules).

## Board drafts
`?board=a|b|c` pins one hall for the whole run (and disables the hall change).
