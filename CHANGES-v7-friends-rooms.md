# v7 – Friends online rooms made functional
Root causes found in the old code:
1. Lobby seats were deleted the moment a socket closed -> opening WhatsApp / a brief signal loss removed the host and deleted the room (later "Room not found").
2. Invitation link was built from the page location / a dev address (`file://`, localhost) instead of the real public server URL -> WhatsApp links never worked.
3. No password, no room settings, no host-only controls on the server.
4. Join/Create sent the request and showed a "Connecting…" screen; errors (not found/full) only toasted, leaving the user stuck/bounced; the `?room=` link joined blindly without showing room info or asking for a password.
5. No landing page / App Links / deep-link entry point.
Changes: server (passwords, config, colours, kick, close, peek API, grace, expiry, landing page, assetlinks), client (friendsMenu/createView/roomView/joinView, share, deep links), Android templates in android/app-links.
Tests: tests/friends_rooms_test.py (+ server_test.js unchanged 47/47).
