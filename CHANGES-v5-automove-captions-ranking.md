# v5 – three gameplay changes
1. Smart auto-move (`distinct()` / `offerMoves()`): exactly one distinct legal move -> executed automatically (450 ms after the dice settles, pause-safe,
   works offline/online/all colours/2-6 players); 2+ distinct moves -> tokens glow + "Choose a token to move" prompt, two-tap select/confirm as before.
   Several tokens standing on the same cell (e.g. 4 in the yard on a 6) are one move. The dice result is never re-rolled.
2. Captions removed: `#cap` can no longer receive text, "Show captions" setting removed, win-screen dialogue text and the voice-preview toast removed.
   Voice (speech synthesis / recorded audio) and sound effects are untouched.
3. N-1 ranking: a player who brings 4 tokens home gets the next finishing position, is skipped for all later turns, keeps a visible card with a crown/place badge.
   Match ends when one player is left = the single final loser. Final screen lists everybody in order (Gold/Silver/Bronze crowns, 4th/5th badges, loser marked "Last Place · Eliminated").
   Server (`server/ludo-rules.js`, `ludo-server.js`): `finished`, `quit`, `loser`, `rank`/`over` on move events; forfeits rank below everyone still playing.
   A lone survivor with nobody finished keeps playing solo practice (as before).
Tests: tests/ranking_automove_test.py, tests/online_rank_test.py (+ online_rank_harness.js, test-only), tests/server_test.js.
