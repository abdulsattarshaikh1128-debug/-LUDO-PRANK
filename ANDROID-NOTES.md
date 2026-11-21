# Android notes
This ZIP contains no Android project, so no APK was built here. When wrapping the HTML in your WebView/Capacitor project:
- `webView.settings.setSupportZoom(false); builtInZoomControls=false; displayZoomControls=false; overScrollMode=OVER_SCROLL_NEVER`
- Edge-to-edge: pass real insets to the page (CSS env(safe-area-inset-*) is already used); `windowSoftInputMode=adjustNothing` for the game.
- Lock nothing else: both orientations are supported.
- Invite links: add an App Links intent-filter for `https://YOUR_HOST/?room=CODE` (optional; the link also works in the browser).
- Set the server address (see server/README-ONLINE.md). Needs INTERNET permission.
- Voice: device Hindi TTS is used, male voice only (silent if none). Recorded male voices: set a Google Cloud TTS key and run `tools/generate-voice-audio.mjs` (key not included).
