# LUDO PRANK – online backend

Real, authoritative Node server (no dependencies, Node 18+). It rolls dice, validates every move, runs rooms and quick-match queues.

    node server/ludo-server.js          # PORT=8787 by default, serves the game at / and WebSocket at /ws
    curl http://HOST:8787/health

Client: open the game from this server (`http://HOST:8787/`) and it connects automatically. In the APK / file:// build, set the server address once in
Play Online -> "Server address" (stored as `lp-server`), e.g. `wss://ludo.example.com/ws`. Use HTTPS/WSS in production (put nginx/Caddy/Cloudflare in front).

Features: unique 5-char room codes, `?room=CODE` share links, join by code, ready state, host start, leave/host hand-over, quick match 2-6 players (no bots),
server-side dice + move validation, turn timers/auto-skip for offline players, reconnect with session token, forfeit after grace period.

Needs from you (not included): a host/VPS or PaaS that can run Node with WebSockets and a public domain + TLS certificate. No API keys are required.
Env: `PORT`, `LUDO_TIMERS` (JSON, optional timing overrides). Rooms live in memory: a restart ends running matches (add Redis/DB if you need persistence).
Not included: Google sign-in, accounts, anti-cheat beyond server authority, rate limiting.

Tests: `node tests/server_test.js`, `python tests/online_ui_test.py` (starts its own server).


## Friends rooms, passwords and invitation links (v7)
- Rooms: create (optional password, 2-6 players, turn timer) -> lobby -> host customizes (players, timer, password, colours, remove player, close room) -> friends join with Room ID + password -> ready -> host starts.
- Password: stored only as a salted scrypt hash, compared in constant time; never sent to clients. 5 wrong tries lock that player for 30 s, 25 wrong tries lock the room for 60 s.
- Lobby seats survive an app switch / short signal loss (grace 90 s). Unused lobbies expire after 45 min; closed/expired codes answer "closed"/"expired" for 24 h.
- Invitation URL: `https://YOUR_DOMAIN/join/ROOMCODE?p=PASSWORD` (password only if the host ticks "Include password"). Opened in a browser it shows a fallback page (open in app / play in browser / instructions).
- WhatsApp: the Share button opens `https://wa.me/?text=...` (or the Android bridge); "Share Invitation" uses the system share sheet.

### Environment variables
| var | purpose |
|---|---|
| `PORT` | listen port (default 8787) |
| `PUBLIC_URL` | public https origin used in invitation links, e.g. `https://ludo.example.com` (otherwise taken from the request Host header) |
| `ANDROID_PACKAGE`, `ANDROID_SHA256` | enable `/.well-known/assetlinks.json` (comma separated SHA-256 signing fingerprints) and `intent://` links |
| `PLAY_STORE_URL` | "Get the app" button on the fallback page |
| `LUDO_TIMERS` | JSON overrides: `lobbyGrace`, `roomTtl`, `forfeit`, `idleRoll`, … |

### What you must provide
A public host that runs `node server/ludo-server.js` behind HTTPS/WSS (Caddy/nginx/Cloudflare, WebSocket upgrade on `/ws`), a domain, and for verified App Links your release-key SHA-256 + package name.
Android: see `android/app-links/` (manifest intent-filters, assetlinks template, WebView bridge example).


## v8: accounts and ads API (server/account-api.js)
| Route | Purpose |
|---|---|
| `GET /api/config` | `googleConfigured`, `googleClientId`, `adsMode` |
| `POST /api/auth/google` `{idToken}` | verifies the Google ID token (signature via Google, audience = `GOOGLE_CLIENT_ID`, issuer, expiry, verified e-mail) -> session token |
| `POST /api/auth/logout`, `GET/PUT /api/progress` | Bearer session; per-account wallet/profile (409 if stale) |
| `POST /api/ads/start`, `/api/ads/redeem` | single-use nonce, proof only after verification |
| `GET /api/ads/ssv` | AdMob server-side-verification callback (ECDSA signature checked against Google's keys, replay-protected) |
| `POST /api/ads/complete` | only when `ADS_MODE=dev` (Google test ads) |

Env: see `server/.env.example`. Persist `LUDO_DATA_DIR` (accounts.json). Serve over HTTPS and set `window.LUDO_SERVER_URL` (or `PUBLIC_URL`) so the app/WebView reaches it.
