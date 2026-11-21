# LUDO PRANK: AdMob + audio assets guide (Android)

Status: **not connected**. This is setup material for the real Android app. The web prototype contains no ads.

## 1. Required AdMob configuration (you must do this)
1. Create an AdMob account, add the app, and copy the **App ID** (`ca-app-pub-XXXX~YYYY`).
2. Create ad units: Banner (Home), Interstitial (after match), Rewarded (optional rewards).
3. Create a Google Cloud OAuth client with the AdMob API enabled (for the reporting dashboard).
4. Configure the GDPR/consent message in AdMob Privacy & messaging (UMP) and complete the Play Console Data safety form.
5. Keep production IDs in `local.properties` / build config, not in git. Never ship server secrets in the app.

## 2. Gradle and manifest
```kotlin
// app/build.gradle.kts
dependencies { implementation("com.google.android.gms:play-services-ads:<latest 23.x, check release notes>") }
buildTypes {
  debug   { manifestPlaceholders["admobAppId"] = "ca-app-pub-3940256099942544~3347511713" } // Google test app ID
  release { manifestPlaceholders["admobAppId"] = project.findProperty("ADMOB_APP_ID") as String }
}
```
```xml
<uses-permission android:name="android.permission.INTERNET"/>
<application>
  <meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" android:value="${admobAppId}"/>
</application>
```

## 3. Test ad unit IDs (Google official, debug builds only)
- Banner: `ca-app-pub-3940256099942544/9214589741`
- Interstitial: `ca-app-pub-3940256099942544/1033173712`
- Rewarded: `ca-app-pub-3940256099942544/5224354917`

Never click your own production ads. Use test IDs or registered test devices.

## 4. AdsManager.kt
```kotlin
object Ads {
  private var inter: InterstitialAd? = null
  private var rewarded: RewardedAd? = null
  private var lastInter = 0L
  private var matchesSinceInter = 0
  private const val MIN_GAP_MS = 180_000L   // frequency cap: 3 min
  private const val EVERY_N_MATCHES = 2     // and every 2nd match

  fun init(activity: Activity, onReady: () -> Unit) {
    // 1) Ask for consent first (UMP), 2) only then initialize ads if consent allows.
    val params = ConsentRequestParameters.Builder().build()
    val ci = UserMessagingPlatform.getConsentInformation(activity)
    ci.requestConsentInfoUpdate(activity, params, {
      UserMessagingPlatform.loadAndShowConsentFormIfRequired(activity) {
        if (ci.canRequestAds()) MobileAds.initialize(activity) { onReady() }
      }
    }, { /* log error, run without ads */ })
  }

  fun banner(ctx: Context, unitId: String) = AdView(ctx).apply {
    setAdSize(AdSize.BANNER); adUnitId = unitId; loadAd(AdRequest.Builder().build())
  } // add only to Home / non-gameplay layouts, above the nav bar, never over the board

  fun loadInterstitial(ctx: Context, unitId: String) =
    InterstitialAd.load(ctx, unitId, AdRequest.Builder().build(), object : InterstitialAdLoadCallback() {
      override fun onAdLoaded(ad: InterstitialAd) { inter = ad }
      override fun onAdFailedToLoad(e: LoadAdError) { inter = null }
    })

  /** Call ONLY after a match ends and the result screen is closed. Never during play. */
  fun maybeShowInterstitial(activity: Activity, matchActive: Boolean, next: () -> Unit) {
    matchesSinceInter++
    val ok = !matchActive && inter != null && matchesSinceInter >= EVERY_N_MATCHES &&
             System.currentTimeMillis() - lastInter > MIN_GAP_MS
    if (!ok) return next()
    inter!!.fullScreenContentCallback = object : FullScreenContentCallback() {
      override fun onAdDismissedFullScreenContent() { inter = null; lastInter = System.currentTimeMillis(); matchesSinceInter = 0; next() }
      override fun onAdFailedToShowFullScreenContent(e: AdError) { inter = null; next() }
    }
    inter!!.show(activity)
  }

  fun loadRewarded(ctx: Context, unitId: String, userId: String) =
    RewardedAd.load(ctx, unitId, AdRequest.Builder().build(), object : RewardedAdLoadCallback() {
      override fun onAdLoaded(ad: RewardedAd) {
        ad.setServerSideVerificationOptions(ServerSideVerificationOptions.Builder()
          .setUserId(userId).setCustomData(UUID.randomUUID().toString()).build()) // one rewardId per offer
        rewarded = ad
      }
      override fun onAdFailedToLoad(e: LoadAdError) { rewarded = null }
    })

  /** Show only after the player taps "Watch ad" on a screen that already explains the reward. */
  fun showRewarded(activity: Activity, onEarned: () -> Unit, onUnavailable: () -> Unit) {
    val ad = rewarded ?: return onUnavailable()
    ad.show(activity) { onEarned() }  // onEarned = request reward from YOUR server; do not grant locally
    rewarded = null
  }
}
```
Lifecycle: call `adView.pause()/resume()/destroy()` in the matching Activity callbacks; reload interstitial and rewarded ads after each use.

## 5. Rewarded verification (server side)
1. In AdMob, enable server-side verification (SSV) on the rewarded unit and set your callback URL.
2. Your server receives Google's signed callback (`user_id`, `custom_data`, `transaction_id`, `signature`, `key_id`). Verify the signature with Google's published public keys.
3. Store `transaction_id` in a table with a unique constraint. A repeated ID means duplicate claim: reject it.
4. Grant the reward in your database only after successful verification, then let the app refresh the player's inventory.
5. Record status per transaction: `pending`, `verified`, `rejected`, with timestamps.

## 6. Admin revenue dashboard (server-side only)
- Build it on your backend using the AdMob API (`accounts.networkReport.generate`) with OAuth. Never put the refresh token or client secret in the app.
- Protect it with admin authentication and role checks. Ordinary players get no route to it.
- Show: impressions by format, estimated revenue, eCPM, daily/weekly/monthly totals, failures, last successful sync time. Label revenue as **estimated**; confirmed payments come only from AdMob payments reports.
- Active users, new users and completed matches come from your own analytics/database, not AdMob.
- If no reporting connection exists, show "Not connected". Never fill in numbers.

## 7. Required audio assets (not included; the prototype uses synthesized placeholders)
Format: `.ogg` or `.mp3`, 44.1 kHz, normalized around -16 LUFS, no clipping.
- Music, seamlessly loopable: `music_login_intro`, `music_home_loop`, `music_game_loop`, `music_victory_sting`, `music_defeat_sting`.
- SFX: `dice_roll`, `dice_land`, `token_move`, `token_capture`, `slipper_whoosh`, `cry`, `laugh`, `six`, `token_home`, `button_tap`, `victory`, `defeat`, `daily_reward`, `reward_wheel`.
- Voice: **Hindi only** (voices never change with country, IP, SIM or GPS). Real voice actors, 2 to 3 takes per line, rights documented.
  - **Announcer lines (26 files):** capture x12, six x5, home x3, win x4, no-move x2. Name: `audio/hi/<event>_<index>.mp3`, key `FILES['hi.cut.0']`.
  - **Robot lines (86 lines, 14 events):** robot cuts human x12 (`rcut`), human cuts robot x11 (`rcutted`), robot six x6 (`rsix`), robot home x4 (`rhome`), robot wins x5 (`rwin`), robot loses x4 (`rlose`), low rolls x4 (`lowroll`), missed capture x3 (`missed`), narrow escape x3 (`escape`), double capture x3 (`double`), human near win x3 (`nearwin`), general comedy chatter x28 (`meme`).
  - **Three robot personalities** (teasing/mischievous, dramatic/deep, excited/fast). Best: 3 distinct voice actors each recording all 86 lines = 258 files, key `FILES['hi.p0.rcut.0']` (persona 0), `hi.p1...`, `hi.p2...`. Minimum: one actor, 86 files, key `FILES['hi.rcut.0']`, used for every robot.
  - The exact text and index order are the `LINES.hi` arrays in the game. Recommended total: 284 files (minimum 112).
- Crying and laughing reaction clips (voice-actor recorded) can replace the synthesized `cry` and `laugh` effects.

## 8. Reward Wheel: backend and rewarded-ad spins (required for production)
The web prototype saves the wallet in the browser, so a user can edit it. In the real app the server must be the authority:
1. `POST /wheel/spin`: server checks the signed-in player, computes the day from **server UTC time**, enforces 3 free spins and 3 ad spins (6 total) per day, picks the reward on the server, credits it in the database, stores a transaction row (`id`, `player`, `day`, `source`, `reward`, `ts`) and returns the reward. The app animates to the returned slice and never chooses the reward.
2. Ad spins: the app shows the rewarded ad (section 4). Your SSV endpoint verifies Google's callback and stores the `transaction_id`. Only then does `POST /wheel/spin` with `source=ad` succeed, and it consumes that verified transaction once. No verified transaction means no spin.
3. Unique constraints on `transaction_id` and on the spin transaction id prevent duplicate claims. Show "ad unavailable" when no ad loads.
4. Never sell spins and never offer cash prizes or withdrawals.
5. Interstitials: only after a match result is closed (see `maybeShowInterstitial`). Banners: Home/menu only, never on the board screen.

## 9. Ad placement rules and rewarded offers (final)
**Banners (adaptive, test ID in debug):** Home, Daily Reward Center, Shop, Inventory and Settings. Never on the match screen, the matchmaking/room screens or the winner celebration. Keep them clear of the bottom navigation.

**Interstitials:** call `Ads.maybeShowInterstitial` only when the player taps **BACK TO HOME** or **PLAY AGAIN** on the winner screen (or at another non-gameplay transition). Never while the celebration (fireworks, music, voice) is visible, and never during dice rolling, token moves, captures or Hindi dialogue. The frequency caps in `Ads` (every 2nd match and at least 3 minutes apart) still apply. Preload the next interstitial after each show.

**Rewarded offers (always optional):** bonus coins, extra wheel spin (max 3 per day), token skin, dice skin, funny sticker, slipper skin. Show a dialog first that names the exact reward, with "Watch ad" and "No thanks":
```kotlin
enum class RewardType { COINS, WHEEL_SPIN, TOKEN_SKIN, DICE_SKIN, STICKER, SLIPPER_SKIN }
fun offerReward(activity: Activity, type: RewardType, description: String, onGranted: () -> Unit) {
  AlertDialog.Builder(activity).setTitle("Watch a short ad?").setMessage("You will receive: $description")
    .setPositiveButton("Watch ad") { _, _ ->
      Ads.showRewarded(activity,
        onEarned = { /* ask YOUR server to grant; it waits for Google's SSV callback with custom_data = offerId + type */ },
        onUnavailable = { Toast.makeText(activity, "No ad available right now. Try again later.", Toast.LENGTH_SHORT).show() })
    }.setNegativeButton("No thanks", null).show()
}
```
The server creates the `offerId` (stored with `type`, `player`, `status=pending`) before the ad. Pass it as `setCustomData`. When Google's SSV callback arrives and verifies, mark it `verified` and credit the reward once. The app only refreshes the player's balance/inventory from the server.

## 10. Winner celebration audio (assets still needed)
The prototype synthesizes the victory tune, fireworks booms/crackles, confetti pops and party horn. Replace with licensed or original files: `music_victory_loop` (6 to 10 s, energetic, not a film song), `sfx_firework_boom` x3, `sfx_firework_crackle` x2, `sfx_confetti_pop` x3, `sfx_party_horn`.
Winner announcements are built from the real player name. Record per seat (Player One to Four; add Five and Six only when extended boards exist): 5 named lines (`winner0` ... `winner3`, keys `FILES['hi.winner0.0']` ... `hi.winner0.4`; the index follows the order in the game's `WN` function) plus 3 shared lines. Named lines: "वाह! {name} ने बाज़ी मार ली!", "क्या बात है! {name} बन गया आज का चैंपियन!", "जोरदार जीत! {name} ने सबको पीछे छोड़ दिया!", "आज तो {name} का जलवा है!", "जीत गया {name}, बधाई हो!". Shared: "भाई ने पूरा गेम पलट दिया!", "बाकी खिलाड़ियों को टाटा बाय-बाय!", "वाह भाई! क्या शानदार जीत है!". That is 20 files for four seats; each recording says the actual name ("Player One" and so on).

## 11. Revenue dashboard server
See `admin-revenue.js` (server only). It denies everyone until you implement real admin authentication, returns `not_connected` without AdMob credentials, never invents figures, labels revenue as estimated, and reports the last successful sync. Rewarded completions come from your own verified SSV table because the AdMob API does not report them as "completions".

## 12. Dialogue library and natural-voice pipeline
- The game now ships a hand-written library of **193 unique Hindi lines in 36 categories** (`tools/dialogue-library.json`, ids `category_index`, append-only). It is **not** 15,000. Reaching 15,000 genuinely different lines needs writers (or reviewed batches of ~300 to 500 lines per category group) checked by `tools/validate-dialogue.mjs`, which rejects exact duplicates, near-duplicate clones (name/number swaps), banned words, over-long lines and bad placeholders and prints progress toward the target.
- Voices: `tools/generate-voice-audio.mjs` renders every name-free line with an authorized neural Hindi voice (Google Cloud Text-to-Speech) for three personas, with short comic pauses. Audition voices first and check the service terms for game use. Real human recordings would still sound more natural; use the same file names: `FILES['hi.line.p<persona>.<id>']`. Laughter, breathing and crying need recorded clips.
- Lines containing player names are spoken by the device voice until name variants are recorded (the name is always correct). Captions are off by default; players can turn them on in Settings.


---
## v8 status (supersedes "not connected" above)
The game now calls a `window.LudoAndroid` bridge. Reference implementation: `android/LudoPrank/app/src/main/java/com/ludoprank/game/LudoBridge.kt`.
* Rewarded (Daily, Weekly, bonus Spin): nonce from `/api/ads/start` -> `showRewarded(nonce,userId,kind)` -> `onAdResult` -> server redeem. In the AdMob console enable **server-side verification** on the rewarded unit and set the callback URL to `https://<your-host>/api/ads/ssv`. Run the server with `ADS_MODE=ssv`. Google's TEST units send no SSV callback, so for development run `ADS_MODE=dev` (the server then accepts the app's completion report - never in production).
* Banner: Home/Store/Inventory/Messages/Friends/Profile only. Interstitial: after a finished match, back on Home, capped.
* Test IDs are in the Kotlin file; **missing: your production App ID and the three production ad-unit IDs** (put them in BuildConfig/local.properties, not in the repo).
