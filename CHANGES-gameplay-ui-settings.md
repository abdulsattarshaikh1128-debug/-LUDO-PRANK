# Gameplay UI + in-game Settings update (ludo-prank-v2.html)
- Player cards: square (width == height, `--cs` scales 72-102px with screen), big avatar, name (max 2 lines, no overflow), colour tab, active card glow. Level / XP / Star removed from gameplay cards.
- Controls: Home, Voice and Settings live in a bottom bar (corners), never over the board. Inline SVG icons. Landscape uses a 3-column layout (cards | board | cards).
- Settings (bottom-right gear): pauses the match (sleep() gate), shows Game Voice, Male Voice Volume, Background Music, Music Volume, Sound Effects, Sound Effects Volume, Player Management, Return to Home (confirm), Resume Game. Prefs persist in localStorage `lp-audio`.
- Player management: status per player; host can mark a non-host human offline/reconnect and remove a disconnected player after confirmation. Removal fixes turn index, deletes tokens, moves the dice; deferred to the next turn start if a move is in flight. Hook for a future online layer: `setPlayerConnection('y', false)`.
- Tests: tests/gameplay_ui_test.py (187 checks), plus existing dice tests (paths made relative).
- NOT in the supplied ZIP: Android project, audio files, screenshot. No APK was built.
