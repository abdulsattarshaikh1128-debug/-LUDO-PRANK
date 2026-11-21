# Dynamic dice update (ludo-prank-v2.html)
- Single #dice node is reparented (FLIP-animated), never cloned; result/face untouched.
- placeDice(m,anim): 1-3 players -> slot (#ds-<k>) beside the ACTIVE player's profile (k = M.players[M.turn].k); 4+ players -> centred #dock under the board. Called from render().
- Player panels are wrapped in .pc with a reserved .dslot; game screen CSS ("ingame" body class) = full-height layout, landscape rules.
- Tests: tests/dice_position_test.py (bot matches, Playwright) and tests/dice_human_test.py (human clicks). Run with python + playwright + chromium.
- NOT included (not in the uploaded ZIP): Android project, APK build, screenshot, audio files, AdMob code.
