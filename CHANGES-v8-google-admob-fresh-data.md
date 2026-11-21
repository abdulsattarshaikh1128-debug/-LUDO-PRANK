# v8 - Google Sign-In, AdMob rewards, fresh-user data

## What was wrong (root causes)
| Problem | Root cause | Fix |
|---|---|---|
| "Continue with Google" just opened the game | the button handler was `toast(); go('home')` - no authentication at all | Real flow: account chooser (Android Credential Manager bridge, or Google Identity Services in a browser) -> ID token -> **server verifies it** (`POST /api/auth/google`) -> session. Errors are shown on the login screen; success is never assumed. |
| Rewarded ads did nothing / daily+weekly were free | ads were never connected; daily/weekly claimed with no ad | `AD.rewarded(kind)`: server nonce -> native ad -> (production) Google-signed SSV callback -> single-use redeem. `RW.claimDaily/claimWeekly` accept `{requireAd, adProof}`; the proof is single use and kind-bound. Spin: the *bonus ad spin* needs the verified proof (free and ticket spins are unchanged). |
| Progress could look "shared" | wallet/profile lived in one fixed key; nothing tied it to a person | Guests keep the **original keys untouched**. A Google account uses its own keys (`lp-wallet:<id>`), synced to the server per account. A new install has empty storage -> fresh defaults. Nothing is baked into the HTML/APK. |
| Online rooms from far away | the client only knew `location.origin` | `window.LUDO_SERVER_URL` / Settings server address / server `welcome.pub`; see README-ONLINE.md. The game server must be on a public HTTPS host. |

## Behaviour
* **Guest** unchanged: same button, same data, login screen on each launch. Works even if Google or the server is unavailable.
* **Google**: stays on the login screen with a message for: server not configured, server unreachable, Google script blocked, user cancelled, forged/expired token. Signed-in users go straight to Home on relaunch. Sign out (Settings) removes that account's local copy (after a final sync) and returns to guest.
* **Fresh account/device**: a first sign-in on any device with no server record starts at default coins/gems (1250 / 30), no rewards, no spins, no stats.
* **Banners**: shown only on Home, Store, Inventory, Messages, Friends, Profile; hidden on Rewards, wheel, lobby and gameplay. They have no reward code path.
* **Interstitial**: only after a finished match, on the way back to Home; every 2nd finished match and not within 3 minutes of the previous one. Never during play.
* **Rewarded**: daily, weekly, bonus spin. No bridge / closed early / failed / unverified => nothing is granted, nothing is consumed.

## New / changed files
`server/account-api.js` (+ `.test.js`), `server/rewards-core.js` (ad gate), `server/ludo-server.js` (mounts `/api/*`), `server/.env.example`,
`android/LudoPrank/app/src/main/java/com/ludoprank/game/LudoBridge.kt`, `tests/accounts_ads_test.py`, `tests/test-server-launch.js` (TEST ONLY), `ludo-prank-v2.html`.

## Not possible to verify here (be honest)
* No Android project/APK, no real AdMob or Google account, no internet to Google: the native SDK bridge is reference code and was exercised through a **simulated** `window.LudoAndroid`. Server-side verification (token claims, SSV signature, nonce rules) is real code and tested with a test key / fake verifier.
* A real two-device, two-network online match could not be run from this sandbox (see CHANGES-v7 for what was tested).

## v8.1 - Android project added (`android/LudoPrank`)
Gradle project (AGP 8.5.2, Kotlin 1.9.24): MainActivity (WebView via WebViewAssetLoader, deep links, back button), LudoBridge (Google Mobile Ads banner/interstitial/rewarded with SSV options, Credential Manager Google sign-in, share/WhatsApp), manifest (AdMob App ID placeholder, App Links, backup disabled), build rules (test ids in debug; release build is blocked while production ids are missing or still test ids). Setup steps: `android/README-ANDROID.md`.
**Not compiled and not run on any device** - no Android SDK/network in the build sandbox. All real-device checks (Google chooser, ads, WhatsApp link, two phones on two networks) are still TO DO.
