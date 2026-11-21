/* LUDO PRANK account + rewarded-ad API (zero dependencies).
   - Google Sign-In: the app sends a Google ID token; THIS server verifies it (signature via Google, audience = GOOGLE_CLIENT_ID,
     issuer, expiry, verified e-mail) and only then creates a session. No token = no session. Nothing is trusted from the client.
   - Progress: stored per Google account (sub). Guests never touch this API; their data stays on the device.
   - Rewarded ads: server-issued single-use nonce -> AdMob server-side verification (SSV) callback marks it verified ->
     the client redeems it once. ADS_MODE=ssv (production default) only accepts a Google-signed SSV callback.
     ADS_MODE=dev (testing with Google's TEST ad units, which send no SSV) accepts the app's own completion report. Never use dev in production.
   Env: GOOGLE_CLIENT_ID (OAuth *Web* client id - not a secret), ADS_MODE (ssv|dev), LUDO_DATA_DIR. */
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto'), https = require('https');
const sha = (s) => crypto.createHash('sha256').update(String(s)).digest('hex');
const SSV_KEYS_URL = 'https://www.gstatic.com/admob/reward/verifier-keys.json';

function getJson(url) {
  return new Promise((ok, no) => { const r = https.get(url, { timeout: 6000 }, (res) => { let b = ''; res.on('data', (c) => { b += c; if (b.length > 1e6) r.destroy(); }); res.on('end', () => { try { ok({ status: res.statusCode, json: JSON.parse(b) }); } catch (e) { no(e); } }); }); r.on('error', no); r.on('timeout', () => r.destroy(new Error('timeout'))); });
}
/* default verifier: Google's own tokeninfo endpoint validates the signature; we then check claims ourselves */
async function googleTokeninfo(idToken, clientId) {
  const { status, json } = await getJson('https://oauth2.googleapis.com/tokeninfo?id_token=' + encodeURIComponent(idToken));
  if (status !== 200) throw new Error('rejected');
  return checkClaims(json, clientId);
}
function checkClaims(c, clientId) {
  if (!c || c.aud !== clientId) throw new Error('wrong_audience');
  if (!['accounts.google.com', 'https://accounts.google.com'].includes(c.iss)) throw new Error('wrong_issuer');
  if (!(+c.exp * 1000 > Date.now())) throw new Error('expired');
  if (!c.sub) throw new Error('no_subject');
  if (c.email && String(c.email_verified) !== 'true') throw new Error('email_unverified');
  return { sub: String(c.sub), email: c.email || '', name: c.name || (c.email || '').split('@')[0] || 'Player', picture: c.picture || '' };
}

function create(opt = {}) {
  const clientId = opt.googleClientId !== undefined ? opt.googleClientId : (process.env.GOOGLE_CLIENT_ID || '');
  const adsMode = opt.adsMode || process.env.ADS_MODE || 'ssv';
  const dir = opt.dataDir || process.env.LUDO_DATA_DIR || path.join(__dirname, '..', 'data');
  const verifyGoogle = opt.verifyGoogle || ((t) => googleTokeninfo(t, clientId));
  const ssvKeys = opt.ssvKeys || null;           // test hook: { keyId: pemPublicKey }
  const file = path.join(dir, 'accounts.json');
  let db = { users: {}, sessions: {}, ssvSeen: {} };
  try { db = Object.assign(db, JSON.parse(fs.readFileSync(file, 'utf8'))); } catch (e) { }
  let timer = null;
  const flush = () => { try { fs.mkdirSync(dir, { recursive: true }); const t = file + '.tmp'; fs.writeFileSync(t, JSON.stringify(db)); fs.renameSync(t, file); } catch (e) { console.error('save failed', e.message); } };
  const persist = () => { clearTimeout(timer); timer = setTimeout(flush, 150); timer.unref && timer.unref(); };
  const nonces = new Map();                      // nonce -> {kind, device, exp, ok, tx, used}
  const hits = new Map();
  const limited = (k, n, ms) => { const t = Date.now(), a = (hits.get(k) || []).filter((x) => t - x < ms); a.push(t); hits.set(k, a); return a.length > n; };
  let keyCache = null;
  async function keyFor(id) {
    if (ssvKeys) return ssvKeys[id];
    if (!keyCache || Date.now() - keyCache.t > 6e5) { const r = await getJson(SSV_KEYS_URL); keyCache = { t: Date.now(), k: Object.fromEntries((r.json.keys || []).map((k) => [String(k.keyId), k.pem])) }; }
    return keyCache.k[id];
  }
  /* AdMob SSV: signature covers the query string up to (not including) "&signature=" */
  async function verifySsv(rawQuery) {
    const i = rawQuery.indexOf('&signature='); if (i < 0) throw new Error('unsigned');
    const msg = rawQuery.slice(0, i), q = new URLSearchParams(rawQuery), sig = q.get('signature'), kid = q.get('key_id');
    const pem = await keyFor(kid); if (!pem) throw new Error('unknown_key');
    const ok = crypto.verify('sha256', Buffer.from(msg), pem, Buffer.from(sig.replace(/-/g, '+').replace(/_/g, '/'), 'base64'));
    if (!ok) throw new Error('bad_signature'); return q;
  }
  const sweep = () => { const t = Date.now(); for (const [k, v] of nonces) if (v.exp < t) nonces.delete(k); for (const [h, s] of Object.entries(db.sessions)) if (s.exp < t) delete db.sessions[h]; };
  const sessionOf = (req) => { const m = /^Bearer\s+([\w-]{20,})$/.exec(req.headers.authorization || ''); if (!m) return null; const s = db.sessions[sha(m[1])]; return s && s.exp > Date.now() && db.users[s.sub] ? { sub: s.sub, h: sha(m[1]) } : null; };
  const body = (req) => new Promise((ok, no) => { let b = ''; req.on('data', (c) => { b += c; if (b.length > 300e3) { no(new Error('too_big')); req.destroy(); } }); req.on('end', () => { try { ok(b ? JSON.parse(b) : {}); } catch (e) { no(new Error('bad_json')); } }); req.on('error', no); });
  const send = (res, code, o) => { res.writeHead(code, { 'content-type': 'application/json', 'cache-control': 'no-store', 'access-control-allow-origin': '*', 'access-control-allow-headers': 'authorization,content-type', 'access-control-allow-methods': 'GET,POST,PUT,OPTIONS' }); res.end(JSON.stringify(o)); };

  /* returns true when the request was an /api/ account/ad route (handled), false to let the main server continue */
  async function handle(req, res, u) {
    const p = u.pathname; if (!(p === '/api/config' || p.startsWith('/api/auth/') || p === '/api/progress' || p.startsWith('/api/ads/'))) return false;
    if (req.method === 'OPTIONS') { send(res, 204, {}); return true; }
    const ip = (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim();
    try {
      sweep();
      if (p === '/api/config') { send(res, 200, { googleClientId: clientId || null, googleConfigured: !!clientId, adsMode, ssvConfigured: adsMode === 'ssv' }); return true; }
      if (p === '/api/auth/google' && req.method === 'POST') {
        if (!clientId) { send(res, 503, { ok: false, error: 'not_configured', message: 'Google Sign-In is not configured on the server (GOOGLE_CLIENT_ID).' }); return true; }
        if (limited('auth:' + ip, 12, 6e4)) { send(res, 429, { ok: false, error: 'rate_limited' }); return true; }
        const b = await body(req); if (typeof b.idToken !== 'string' || b.idToken.length < 20 || b.idToken.length > 5000) { send(res, 400, { ok: false, error: 'bad_request' }); return true; }
        let who; try { who = await verifyGoogle(b.idToken); } catch (e) { send(res, 401, { ok: false, error: 'invalid_token', message: 'Google could not verify this sign-in (' + e.message + ').' }); return true; }
        const u0 = db.users[who.sub] || (db.users[who.sub] = { created: Date.now(), progress: null, updatedAt: 0 });
        Object.assign(u0, { email: who.email, name: who.name, picture: who.picture, last: Date.now() });
        const token = crypto.randomBytes(32).toString('base64url'); db.sessions[sha(token)] = { sub: who.sub, exp: Date.now() + 90 * 864e5 }; persist();
        send(res, 200, { ok: true, token, user: { sub: who.sub, name: who.name, email: who.email, picture: who.picture }, hasProgress: !!u0.progress }); return true;
      }
      if (p === '/api/auth/logout' && req.method === 'POST') { const s = sessionOf(req); if (s) { delete db.sessions[s.h]; persist(); } send(res, 200, { ok: true }); return true; }
      if (p === '/api/progress') {
        const s = sessionOf(req); if (!s) { send(res, 401, { ok: false, error: 'not_signed_in' }); return true; }
        const usr = db.users[s.sub];
        if (req.method === 'GET') { send(res, 200, { ok: true, data: usr.progress, updatedAt: usr.updatedAt }); return true; }
        if (req.method === 'PUT') {
          const b = await body(req); if (!b.data || typeof b.data !== 'object' || typeof b.data.wallet !== 'object') { send(res, 400, { ok: false, error: 'bad_request' }); return true; }
          if (b.baseUpdatedAt && usr.updatedAt && +b.baseUpdatedAt < usr.updatedAt) { send(res, 409, { ok: false, error: 'stale', data: usr.progress, updatedAt: usr.updatedAt }); return true; }
          usr.progress = b.data; usr.updatedAt = Date.now(); persist(); send(res, 200, { ok: true, updatedAt: usr.updatedAt }); return true;
        }
      }
      if (p === '/api/ads/start' && req.method === 'POST') {
        const b = await body(req), kind = b.kind, dev = String(b.device || '').slice(0, 64);
        if (!['daily', 'weekly', 'spin'].includes(kind)) { send(res, 400, { ok: false, error: 'bad_kind' }); return true; }
        if (limited('ad:' + (dev || ip), 30, 6e4)) { send(res, 429, { ok: false, error: 'rate_limited' }); return true; }
        const nonce = crypto.randomBytes(16).toString('hex'); nonces.set(nonce, { kind, dev, exp: Date.now() + 10 * 6e4, ok: false, tx: '', used: false });
        send(res, 200, { ok: true, nonce, userId: dev.slice(0, 32), mode: adsMode }); return true;
      }
      if (p === '/api/ads/ssv' && req.method === 'GET') {           // called by Google's servers, not by the app
        let q; try { q = await verifySsv(req.url.split('?')[1] || ''); } catch (e) { send(res, 400, { ok: false, error: e.message }); return true; }
        const tx = q.get('transaction_id'), nonce = q.get('custom_data'), n = nonces.get(nonce);
        if (!tx || !n) { send(res, 200, { ok: false, error: 'unknown_nonce' }); return true; }          // Google only needs a 200
        if (db.ssvSeen[tx]) { send(res, 200, { ok: false, error: 'replay' }); return true; }
        db.ssvSeen[tx] = Date.now(); const keep = Object.entries(db.ssvSeen).sort((a, b) => b[1] - a[1]).slice(0, 5000); db.ssvSeen = Object.fromEntries(keep);
        n.ok = true; n.tx = tx; persist(); send(res, 200, { ok: true }); return true;
      }
      if (p === '/api/ads/complete' && req.method === 'POST') {      // dev/test-ads only
        if (adsMode !== 'dev') { send(res, 403, { ok: false, error: 'ssv_required' }); return true; }
        const b = await body(req), n = nonces.get(b.nonce); if (!n) { send(res, 404, { ok: false, error: 'unknown_nonce' }); return true; }
        n.ok = true; n.tx = n.tx || 'dev-' + b.nonce; send(res, 200, { ok: true }); return true;
      }
      if (p === '/api/ads/redeem' && req.method === 'POST') {
        const b = await body(req), n = nonces.get(b.nonce);
        if (!n) { send(res, 200, { ok: false, reason: 'unknown_or_expired' }); return true; }
        if (n.kind !== b.kind) { send(res, 200, { ok: false, reason: 'wrong_kind' }); return true; }
        if (n.used) { send(res, 200, { ok: false, reason: 'already_used' }); return true; }
        if (!n.ok) { send(res, 200, { ok: false, reason: 'pending' }); return true; }
        n.used = true; send(res, 200, { ok: true, proof: { verified: true, txId: n.tx, kind: n.kind } }); return true;
      }
      send(res, 404, { ok: false, error: 'not_found' }); return true;
    } catch (e) { send(res, e.message === 'too_big' ? 413 : 400, { ok: false, error: e.message }); return true; }
  }
  return { handle, flush, db: () => db, clientId, adsMode };
}
module.exports = { create, checkClaims };
