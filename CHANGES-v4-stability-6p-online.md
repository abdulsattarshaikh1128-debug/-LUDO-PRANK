# v4 – stable layout, six-player, online, animations
See the final report in chat. Summary of the code changes (all in `ludo-prank-v2.html` unless noted):
- Zoom lock (meta viewport + gesture/touch/wheel/dblclick handlers), fixed px layout computed once by `layoutLock()`, fixed bottom bar (Home / Sound / Settings).
- Six-player hexagon board (78-cell ring, 6 yards, hubs, safe cells) with parametrised engine; 2/3/4/5/6 players.
- New `server/ludo-rules.js`, `server/ludo-server.js` (rooms, quick match, reconnect) and client `NET`.
- Token lift/cancel/hop/cell-by-cell/yard animations; capture walks back the exact path.
- More male Hindi dialogue lines (`tools/dialogue-library.json`, validated).
- Fixed bug found by tests: Ready button threw because `NET.ready` collided with the connection promise (now `NET.setReady`).
Tests: tests/*.py, tests/server_test.js. Android: see ANDROID-NOTES.md.
