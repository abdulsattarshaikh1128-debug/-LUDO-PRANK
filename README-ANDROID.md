# LUDO PRANK Android project (`android/LudoPrank`)
**Status: source only. It was NOT compiled or run in the sandbox that produced this ZIP (no Android SDK, no network).** Open it in Android Studio (Koala+ / JDK 17) and sync.

## One-time setup (nothing below can be done by code)
1. `cp local.properties.example local.properties` and fill `sdk.dir`, `SERVER_URL`, `GOOGLE_WEB_CLIENT_ID`, and (for release) your 4 AdMob ids.
2. **Deploy the server** (`server/`, `node server/ludo-server.js`) on a public HTTPS host with env from `server/.env.example`
   (`PUBLIC_URL`, `GOOGLE_CLIENT_ID` = the same Web client id, `ADS_MODE`, `ANDROID_PACKAGE=com.ludoprank.game`, `ANDROID_SHA256`, persistent `LUDO_DATA_DIR`).
3. **Google Cloud Console** -> APIs & Services -> Credentials (OAuth consent screen configured):
   * "Web application" client -> its id is `GOOGLE_WEB_CLIENT_ID` / server `GOOGLE_CLIENT_ID`.
   * "Android" client: package `com.ludoprank.game` + the SHA-1 of EACH signing key you use: debug (`./gradlew signingReport`), your release/upload key, and the **Play App Signing** key shown in Play Console. A missing SHA-1 is the usual cause of "sign-in failed / no credentials available".
   * Firebase is NOT required (Credential Manager + server-side token verification). If you also use Firebase Auth, add the same SHA-1/SHA-256 there.
4. **App Links**: put the release certificate SHA-256 into the server env `ANDROID_SHA256`; the server then serves `/.well-known/assetlinks.json` so `https://<host>/join/CODE` opens the app directly.
5. **AdMob**: create the app + banner/interstitial/rewarded units; on the rewarded unit enable server-side verification with callback `https://<host>/api/ads/ssv`. Run the server with `ADS_MODE=ssv` for production.
   Debug builds use Google's TEST ids automatically (rewarded test ads send no SSV callback -> use server `ADS_MODE=dev` only while testing).
   `./gradlew assembleRelease` refuses to build while any production id is empty or still a test id.

## Build
`./gradlew assembleDebug` (the game HTML is copied from `../../ludo-prank-v2.html` into the APK assets automatically). Gradle wrapper files are included only if generated; otherwise use Android Studio's Gradle.
