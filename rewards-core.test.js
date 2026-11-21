const test = require('node:test'), assert = require('node:assert'), RW = require('./rewards-core.js');
const D = 864e5, T0 = Date.UTC(2026, 10, 16, 10); // Mon 2026-11-16 10:00 UTC
const seq = (...v) => { let i = 0; return () => v[i++ % v.length]; };
test('daily: one claim per day, correct reward per day, duplicate blocked', () => {
  const s = RW.newState(), c0 = s.coins;
  const a = RW.claimDaily(s, T0); assert.ok(a.ok); assert.equal(s.coins, c0 + 150);
  assert.equal(RW.claimDaily(s, T0 + 3600e3).reason, 'already_claimed');
  assert.equal(RW.claimDaily(s, T0).reason, 'already_claimed');
  const b = RW.claimDaily(s, T0 + D); assert.ok(b.ok); assert.equal(s.gems, 35);
  assert.ok(RW.claimDaily(s, T0 + 2 * D).ok); assert.equal(s.tickets, 1);
  assert.equal(s.tx.filter((t) => t.src === 'daily').length, 3);
});
test('daily: day 7 premium, then a fresh cycle with a new collection', () => {
  const s = RW.newState(); let last; for (let i = 0; i < 7; i++) last = RW.claimDaily(s, T0 + i * D);
  assert.ok(last.prem); assert.ok(s.inv.includes('frame:6')); assert.equal(RW.dailyView(s, T0 + 6 * D + 1).items.every((x) => x.status === 'claimed'), true);
  const v = RW.dailyView(s, T0 + 7 * D); assert.equal(v.name, 'Festival Week'); assert.equal(v.items[0].status, 'available');
  const n = RW.claimDaily(s, T0 + 7 * D); assert.ok(n.ok); assert.equal(n.cycle, 1); assert.equal(RW.dailyView(s, T0 + 7 * D).items[0].status, 'claimed');
});
test('daily: clock rolled back cannot reopen a claimed day; missed days do not break progress', () => {
  const s = RW.newState(); RW.claimDaily(s, T0 + D); assert.equal(RW.claimDaily(s, T0).reason, 'already_claimed'); assert.equal(RW.claimDaily(s, T0 - 5 * D).reason, 'already_claimed');
  assert.ok(RW.claimDaily(s, T0 + 5 * D).ok); assert.equal(s.daily.day, 2);
});
test('daily: owned cosmetic becomes coins, stated exactly', () => {
  const s = RW.newState(); s.inv.push('avatar:12'); s.daily.day = 3; const c = s.coins; const r = RW.claimDaily(s, T0);
  assert.equal(r.reward.coins, 150); assert.equal(s.coins, c + 150); assert.match(r.reward.text, /already own/);
});
test('weekly: progress, claim, duplicate block, exclusive tier, weekly reset', () => {
  const s = RW.newState(); RW.tick(s, T0); assert.equal(RW.weekView(s, T0).tiers[0].status, 'locked');
  assert.equal(RW.claimWeekly(s, T0, 0).reason, 'locked');
  for (let i = 0; i < 3; i++) RW.claimDaily(s, T0 + i * D); assert.equal(RW.weekView(s, T0 + 2 * D).tiers[0].status, 'available');
  const c = s.coins, g = s.gems, r0 = RW.weekView(s, T0 + 2 * D).tiers[0].r; assert.ok(RW.claimWeekly(s, T0 + 2 * D, 0).ok); assert.equal(s.coins - c, r0.c || 0); assert.equal(s.gems - g, r0.g || 0);
  assert.equal(RW.claimWeekly(s, T0 + 2 * D, 0).reason, 'already_claimed');
  RW.progress(s, T0 + 2 * D, 'games', 5); RW.progress(s, T0 + 2 * D, 'wins', 2); RW.progress(s, T0 + 2 * D, 'caps', 10);
  assert.equal(RW.claimWeekly(s, T0 + 2 * D, 4).reason, 'locked'); for (const i of [1, 2, 3]) assert.ok(RW.claimWeekly(s, T0 + 2 * D, i).ok);
  const top = RW.weekView(s, T0 + 2 * D).tiers[4].r.item; assert.ok(RW.claimWeekly(s, T0 + 2 * D, 4).ok); assert.ok(s.inv.includes(top));
  const next = T0 + 7 * D; assert.notEqual(RW.wk(T0), RW.wk(next)); const v = RW.weekView(s, next);
  assert.equal(v.tiers.every((t) => t.status === 'locked'), true); assert.equal(s.week.prog.days, 0); assert.equal(v.name, RW.WEEKLY[+RW.wk(next).split('-W')[1] % 3].name); assert.notEqual(v.name, RW.weekView(RW.newState(), T0).name);
  assert.equal(RW.wk(Date.UTC(2026, 10, 22, 23, 59)), RW.wk(T0)); assert.notEqual(RW.wk(Date.UTC(2026, 10, 23, 0, 0)), RW.wk(T0));
});
test('weekly: claim keys survive a clock rollback inside the same week', () => {
  const s = RW.newState(); for (let i = 0; i < 3; i++) RW.claimDaily(s, T0 + i * D); RW.claimWeekly(s, T0 + 2 * D, 0); assert.equal(RW.claimWeekly(s, T0, 0).reason, 'already_claimed');
});
test('spin: 3 free, tickets after free, 6/day cap, daily reset', () => {
  const s = RW.newState(), r = seq(0.1, 0.5, 0.9); s.tickets = 5;
  for (let i = 0; i < 3; i++) assert.ok(RW.spin(s, T0, 'free', r).ok);
  assert.equal(RW.spin(s, T0, 'free', r).reason, 'no_free');
  for (let i = 0; i < 3; i++) assert.ok(RW.spin(s, T0, 'ticket', r).ok); assert.equal(s.tickets, 2);
  assert.equal(RW.spin(s, T0, 'ticket', r).reason, 'daily_limit'); assert.equal(s.hist.length, 6);
  assert.ok(RW.spin(s, T0 + D, 'free', r).ok);
});
test('spin: ad spins need verified proof, 3 max, no reuse, nothing consumed on failure', () => {
  const s = RW.newState(), r = Math.random; for (let i = 0; i < 3; i++) RW.spin(s, T0, 'free', r);
  const before = JSON.stringify(s.sp), coins = s.coins;
  assert.equal(RW.spin(s, T0, 'ad', r).reason, 'ad_unverified'); assert.equal(RW.spin(s, T0, 'ad', r, { adProof: { verified: false, txId: 'x' } }).reason, 'ad_unverified');
  assert.equal(JSON.stringify(s.sp), before); assert.equal(s.coins, coins);
  for (const id of ['a', 'b', 'c']) assert.ok(RW.spin(s, T0, 'ad', r, { adProof: { verified: true, txId: id } }).ok);
  assert.equal(RW.spin(s, T0, 'ad', r, { adProof: { verified: true, txId: 'd' } }).reason, 'daily_limit');
  const t = RW.newState(); for (let i = 0; i < 3; i++) RW.spin(t, T0, 'free', r); RW.spin(t, T0, 'ad', r, { adProof: { verified: true, txId: 'z' } });
  assert.equal(RW.spin(t, T0, 'ad', r, { adProof: { verified: true, txId: 'z' } }).reason, 'ad_already_used');
});
test('spin: credited reward equals the reward shown, duplicate request id is idempotent', () => {
  const s = RW.newState(); for (let n = 0; n < 200; n++) { const t = RW.newState(), c = t.coins, g = t.gems, o = RW.spin(t, T0, 'free', Math.random); assert.equal(t.coins - c, o.reward.coins); assert.equal(t.gems - g, o.reward.gems); if (o.reward.item) assert.ok(t.inv.includes(o.reward.item)); }
  const a = RW.spin(s, T0, 'free', Math.random, { rid: 'r1' }), c = s.coins, b = RW.spin(s, T0, 'free', Math.random, { rid: 'r1' });
  assert.ok(b.dup); assert.equal(s.coins, c); assert.equal(s.sp.free, 1); assert.equal(b.slice, a.slice);
});
test('wheel: probabilities sum to 100, jackpot is 1 %, observed odds match, cosmetics never duplicate', () => {
  const p = RW.probabilities(); assert.equal(Math.round(p.reduce((a, x) => a + x.p, 0)), 100); assert.equal(p[9].p, 1);
  const N = 100000, cnt = Array(10).fill(0); for (let i = 0; i < N; i++) { const s = RW.newState(); cnt[RW.spin(s, T0, 'free', Math.random).slice]++; }
  cnt.forEach((c, i) => assert.ok(Math.abs(c / N * 100 - p[i].p) < 0.6, 'slice ' + i + ' observed ' + (c / N * 100).toFixed(2) + ' vs ' + p[i].p));
  const s = RW.newState(); for (let d = 0; d < 400; d++) { RW.spin(s, T0 + d * D, 'free', Math.random); } assert.equal(new Set(s.inv).size, s.inv.length);
});
/* rewarded-ad gate for daily/weekly */
{
  const assert2 = require('assert'), RW2 = require('./rewards-core'); const T = Date.UTC(2026, 10, 16, 8), D2 = 864e5;
  const s = RW2.newState(), c0 = s.coins, g = { requireAd: true };
  assert2.equal(RW2.claimDaily(s, T, g).reason, 'ad_unverified'); assert2.equal(s.coins, c0);
  assert2.equal(RW2.claimDaily(s, T, { requireAd: true, adProof: { verified: false, txId: 'a', kind: 'daily' } }).reason, 'ad_unverified');
  assert2.equal(RW2.claimDaily(s, T, { requireAd: true, adProof: { verified: true, txId: 'a', kind: 'spin' } }).reason, 'ad_unverified');
  assert2.ok(RW2.claimDaily(s, T, { requireAd: true, adProof: { verified: true, txId: 'a', kind: 'daily' } }).ok); assert2.ok(s.coins > c0);
  assert2.equal(RW2.claimDaily(s, T + D2, { requireAd: true, adProof: { verified: true, txId: 'a', kind: 'daily' } }).reason, 'ad_already_used');
  for (let i = 1; i < 3; i++) RW2.claimDaily(s, T + i * D2);
  const w = RW2.weekView(s, T + 2 * D2).tiers[0]; assert2.equal(w.status, 'available'); const c1 = s.coins;
  assert2.equal(RW2.claimWeekly(s, T + 2 * D2, 0, g).reason, 'ad_unverified'); assert2.equal(s.coins, c1);
  assert2.ok(RW2.claimWeekly(s, T + 2 * D2, 0, { requireAd: true, adProof: { verified: true, txId: 'w1', kind: 'weekly' } }).ok);
  assert2.equal(RW2.claimWeekly(s, T + 2 * D2, 0, { requireAd: true, adProof: { verified: true, txId: 'w2', kind: 'weekly' } }).reason, 'already_claimed');
  console.log('rewards ad-gate tests passed');
}
