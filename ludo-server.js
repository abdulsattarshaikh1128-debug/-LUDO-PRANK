#!/usr/bin/env node
'use strict';
/* LUDO PRANK realtime server: zero dependencies (Node >= 18). WebSocket (RFC 6455) + tiny HTTP.
   - quick match queues for 2..6 players (real connected people only, never bots)
   - private rooms with codes, ready state, host start, leave, host hand-over
   - server-authoritative game: the server rolls the dice and validates every move
   - reconnection: a session token lets a dropped player resume their seat
   Run:  node server/ludo-server.js        (PORT env, default 8787)
   State is in memory (single instance). See server/README-ONLINE.md. */
const http = require('http'), crypto = require('crypto'), fs = require('fs'), path = require('path');
const R = require('./ludo-rules.js');
const PORT = +process.env.PORT || 8787;
const T = Object.assign({ lobbyGrace: 90000, roomTtl: 45 * 60000, tomb: 24 * 3600000, skipOffline: 8000, forfeit: 60000, idleRoll: 40000, noMoveDelay: 1400, moveBase: 500, stepMs: 230, capMs: 3200 }, JSON.parse(process.env.LUDO_TIMERS || '{}'));
const sessions = new Map();   // token -> player
const players = new Map();    // pid -> player
const rooms = new Map();      // code -> room
const tombs = new Map();      // code -> { reason: 'closed'|'expired', t }  (so a dead invitation says why)
const PUBLIC_URL = (process.env.PUBLIC_URL || '').replace(/\/+$/, '');   // e.g. https://ludo.example.com  (recommended behind TLS)
const ANDROID_PACKAGE = process.env.ANDROID_PACKAGE || '', ANDROID_SHA256 = (process.env.ANDROID_SHA256 || '').split(',').filter(Boolean), PLAY_URL = process.env.PLAY_STORE_URL || '';
const queues = { 2: [], 3: [], 4: [], 5: [], 6: [] };
const rid = n => crypto.randomBytes(n).toString('hex');
const clean = (s, d) => String(s == null ? d : s).replace(/[<>&"']/g, '').slice(0, 12) || d;
const send = (p, m) => { if (p.ws && p.ws.writable && !p.ws.destroyed) wsSend(p.ws, JSON.stringify(m)) };
const TIMERS = [0, 20, 40, 60, 90];
const seatsFor = n => R.config(n).seats;
const roomPublic = r => ({ code: r.code, n: r.n, host: r.host, started: !!r.game, hasPw: !!r.hash, sharePw: !!r.sharePw, timer: r.timerS || 0, seats: seatsFor(r.n), players: r.members.map(pl => Object.assign(pub(pl, r), { color: r.picks.get(pl.pid) })) });
const hashPw = (pw, salt) => crypto.scryptSync(String(pw), salt, 32);
const okPw = (r, pw) => { if (!r.hash) return true; if (typeof pw !== 'string' || !pw) return false; const h = hashPw(pw, r.salt); return h.length === r.hash.length && crypto.timingSafeEqual(h, r.hash) };
const setPw = (r, pw) => { if (pw) { r.salt = crypto.randomBytes(16); r.hash = hashPw(pw, r.salt) } else { r.salt = null; r.hash = null } };
const cleanPw = v => { if (v == null || v === '') return ''; const s = String(v); return s.length <= 32 ? s : null };
function normPicks(r) { const seats = seatsFor(r.n), used = new Set(); r.members.forEach(m => { const c = r.picks.get(m.pid); if (c && seats.includes(c) && !used.has(c)) used.add(c); else r.picks.delete(m.pid) }); r.members.forEach(m => { if (!r.picks.has(m.pid)) { const c = seats.find(x => !used.has(x)); r.picks.set(m.pid, c); used.add(c) } }) }
function closeRoom(r, reason) { r.members.forEach(pl => { if (pl.room === r.code) { pl.room = null; clearTimeout(pl.lobbyT); send(pl, { t: 'closed', reason }) } }); clearTimeout(r.idleT); clearTimeout(r.skipT); rooms.delete(r.code); tombs.set(r.code, { reason, t: Date.now() }) }
const peek = code => { const c = String(code || '').toUpperCase().trim(), r = rooms.get(c); if (r) { const h = r.members.find(x => x.pid === r.host); return { code: c, found: true, hasPw: !!r.hash, n: r.n, count: r.members.length, started: !!r.game, host: h ? h.name : '', full: r.members.length >= r.n } } const tb = tombs.get(c); return { code: c, found: false, reason: tb ? tb.reason : 'no_room' } };
setInterval(() => { const now = Date.now(); for (const r of [...rooms.values()]) { if (!r.game && now - r.created > T.roomTtl) closeRoom(r, 'expired') } for (const [c, v] of tombs) if (now - v.t > T.tomb) tombs.delete(c) }, 15000).unref();
const pub = (p, r) => ({ pid: p.pid, name: p.name, avatar: p.avatar, frame: p.frame, ready: !!(r && r.ready.has(p.pid)), online: !!p.online, seat: r && r.game ? r.game.cfg.seats[r.order.indexOf(p.pid)] : undefined });

/* ---------- WebSocket framing ---------- */
function wsSend(sock, str) {
  const b = Buffer.from(str), l = b.length; let h;
  if (l < 126) h = Buffer.from([0x81, l]); else if (l < 65536) { h = Buffer.alloc(4); h[0] = 0x81; h[1] = 126; h.writeUInt16BE(l, 2) } else { h = Buffer.alloc(10); h[0] = 0x81; h[1] = 127; h.writeBigUInt64BE(BigInt(l), 2) }
  try { sock.write(Buffer.concat([h, b])) } catch (e) { }
}
function wsParse(sock, onMsg, onClose) {
  let buf = Buffer.alloc(0), frag = null;
  sock.on('data', d => {
    buf = Buffer.concat([buf, d]);
    for (;;) {
      if (buf.length < 2) return;
      const op = buf[0] & 15, fin = buf[0] & 128, masked = buf[1] & 128; let len = buf[1] & 127, o = 2;
      if (len === 126) { if (buf.length < 4) return; len = buf.readUInt16BE(2); o = 4 } else if (len === 127) { if (buf.length < 10) return; len = Number(buf.readBigUInt64BE(2)); o = 10 }
      if (len > 8192) { sock.destroy(); return }
      if (!masked) { sock.destroy(); return }
      if (buf.length < o + 4 + len) return;
      const mask = buf.slice(o, o + 4), data = Buffer.from(buf.slice(o + 4, o + 4 + len)); for (let i = 0; i < len; i++) data[i] ^= mask[i & 3];
      buf = buf.slice(o + 4 + len);
      if (op === 8) { try { sock.write(Buffer.from([0x88, 0])) } catch (e) { } sock.end(); return }
      if (op === 9) { try { sock.write(Buffer.concat([Buffer.from([0x8a, data.length]), data])) } catch (e) { } continue }
      if (op === 10) continue;
      if (op === 1 || op === 2) frag = data; else if (op === 0 && frag) frag = Buffer.concat([frag, data]);
      if (fin && frag) { const s = frag.toString(); frag = null; try { onMsg(JSON.parse(s)) } catch (e) { onMsg({ t: '_bad' }) } }
    }
  });
  sock.on('close', onClose); sock.on('error', () => { });
}

/* ---------- http ---------- */
const baseOf = req => PUBLIC_URL || ((req.headers['x-forwarded-proto'] || 'http').split(',')[0].trim() + '://' + (req.headers['x-forwarded-host'] || req.headers.host || 'localhost'));
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function landing(code, pw, base) {
  const st = peek(code), q = '?room=' + encodeURIComponent(code) + (pw ? '&p=' + encodeURIComponent(pw) : ''), web = base + '/' + q, host = base.replace(/^https?:\/\//, '');
  const intent = ANDROID_PACKAGE ? 'intent://' + host + '/join/' + encodeURIComponent(code) + (pw ? '?p=' + encodeURIComponent(pw) : '') + '#Intent;scheme=https;package=' + ANDROID_PACKAGE + ';S.browser_fallback_url=' + encodeURIComponent(web) + ';end' : 'ludoprank://join/' + encodeURIComponent(code) + (pw ? '?p=' + encodeURIComponent(pw) : '');
  const msg = st.found ? (st.started ? 'This match has already started.' : st.full ? 'This room is full right now.' : 'Room ' + esc(code) + ' is waiting for you' + (st.host ? ' - host: ' + esc(st.host) : '') + ' (' + st.count + '/' + st.n + ' players).') : st.reason === 'expired' ? 'This invitation has expired. Ask your friend for a new one.' : st.reason === 'closed' ? 'This room was closed by the host.' : 'Room not found. Check the code or ask your friend for a new invitation.';
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Join LUDO PRANK room ${esc(code)}</title><meta name="robots" content="noindex">
<style>body{margin:0;font-family:system-ui,sans-serif;background:linear-gradient(#1b4fd1,#0a2a78);color:#fff;min-height:100vh;display:grid;place-items:center}main{width:min(92vw,420px);background:#fff;color:#0b2a6a;border-radius:20px;padding:22px;text-align:center;box-shadow:0 10px 30px #0006}h1{margin:0 0 4px;font-size:26px}.code{font-size:40px;letter-spacing:6px;font-weight:800;margin:8px 0}a.b{display:block;margin:10px 0;padding:14px;border-radius:14px;background:#f5b800;color:#2a1b00;font-weight:800;text-decoration:none}a.b.g{background:#e7eefc;color:#0b2a6a}ol{text-align:left;font-size:14px;padding-left:20px}small{color:#456}</style></head><body><main>
<h1>LUDO PRANK</h1><div class="code">${esc(code)}</div><p>${msg}</p>
${st.found && !st.started && !st.full ? `<a class="b" href="${esc(intent)}">Open in the LUDO PRANK app</a><a class="b g" href="${esc(web)}">Play in your browser instead</a>${PLAY_URL ? `<a class="b g" href="${esc(PLAY_URL)}">Get the app</a>` : ''}
<ol><li>Have the app? Tap <b>Open in the LUDO PRANK app</b>.</li><li>No app yet? Install it, then open this link again - or tap <b>Play in your browser</b>.</li><li>${pw ? 'The room password is already filled in.' : 'If the room has a password, ask the host for it.'}</li></ol>` : `<a class="b g" href="${esc(base)}/">Open LUDO PRANK</a>`}
<small>Real-time online Ludo with friends</small></main></body></html>`;
}
const ACCOUNTS = require('./account-api').create();
const server = http.createServer((req, res) => {
  if (req.url.startsWith('/api/') && !req.url.startsWith('/api/room/')) { const uu = new URL(req.url, 'http://x'); return void ACCOUNTS.handle(req, res, uu).then((h) => { if (!h) { res.writeHead(404); res.end('not found'); } }); }
  if (req.url === '/health') { res.writeHead(200, { 'content-type': 'application/json' }); return res.end(JSON.stringify({ ok: true, players: players.size, rooms: rooms.size, queues: Object.fromEntries(Object.entries(queues).map(([k, v]) => [k, v.length])) })) }
  const u = new URL(req.url, 'http://x'), base = baseOf(req);
  if (u.pathname === '/.well-known/assetlinks.json') { res.writeHead(200, { 'content-type': 'application/json' }); return res.end(JSON.stringify(ANDROID_PACKAGE && ANDROID_SHA256.length ? [{ relation: ['delegate_permission/common.handle_all_urls'], target: { namespace: 'android_app', package_name: ANDROID_PACKAGE, sha256_cert_fingerprints: ANDROID_SHA256 } }] : [])) }
  if (u.pathname.startsWith('/api/room/')) { res.writeHead(200, { 'content-type': 'application/json', 'access-control-allow-origin': '*', 'cache-control': 'no-store' }); return res.end(JSON.stringify(peek(decodeURIComponent(u.pathname.slice(10))))) }
  if (u.pathname.startsWith('/join/')) { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' }); return res.end(landing(decodeURIComponent(u.pathname.slice(6)).toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8), u.searchParams.get('p') || '', base)) }
  const f = path.join(__dirname, '..', 'ludo-prank-v2.html');
  if ((req.url === '/' || req.url.startsWith('/?')) && fs.existsSync(f)) { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); return res.end(fs.readFileSync(f)) }
  res.writeHead(404); res.end('not found');
});
server.on('upgrade', (req, sock) => {
  if (req.url.split('?')[0] !== '/ws' || !req.headers['sec-websocket-key']) { sock.destroy(); return }
  const acc = crypto.createHash('sha1').update(req.headers['sec-websocket-key'] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
  sock.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + acc + '\r\n\r\n');
  sock.setNoDelay(true);
  const conn = { ws: sock, p: null, rate: [], pub: baseOf(req) };
  wsParse(sock, m => handle(conn, m), () => drop(conn));
});

/* ---------- sessions ---------- */
function handle(conn, m) {
  const now = Date.now(); conn.rate = conn.rate.filter(t => now - t < 2000); if (conn.rate.push(now) > 40) return;
  if (m.t === 'hello') {
    let p = m.token && sessions.get(m.token);
    if (p) { if (p.ws && p.ws !== conn.ws) { try { p.ws.destroy() } catch (e) { } } p.ws = conn.ws; p.online = true; clearTimeout(p.offT); clearTimeout(p.lobbyT); p.name = clean(m.name, p.name); }
    else { p = { pid: rid(4), token: rid(16), name: clean(m.name, 'Player'), avatar: m.avatar | 0, frame: m.frame | 0, ws: conn.ws, online: true, room: null, q: 0 }; sessions.set(p.token, p); players.set(p.pid, p) }
    p.avatar = m.avatar | 0; p.frame = m.frame | 0; conn.p = p;
    send(p, { t: 'welcome', pub: conn.pub, pid: p.pid, token: p.token, resumed: !!(m.token && sessions.get(m.token) === p && p.room) });
    if (p.room) resume(p); else if (p.q) qStatus(p.q);
    return;
  }
  const p = conn.p; if (!p) return send({ ws: conn.ws }, { t: 'error', code: 'nohello' });
  const err = (code, msg) => send(p, { t: 'error', code, msg });
  switch (m.t) {
    case 'ping': return send(p, { t: 'pong', ts: m.ts });
    case 'quick': { const n = m.n | 0; if (!(n >= 2 && n <= 6)) return err('bad_n'); leaveAll(p); queues[n].push(p); p.q = n; qStatus(n); return qTry(n) }
    case 'cancelQuick': { leaveQueue(p); return send(p, { t: 'mm', cancelled: true }) }
    case 'createRoom': {
      const n = m.n | 0; if (!(n >= 2 && n <= 6)) return err('bad_n', 'Choose 2 to 6 players'); const pw = cleanPw(m.pw); if (pw === null) return err('bad_pw', 'Password can be at most 32 characters');
      const tS = TIMERS.includes(m.timer | 0) ? m.timer | 0 : 0;
      leaveAll(p); const code = mkCode(); const r = { code, n, host: p.pid, members: [p], ready: new Set([p.pid]), game: null, order: [], picks: new Map(), created: Date.now(), timerS: tS, idle: tS ? tS * 1000 : 0, sharePw: !!m.sharePw && !!pw, failN: 0 };
      setPw(r, pw); normPicks(r); rooms.set(code, r); p.room = code; return roomCast(r) }
    case 'peek': return send(p, Object.assign({ t: 'peek' }, peek(m.code)));
    case 'joinRoom': {
      const code = String(m.code || '').toUpperCase().trim(), r = rooms.get(code);
      if (!r) { const tb = tombs.get(code); return err(tb ? tb.reason : 'no_room', tb ? (tb.reason === 'expired' ? 'This invitation has expired' : 'This room was closed') : 'Room not found') }
      if (r.members.includes(p)) return roomCast(r);
      const now = Date.now(); if ((p.lock && p.lock > now) || (r.lockUntil && r.lockUntil > now)) return err('rate_limited', 'Too many wrong passwords - wait a moment');
      if (r.hash) { const pw = m.pw == null ? '' : String(m.pw); if (!pw) return err('need_password', 'This room needs a password'); if (!okPw(r, pw)) { p.fails = (p.fails || 0) + 1; r.failN++; if (p.fails >= 5) { p.lock = now + 30000; p.fails = 0 } if (r.failN >= 25) { r.lockUntil = now + 60000; r.failN = 0 } return err('bad_password', 'Incorrect password') } p.fails = 0 }
      if (r.game) return err('started', 'Match already started'); if (r.members.length >= r.n) return err('full', 'Room is full');
      leaveAll(p); r.members.push(p); p.room = r.code; normPicks(r); return roomCast(r) }
    case 'config': {
      const r = rooms.get(p.room); if (!r || r.game) return; if (r.host !== p.pid) return err('not_host', 'Only the host can change room settings');
      if (m.n != null) { const n = m.n | 0; if (!(n >= 2 && n <= 6) || n < r.members.length) return err('bad_n', 'Players: 2-6, not fewer than already joined'); r.n = n }
      if (m.timer != null) { const t = m.timer | 0; if (!TIMERS.includes(t)) return err('bad_timer'); r.timerS = t; r.idle = t ? t * 1000 : 0 }
      if (m.pw !== undefined) { const pw = cleanPw(m.pw); if (pw === null) return err('bad_pw', 'Password can be at most 32 characters'); setPw(r, pw); if (!pw) r.sharePw = false }
      if (m.sharePw != null) r.sharePw = !!m.sharePw && !!r.hash;
      normPicks(r); return roomCast(r) }
    case 'color': {
      const r = rooms.get(p.room); if (!r || r.game) return; const tgt = m.pid && m.pid !== p.pid ? r.members.find(x => x.pid === m.pid) : p; if (!tgt) return; if (tgt !== p && r.host !== p.pid) return err('not_host', 'Only the host can change other players');
      const c = String(m.c || ''); if (!seatsFor(r.n).includes(c)) return err('bad_color'); const holder = r.members.find(x => x !== tgt && r.picks.get(x.pid) === c); if (holder) return err('color_taken', 'That colour is taken'); r.picks.set(tgt.pid, c); return roomCast(r) }
    case 'kick': {
      const r = rooms.get(p.room); if (!r || r.game) return; if (r.host !== p.pid) return err('not_host', 'Only the host can remove players'); const v = r.members.find(x => x.pid === m.pid); if (!v || v === p) return;
      r.members = r.members.filter(x => x !== v); r.ready.delete(v.pid); r.picks.delete(v.pid); v.room = null; clearTimeout(v.lobbyT); send(v, { t: 'kicked' }); normPicks(r); return roomCast(r) }
    case 'close': { const r = rooms.get(p.room); if (!r || r.game) return; if (r.host !== p.pid) return err('not_host', 'Only the host can close the room'); return closeRoom(r, 'closed') }
    case 'ready': { const r = rooms.get(p.room); if (!r || r.game || p.pid === r.host) return; m.on ? r.ready.add(p.pid) : r.ready.delete(p.pid); return roomCast(r) }
    case 'start': { const r = rooms.get(p.room); if (!r) return; if (r.host !== p.pid) return err('not_host', 'Only the host can start'); if (r.game) return; if (r.members.length < 2) return err('few', 'Need at least 2 players'); if (!r.members.every(x => r.ready.has(x.pid) && x.online)) return err('not_ready', 'Everyone must be ready and online'); const mem = r.members.slice(); r.n = mem.length; const rank = c => { const i = ['r', 'g', 'y', 'b', 'o', 'p'].indexOf(c); return i < 0 ? 9 : i }; mem.sort((a, b) => rank(r.picks.get(a.pid)) - rank(r.picks.get(b.pid))); return startGame(r, mem) }
    case 'leave': return leaveAll(p, true);
    case 'roll': return gRoll(p);
    case 'move': return gMove(p, m.tok | 0);
  }
}
function drop(conn) {
  const p = conn.p; if (!p || p.ws !== conn.ws) return;
  p.online = false; p.ws = null; leaveQueue(p);
  const r = rooms.get(p.room);
  if (r && !r.game) { /* lobby: keep the seat while the phone is in WhatsApp / loses signal; remove only after the grace period */
    roomCast(r); clearTimeout(p.lobbyT);
    p.lobbyT = setTimeout(() => { if (p.online || p.room !== r.code || !rooms.has(r.code) || r.game) return; r.members = r.members.filter(x => x !== p); r.ready.delete(p.pid); r.picks.delete(p.pid); p.room = null; if (!r.members.length) { rooms.delete(r.code); tombs.set(r.code, { reason: 'closed', t: Date.now() }) } else { if (r.host === p.pid) { const nh = r.members.find(x => x.online) || r.members[0]; r.host = nh.pid; r.ready.add(nh.pid) } normPicks(r); roomCast(r) } }, T.lobbyGrace); return }
  if (r && r.game) { gCast(r, { e: 'presence', seat: seatOf(r, p), online: false }); p.offT = setTimeout(() => gForfeit(r, p), T.forfeit); if (r.game.cfg.seats[r.game.turn] === seatOf(r, p)) schedOffline(r) }
  else p.offT = setTimeout(() => { sessions.delete(p.token); players.delete(p.pid) }, 120000);
}
function resume(p) {
  const r = rooms.get(p.room); if (!r) { p.room = null; return }
  if (!r.game) return roomCast(r);
  gCast(r, { e: 'presence', seat: seatOf(r, p), online: true });
  send(p, { t: 'sync', room: roomPublic(r), game: snapshot(r), you: seatOf(r, p) });
  if (r.timer === 'off' && r.game.cfg.seats[r.game.turn] === seatOf(r, p)) { clearTimeout(r.skipT) }
}
function leaveQueue(p) { if (p.q) { const n = p.q; queues[n] = queues[n].filter(x => x !== p); p.q = 0; qStatus(n) } }
function leaveAll(p, explicit) {
  leaveQueue(p);
  const r = rooms.get(p.room); if (!r) { if (explicit) send(p, { t: 'left' }); return }
  p.room = null; clearTimeout(p.offT);
  if (r.game) { gForfeit(r, p, true); } else { clearTimeout(p.lobbyT); r.members = r.members.filter(x => x !== p); r.ready.delete(p.pid); r.picks.delete(p.pid); if (!r.members.length) { rooms.delete(r.code); tombs.set(r.code, { reason: 'closed', t: Date.now() }) } else { if (r.host === p.pid) { r.host = r.members[0].pid; r.ready.add(r.host) } normPicks(r); roomCast(r) } }
  send(p, { t: 'left' });
}
const mkCode = () => { for (;;) { const c = Array.from({ length: 5 }, () => 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'[crypto.randomInt(32)]).join(''); if (!rooms.has(c) && !tombs.has(c)) return c } };
function roomCast(r) { const pu = roomPublic(r); r.members.forEach(pl => send(pl, { t: 'room', room: pu, you: pl.pid })) }

/* ---------- matchmaking ---------- */
function qStatus(n) { queues[n].forEach(pl => send(pl, { t: 'mm', n, joined: queues[n].length, players: queues[n].map(x => pub(x)), status: queues[n].length >= n ? 'starting' : 'waiting' })) }
function qTry(n) {
  const q = queues[n].filter(x => x.online); queues[n] = q;
  if (q.length >= n) { const grp = q.splice(0, n); grp.forEach(x => x.q = 0); qStatus(n); const code = mkCode(); const r = { code, n, host: grp[0].pid, members: grp, ready: new Set(grp.map(x => x.pid)), game: null, order: [], picks: new Map(), created: Date.now(), quick: true }; rooms.set(code, r); grp.forEach(x => x.room = code); startGame(r, grp) }
}

/* ---------- game ---------- */
const seatOf = (r, p) => r.game ? r.game.cfg.seats[r.order.indexOf(p.pid)] : null;
const gCast = (r, ev) => r.members.forEach(pl => send(pl, { t: 'ev', ev }));
const snapshot = r => { const g = r.game; return { n: g.n, seats: g.cfg.seats, tokens: g.tokens, turn: g.turn, roll: g.roll, phase: g.phase, alive: g.alive, winner: g.winner, loser: g.loser, finished: g.finished, quit: g.quit, turnN: g.turnN, players: r.members.map(pl => ({ ...pub(pl, r), seat: seatOf(r, pl) })) } };
function startGame(r, members) {
  r.order = members.map(x => x.pid); r.members = members.slice(); r.game = R.newGame(members.length); r.game.cfg.seats.forEach(() => 0);
  r.members.forEach(pl => send(pl, { t: 'start', room: roomPublic(r), game: snapshot(r), you: seatOf(r, pl) }));
  armIdle(r);
}
function armIdle(r) { clearTimeout(r.idleT); clearTimeout(r.skipT); if (!r.game || r.game.phase === 'over') return; const g = r.game, seat = g.cfg.seats[g.turn], pl = playerAt(r, seat); if (pl && !pl.online) return schedOffline(r); r.idleT = setTimeout(() => autoPlay(r, seat), r.idle || T.idleRoll) }
const playerAt = (r, seat) => { const i = r.game.cfg.seats.indexOf(seat); return r.members.find(x => x.pid === r.order[i]) };
function schedOffline(r) { clearTimeout(r.skipT); const g = r.game, turnN = g.turnN; r.skipT = setTimeout(() => { if (!r.game || r.game.turnN !== turnN || r.game.phase === 'over') return; const seat = g.cfg.seats[g.turn], pl = playerAt(r, seat); if (pl && !pl.online) { gCast(r, { e: 'skip', seat, reason: 'offline' }); advance(r, false) } }, T.skipOffline) }
function autoPlay(r, seat) { const g = r.game; if (!g || g.phase === 'over' || g.cfg.seats[g.turn] !== seat) return; const pl = playerAt(r, seat); pl.idleMiss = (pl.idleMiss || 0) + 1; if (g.phase === 'roll') doRoll(r); if (g.phase === 'move') { const l = R.legalTokens(g, seat, g.roll); doMove(r, l[0]) } }
function gRoll(p) { const r = rooms.get(p.room); if (!r || !r.game) return; const g = r.game; if (g.phase !== 'roll' || g.cfg.seats[g.turn] !== seatOf(r, p)) return send(p, { t: 'error', code: 'not_your_turn' }); p.idleMiss = 0; doRoll(r) }
function doRoll(r) {
  const g = r.game, seat = g.cfg.seats[g.turn]; clearTimeout(r.idleT);
  g.roll = crypto.randomInt(1, 7); const legal = R.legalTokens(g, seat, g.roll);
  g.phase = legal.length ? 'move' : 'wait';
  gCast(r, { e: 'roll', seat, v: g.roll, legal, turnN: g.turnN });
  if (!legal.length) { const tn = g.turnN; setTimeout(() => { if (r.game && r.game.turnN === tn) advance(r, false) }, T.noMoveDelay) } else armIdle2(r)
}
function armIdle2(r) { clearTimeout(r.idleT); const g = r.game, seat = g.cfg.seats[g.turn], tn = g.turnN; r.idleT = setTimeout(() => { if (r.game && r.game.turnN === tn) autoPlay(r, seat) }, r.idle || T.idleRoll) }
function gMove(p, ti) { const r = rooms.get(p.room); if (!r || !r.game) return; const g = r.game; if (g.phase !== 'move' || g.cfg.seats[g.turn] !== seatOf(r, p)) return send(p, { t: 'error', code: 'invalid_move' }); try { doMove(r, ti) } catch (e) { send(p, { t: 'error', code: 'invalid_move' }) } }
function doMove(r, ti) {
  const g = r.game; clearTimeout(r.idleT); const ev = R.applyMove(g, ti); ev.e = 'move'; ev.turnN = g.turnN;
  g.phase = ev.over ? 'over' : 'busy'; gCast(r, ev);
  if (ev.over) return finish(r);
  const steps = ev.from < 0 ? 2 : ev.roll, dly = T.moveBase + steps * T.stepMs + (ev.caps.length ? T.capMs : 0), tn = g.turnN;
  setTimeout(() => { if (r.game && r.game.turnN === tn && r.game.phase === 'busy') advance(r, ev.extra) }, dly);
}
function advance(r, extra) {
  const g = r.game; if (g.phase === 'over') return; R.nextTurn(g, extra); gCast(r, { e: 'turn', turn: g.turn, seat: g.cfg.seats[g.turn], turnN: g.turnN }); armIdle(r);
}
function finish(r) {
  const g = r.game; clearTimeout(r.idleT); clearTimeout(r.skipT);
  gCast(r, { e: 'over', winner: g.winner, loser: g.loser, ranking: R.ranking(g), progress: Object.fromEntries(g.cfg.seats.map(s => [s, R.progress(g, s)])) });
  setTimeout(() => { r.members.forEach(pl => { if (pl.room === r.code) pl.room = null }); rooms.delete(r.code) }, 60000);
}
function gForfeit(r, p, left) {
  const g = r.game; if (!g || g.phase === 'over') return; const seat = seatOf(r, p); if (!seat) return; const i = g.cfg.seats.indexOf(seat); if (!g.alive[i]) return;
  const wasTurn = g.cfg.seats[g.turn] === seat; R.forfeit(g, seat);
  gCast(r, { e: 'forfeit', seat, left: !!left });
  if (g.phase === 'over') return finish(r);
  if (wasTurn) { g.turnN++; g.phase = 'busy'; setTimeout(() => advance(r, false), 400) }
}
if (require.main === module) server.listen(PORT, () => console.log('LUDO PRANK server on :' + PORT));
module.exports = { server, T, rooms, queues, sessions, tombs };
