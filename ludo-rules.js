'use strict';
/* Pure Ludo rules shared by the server (authoritative) and unit tests.
   Track positions are ABSOLUTE indices on the ring, so no board coordinates are needed.
   Token state s:  -1 yard | 0..LTR track (relative to the seat's start) | LTR+1..LTR+5 home column | HOME finished. */
const BOARD6 = ['r', 'g', 'y', 'b', 'o', 'p'];
const BOARD4 = ['r', 'g', 'y', 'b'];
const SEATS4 = { 1: ['r'], 2: ['r', 'y'], 3: ['r', 'g', 'y'], 4: ['r', 'g', 'y', 'b'] };
function config(n) {
  if (n >= 5 && n <= 6) return { board: 6, n, seats: BOARD6.slice(0, n), colors: BOARD6, LAP: 78, LTR: 76, HOME: 82, off: c => (13 * BOARD6.indexOf(c) + 8) % 78 };
  if (n >= 1 && n <= 4) return { board: 4, n, seats: SEATS4[n], colors: BOARD4, LAP: 52, LTR: 50, HOME: 56, off: c => 13 * BOARD4.indexOf(c) };
  throw new Error('unsupported player count ' + n);
}
/* safe ring cells: every colour's start cell and the star 8 cells later (all colours of the board, played or not) */
function safeSet(cfg) { const s = new Set(); cfg.colors.forEach(c => { s.add(cfg.off(c)); s.add((cfg.off(c) + 8) % cfg.LAP) }); return s }
const absOf = (cfg, seat, s) => (cfg.off(seat) + s) % cfg.LAP;
function newGame(n) {
  const cfg = config(n);
  const tokens = {}; cfg.seats.forEach(c => tokens[c] = [-1, -1, -1, -1]);
  return { n, cfg, tokens, turn: 0, roll: 0, phase: 'roll', alive: cfg.seats.map(() => true), winner: null, loser: null, finished: [], quit: [], turnN: 0, caps: {} };
}
const legalTokens = (g, seat, roll) => g.tokens[seat].map((s, i) => (s < 0 ? roll === 6 : s + roll <= g.cfg.HOME) ? i : -1).filter(i => i >= 0);
const progress = (g, seat) => g.tokens[seat].reduce((a, s) => a + Math.max(0, s + 1), 0);
/* N-1 ranking: seats that finished (in order), then players still in the match (best progress first), then players who quit (last quitter first).
   The LAST entry is the single final loser. */
const activeSeats = g => g.cfg.seats.filter((s, i) => g.alive[i] && !g.finished.includes(s));
const ranking = g => g.finished.concat(activeSeats(g).sort((a, b) => progress(g, b) - progress(g, a)), g.quit.slice().reverse());
/* ends the match when at most one player is still competing; fixes winner + the one final loser */
function settle(g) {
  if (activeSeats(g).length > 1) return false;
  const order = ranking(g); g.winner = order[0]; g.loser = order.length > 1 ? order[order.length - 1] : null; g.phase = 'over'; return true;
}
/* applies a legal move; returns the event describing it. Throws on an illegal move. */
function applyMove(g, ti) {
  const seat = g.cfg.seats[g.turn], t = g.tokens[seat];
  if (g.phase !== 'move' || !legalTokens(g, seat, g.roll).includes(ti)) throw new Error('illegal move');
  const from = t[ti], to = from < 0 ? 0 : from + g.roll, caps = [];
  t[ti] = to;
  if (to <= g.cfg.LTR && !safeSet(g.cfg).has(absOf(g.cfg, seat, to))) {
    const here = absOf(g.cfg, seat, to);
    for (const o of g.cfg.seats) if (o !== seat) g.tokens[o].forEach((s, i) => { if (s >= 0 && s <= g.cfg.LTR && absOf(g.cfg, o, s) === here) { caps.push({ seat: o, ti: i, from: s }); g.tokens[o][i] = -1 } });
  }
  const homed = to === g.cfg.HOME, won = t.every(s => s === g.cfg.HOME);
  const extra = g.roll === 6 || caps.length > 0 || homed;
  let rank = 0, over = false;
  if (won) { g.finished.push(seat); rank = g.finished.length; over = settle(g) }
  return { seat, ti, from, to, roll: g.roll, caps, homed, extra: extra && !won, won, rank, over };
}
/* advance the turn pointer to the next alive seat (or keep it on an extra turn) */
function nextTurn(g, extra) {
  g.turnN++; g.roll = 0; g.phase = 'roll';
  const out = i => !g.alive[i] || g.finished.includes(g.cfg.seats[i]);
  if (!extra || out(g.turn)) { const n = g.cfg.seats.length; let i = g.turn; for (let k = 0; k < n; k++) { i = (i + 1) % n; if (!out(i)) break } g.turn = i }
  return g.turn;
}
function forfeit(g, seat) {
  const i = g.cfg.seats.indexOf(seat); g.alive[i] = false; if (!g.finished.includes(seat)) g.tokens[seat] = [-1, -1, -1, -1];
  if (!g.finished.includes(seat)) g.quit.push(seat);
  settle(g);
  return activeSeats(g).length;
}
module.exports = { config, safeSet, absOf, newGame, legalTokens, progress, ranking, activeSeats, settle, applyMove, nextTurn, forfeit, BOARD4, BOARD6 };
