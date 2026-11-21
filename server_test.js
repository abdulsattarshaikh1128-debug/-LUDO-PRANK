'use strict';
/* Integration + rules tests for the realtime server. Run: node tests/server_test.js */
const assert = require('assert'); const R = require('../server/ludo-rules.js');
process.env.LUDO_TIMERS = JSON.stringify({ skipOffline: 300, forfeit: 1500, idleRoll: 4000, noMoveDelay: 5, moveBase: 2, stepMs: 0, capMs: 0 });
const S = require('../server/ludo-server.js');
let pass = 0, fail = 0; const ok = (n, c, i) => { c ? pass++ : fail++; console.log((c ? 'PASS ' : 'FAIL ') + n + (c ? '' : ' | ' + JSON.stringify(i))) };
const sleep = ms => new Promise(r => setTimeout(r, ms));
function client(port, name, token) {
  const c = { name, ev: [], msgs: [], seat: null }; c.ws = new WebSocket('ws://127.0.0.1:' + port + '/ws');
  c.open = new Promise(r => c.ws.onopen = r);
  c.ws.onmessage = e => { const m = JSON.parse(e.data); c.msgs.push(m); if (m.t === 'welcome') { c.pid = m.pid; c.token = m.token; c.welcome = m } if (m.t === 'ev') c.ev.push(m.ev); if (m.t === 'start' || m.t === 'sync') { c.game = m.game; c.seat = m.you; c.started = true } if (m.t === 'room') c.room = m.room; if (m.t === 'mm') c.mm = m; if (m.t === 'error') c.err = m };
  c.send = o => c.ws.send(JSON.stringify(o));
  c.hello = async () => { await c.open; c.send({ t: 'hello', name, avatar: 1, frame: 0, token }); await sleep(50) };
  c.until = async (f, ms = 5000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (f()) return true; await sleep(10) } return false };
  return c;
}
(async () => {
  /* ----- rules ----- */
  const g4 = R.newGame(4), g6 = R.newGame(6);
  ok('rules: 4P ring 52 / home 56', g4.cfg.LAP === 52 && g4.cfg.HOME === 56);
  ok('rules: 6P ring 78 (6x13) / home 82', g6.cfg.LAP === 78 && g6.cfg.HOME === 82 && g6.cfg.seats.length === 6);
  ok('rules: 4P safe cells = starts + stars', [...R.safeSet(g4.cfg)].sort((a, b) => a - b).join() === '0,8,13,21,26,34,39,47');
  ok('rules: 6P has 12 safe cells (6 starts + 6 stars)', R.safeSet(g6.cfg).size === 12);
  g6.phase = 'move'; g6.roll = 3; ok('rules: yard token needs a 6', R.legalTokens(g6, 'r', 3).length === 0 && R.legalTokens(g6, 'r', 6).length === 4);
  // capture on a non-safe ring cell (6P): red at s=2 (abs 10), green at abs 10 -> green s = (10-off g=21)+78
  g6.tokens.r[0] = 1; g6.tokens.g[0] = (10 - 21 + 78) % 78; g6.roll = 1; g6.phase = 'move';
  const e = R.applyMove(g6, 0); ok('rules: capture sends token to yard & grants extra turn', e.caps.length === 1 && g6.tokens.g[0] === -1 && e.extra, e);
  const g = R.newGame(6); g.tokens.r[0] = 1; g.tokens.g[0] = (8 - 21 + 78) % 78; /* abs 8 = red start (safe)*/ g.tokens.r[0] = 7; g.roll = 1; g.phase = 'move';
  const e2 = R.applyMove(g, 0); ok('rules: no capture on a safe cell', e2.caps.length === 0 && g.tokens.g[0] === (8 - 21 + 78) % 78);
  const gh = R.newGame(6); gh.tokens.r = [82, 82, 82, 79]; gh.roll = 3; gh.phase = 'move'; const e3 = R.applyMove(gh, 3); ok('rules: 4th token home = 1st place (6P keeps playing)', e3.won && e3.rank === 1 && !e3.over && gh.phase !== 'over' && !e3.extra);
  /* N-1 ranking for every player count, driven by the real rules engine */
  for (const n of [2, 3, 4, 5, 6]) {
    const gx = R.newGame(n), seats = gx.cfg.seats, order = []; let bad = '';
    for (let k = 0; k < n - 1; k++) {
      const act = R.activeSeats(gx), who = act[(k * 7 + 1) % act.length]; gx.turn = seats.indexOf(who); gx.tokens[who] = [82 - 0, 82, 82, gx.cfg.HOME - 3].map(v => v === 82 ? gx.cfg.HOME : v); gx.roll = 3; gx.phase = 'move';
      const ev = R.applyMove(gx, 3); order.push(who);
      if (ev.rank !== k + 1) bad += ' rank' + k; if ((k < n - 2) === ev.over) bad += ' over' + k;
      if (!ev.over) { R.nextTurn(gx, false); for (let q = 0; q < 3 * n; q++) { if (order.includes(seats[gx.turn])) bad += ' finishedGotTurn'; R.nextTurn(gx, false) } }
    }
    const rk = R.ranking(gx), lo = seats.find(x => !order.includes(x));
    ok(`ranking ${n}P: ${n - 1} winners in finishing order, exactly 1 final loser, match over`, !bad && gx.phase === 'over' && rk.length === n && order.every((x, i) => rk[i] === x) && rk[n - 1] === lo && gx.loser === lo && gx.winner === order[0], { bad, rk, order, lo });
  }
  const gq = R.newGame(3); R.forfeit(gq, 'g'); ok('rules: 3P one quits -> 2 remain, match continues, quitter will be last', gq.phase !== 'over' && R.activeSeats(gq).length === 2);
  R.forfeit(gq, 'y'); ok('rules: 3P both opponents quit -> remaining player 1st, first quitter last', gq.phase === 'over' && gq.winner === 'r' && gq.loser === 'g', R.ranking(gq));
  const go = R.newGame(2); go.tokens.r[0] = 54; go.roll = 3; go.phase = 'move'; ok('rules: cannot overshoot home', !R.legalTokens(go, 'r', 3).includes(0));
  /* ----- server ----- */
  await new Promise(r => S.server.listen(0, r)); const port = S.server.address().port;
  /* quick match with 6 real clients */
  const cs = Array.from({ length: 6 }, (_, i) => client(port, 'P' + (i + 1)));
  for (const c of cs) await c.hello();
  for (let i = 0; i < 5; i++) { cs[i].send({ t: 'quick', n: 6 }); await sleep(40) }
  await cs[4].until(() => cs[4].mm && cs[4].mm.joined === 5);
  ok('matchmaking: waiting shows joined count 5/6, not started', cs[0].mm.joined === 5 && cs[0].mm.status === 'waiting' && !cs.some(c => c.started), cs[0].mm);
  cs[5].send({ t: 'quick', n: 6 });
  ok('matchmaking: 6th real player starts 6-player match', await cs[0].until(() => cs.every(c => c.started)));
  ok('matchmaking: all six get distinct seats r,g,y,b,o,p', new Set(cs.map(c => c.seat)).size === 6 && cs.every(c => c.game.players.length === 6 && c.game.seats.length === 6), cs.map(c => c.seat));
  ok('matchmaking: server never adds bots (6 humans listed)', cs[0].game.players.every(p => /^P\d$/.test(p.name)));
  /* out-of-turn + invalid actions rejected */
  const seats = cs[0].game.seats, turnSeat = seats[cs[0].game.turn], other = cs.find(c => c.seat !== turnSeat), cur = cs.find(c => c.seat === turnSeat);
  other.send({ t: 'roll' }); await sleep(100); ok('validation: roll out of turn rejected', other.err && other.err.code === 'not_your_turn' && !cs[0].ev.some(e => e.e === 'roll'));
  cur.send({ t: 'move', tok: 0 }); await sleep(100); ok('validation: move before roll rejected', cur.err && cur.err.code === 'invalid_move');
  /* play whole match randomly: honest invariants */
  let fins = [], finTurns = 0, dupTurn = 0, lastTurnN = -1, rolls = 0, moves = 0, captures = 0, rollsBad = 0, over = null;
  const sim = cs.map(c => { c.on = true; return c });
  const track = {}; seats.forEach(s => track[s] = [-1, -1, -1, -1]);
  const drive = async () => {
    const t0 = Date.now();
    while (!over && Date.now() - t0 < 120000) {
      for (const c of cs) {
        while (c.ev.length) {
          const ev = c.ev.shift();
          if (c !== cs[0]) { if (ev.e === 'roll' && ev.seat === c.seat && ev.legal.length) setTimeout(() => c.send({ t: 'move', tok: ev.legal[Math.random() * ev.legal.length | 0] }), 5); if (ev.e === 'turn' && ev.seat === c.seat) setTimeout(() => c.send({ t: 'roll' }), 5); }
          else {
            if (ev.e === 'turn') { if (ev.turnN <= lastTurnN) dupTurn++; lastTurnN = ev.turnN }
            if (ev.e === 'roll') { rolls++; if (ev.v < 1 || ev.v > 6) rollsBad++ }
            if (ev.e === 'move') { moves++; captures += ev.caps.length; track[ev.seat][ev.ti] = ev.to; ev.caps.forEach(k => track[k.seat][k.ti] = -1) }
            if (ev.e === 'over') over = ev;
            if (ev.e === 'move' && ev.won) fins.push(ev.seat);
            if (ev.e === 'turn' && fins.includes(ev.seat)) finTurns++;
            if (ev.e === 'roll' && ev.seat === c.seat && ev.legal.length) setTimeout(() => c.send({ t: 'move', tok: ev.legal[Math.random() * ev.legal.length | 0] }), 5);
            if (ev.e === 'turn' && ev.seat === c.seat) setTimeout(() => c.send({ t: 'roll' }), 5);
          }
        }
      }
      await sleep(5);
    }
  };
  // kick off first roll
  setTimeout(() => cur.send({ t: 'roll' }), 20);
  await drive();
  ok('full 6-player match: exactly 5 players finished in order, 1st finisher is winner', fins.length === 5 && over && over.ranking.slice(0, 5).join() === fins.join() && over.winner === fins[0], { fins, over });
  ok('full 6-player match: exactly one final loser (last), not a finisher, tokens incomplete', over && over.loser === over.ranking[5] && !fins.includes(over.loser) && !track[over.loser].every(s => s === 82), over && over.loser);
  ok('finished players never got another turn', finTurns === 0, finTurns);
  ok('full 6-player match reaches game over with a winner', !!over && seats.includes(over.winner), over && over.winner);
  ok('winner has all four tokens home (82)', over && track[over.winner].every(s => s === 82), over && track[over.winner]);
  ok('ranking lists all six seats, winner first', over && over.ranking.length === 6 && over.ranking[0] === over.winner);
  ok('no duplicate / out-of-order turns', dupTurn === 0, dupTurn);
  ok('all dice values 1..6, server-side', rolls > 50 && rollsBad === 0, { rolls, rollsBad });
  ok('captures happened and moves were validated', moves > 50 && captures > 0, { moves, captures });
  ok('client-side mirror of positions never exceeds home', Object.values(track).every(a => a.every(s => s >= -1 && s <= 82)));
  cs.forEach(c => c.ws.close());
  /* rooms + reconnect + disconnect */
  const host = client(port, 'Host'), f1 = client(port, 'Fri1'), f2 = client(port, 'Fri2');
  for (const c of [host, f1, f2]) await c.hello();
  host.send({ t: 'createRoom', n: 4 }); await host.until(() => host.room);
  const code = host.room.code; ok('room: unique 5-char code generated', /^[A-Z2-9]{5}$/.test(code), code);
  f1.send({ t: 'joinRoom', code: code.toLowerCase() }); f2.send({ t: 'joinRoom', code }); await f2.until(() => f2.room && f2.room.players.length === 3);
  ok('room: joined players listed with names/avatars to all', host.room.players.length === 3 && host.room.players.every(p => p.name && p.avatar === 1), host.room);
  f1.send({ t: 'joinRoom', code: 'ZZZZZ' }); await sleep(60); ok('room: unknown code returns clear error', f1.err && f1.err.code === 'no_room');
  host.send({ t: 'start' }); await sleep(80); ok('room: start refused until everyone ready', host.err && host.err.code === 'not_ready' && !host.started);
  f1.send({ t: 'ready', on: true }); f2.send({ t: 'ready', on: true }); await sleep(80);
  f1.send({ t: 'start' }); await sleep(60); ok('room: only host can start', f1.err && f1.err.code === 'not_host');
  host.send({ t: 'start' }); ok('room: host starts match with the 3 joined players', await host.until(() => host.started && f1.started && f2.started) && host.game.n === 3, host.game && host.game.n);
  const full = client(port, 'Late'); await full.hello(); full.send({ t: 'joinRoom', code }); await sleep(80); ok('room: cannot join after start', full.err && full.err.code === 'started');
  // disconnect handling: f2 drops; reconnect with token within grace
  const tok = f2.token; f2.ws.close(); await sleep(150);
  ok('disconnect: others notified (presence offline)', host.ev.some(e => e.e === 'presence' && !e.online));
  const f2b = client(port, 'Fri2', tok); await f2b.hello(); ok('reconnect: same pid & resumed flag', f2b.pid === f2.pid && f2b.welcome.resumed === true);
  ok('reconnect: receives full game sync + same seat', await f2b.until(() => f2b.started) && f2b.seat === f2.seat, f2b.seat);
  ok('reconnect: others notified (presence online)', host.ev.some(e => e.e === 'presence' && e.online));
  // offline turn skipped, then forfeit
  f1.ws.close(); await sleep(60); const hostSeat = host.seat;
  ok('disconnect: offline player forfeits after grace, game continues for others', await host.until(() => host.ev.some(e => e.e === 'forfeit'), 5000));
  host.ws.close(); f2b.ws.close(); full.ws.close();
  /* leave room before start + host handover */
  const a = client(port, 'A'), b = client(port, 'B'); await a.hello(); await b.hello(); a.send({ t: 'createRoom', n: 2 }); await a.until(() => a.room); b.send({ t: 'joinRoom', code: a.room.code }); await b.until(() => b.room && b.room.players.length === 2);
  a.send({ t: 'leave' }); await b.until(() => b.room.players.length === 1); ok('leave: member leaves lobby, host handed over', b.room.host === b.pid, b.room);
  /* quick match 2 players + cancel */
  const q1 = client(port, 'Q1'), q2 = client(port, 'Q2'); await q1.hello(); await q2.hello(); q1.send({ t: 'quick', n: 2 }); await q1.until(() => q1.mm && q1.mm.joined === 1);
  q1.send({ t: 'cancelQuick' }); await sleep(60); ok('matchmaking: cancel leaves queue', q1.mm.cancelled === true);
  q1.send({ t: 'quick', n: 2 }); q2.send({ t: 'quick', n: 2 }); ok('matchmaking: two real players start a 2-player match', await q1.until(() => q1.started && q2.started) && q1.game.n === 2 && q1.game.seats.join() === 'r,y');
  console.log(`\n${pass}/${pass + fail} passed`); process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1) });
