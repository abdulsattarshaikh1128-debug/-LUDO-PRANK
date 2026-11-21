# v6 – one-tap movement + Customize Players
1. One-tap movement (`offerMoves`, `tap`): one distinct legal move -> executes 180 ms after the dice settles, no ring, no second tap.
   Several distinct moves -> tokens glow with "Tap the token you want to move"; ONE tap on a token moves it immediately (the old lift/confirm second tap and destination marker are no longer used).
   Same-cell tokens (e.g. yard tokens on a 6) are one move. The dice result is never re-rolled; extra dice taps during a move are ignored.
2. Robot Mode -> "Customize Players" (`customView`): Human selector (1-5) + Robot selector (0-5), total 2..6 shown and capped, per-player list with colour and Human/Robot badge,
   difficulty (existing easy/medium/hard), Start Game / Back, last choice remembered (localStorage `lp-custom`).
   Starts the real engine via `startMatch({n:humans+robots,h:humans,diff,custom:true})`; robots are named Robot 1..N and play through the normal AI.
Tests: tests/onetap_custom_test.py (+ updated ranking_automove_test, six_player_anim_test).
