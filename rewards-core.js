/* LUDO PRANK reward rules: daily calendar, weekly rewards, spin wheel.
   ONE implementation used by the game prototype AND by a server. In production the SERVER runs these functions with its own clock
   and random generator (never trust the client's clock or dice). Pure state-in/state-out, no I/O. */
const RW = (() => {
  const DAY = 864e5, LIM = { free: 3, ad: 3, total: 6 }, OWNED_BONUS = 150;
  const iso = (t) => new Date(t).toISOString().slice(0, 10);
  const wk = (t) => { const d = new Date(t); d.setUTCHours(0, 0, 0, 0); d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7)); const y = d.getUTCFullYear(); return y + '-W' + String(Math.ceil(((d - Date.UTC(y, 0, 1)) / DAY + 1) / 7)).padStart(2, '0'); };
  const nextDay = (t) => { const d = new Date(t); d.setUTCHours(0, 0, 0, 0); return d.getTime() + DAY; };
  const nextWeek = (t) => { const d = new Date(t); d.setUTCHours(0, 0, 0, 0); return d.getTime() + (8 - (d.getUTCDay() || 7)) * DAY; };
  const DICE = ['Golden Dice', 'Starry Dice', 'Candy Dice', 'Neon Dice', 'Ice Dice'], TOKS = ['Diamond Tokens', 'Rainbow Tokens', 'Glow Tokens', 'Fire Tokens', 'Galaxy Tokens'];
  const AV = ['🦖', '🧞', '🥷', '🧙', '👽', '🤴'], FRN = ['Gold Crown', 'Fire', 'Galaxy'];   // avatars 12..17, frames 6..8
  const DAILY = [
    { name: 'Starter Week', d: [{ c: 150 }, { g: 5 }, { t: 1 }, { item: 'avatar:12' }, { item: 'dice:Candy Dice' }, { item: 'token:Glow Tokens' }, { c: 500, g: 25, item: 'frame:6', prem: 1 }] },
    { name: 'Festival Week', d: [{ c: 200 }, { g: 8 }, { t: 2 }, { item: 'avatar:13' }, { item: 'dice:Starry Dice' }, { item: 'token:Rainbow Tokens' }, { c: 800, g: 40, item: 'frame:7', prem: 1 }] },
    { name: 'Champion Week', d: [{ c: 250 }, { g: 10 }, { t: 2 }, { item: 'avatar:14' }, { item: 'dice:Golden Dice' }, { item: 'token:Diamond Tokens' }, { c: 1000, g: 50, item: 'frame:8', prem: 1 }] }];
  const WEEKLY = [
    { name: 'Neon Collection', t: [{ c: 300, g: 5 }, { t: 1, c: 100 }, { item: 'dice:Neon Dice' }, { item: 'token:Fire Tokens' }, { item: 'avatar:15', c: 500, g: 20 }] },
    { name: 'Frost Collection', t: [{ c: 400 }, { t: 2 }, { item: 'dice:Ice Dice' }, { item: 'token:Galaxy Tokens' }, { item: 'avatar:16', c: 600, g: 25 }] },
    { name: 'Royal Collection', t: [{ g: 10 }, { c: 300, t: 1 }, { item: 'dice:Neon Dice', c: 100 }, { item: 'token:Fire Tokens', c: 100 }, { item: 'avatar:17', c: 800, g: 30 }] }];
  const NEED = [{ k: 'days', n: 3 }, { k: 'games', n: 5 }, { k: 'wins', n: 2 }, { k: 'caps', n: 10 }, { k: 'all', n: 4 }];
  const WHEEL = [
    { t: '🪙 50', c: 50, w: 24 }, { t: '🪙 100', c: 100, w: 17 }, { t: '🪙 200', c: 200, w: 6 }, { t: '💎 5', g: 5, w: 15 }, { t: '💎 15', g: 15, w: 5 },
    { t: '🎁 Chest', c: 150, g: 5, w: 8, d: 'Reward chest: 🪙 150 + 💎 5' }, { t: '🎲 Dice', pool: 'dice', w: 8, d: 'Random dice skin you do not own yet' },
    { t: '🎨 Token', pool: 'token', w: 8, d: 'Random token skin you do not own yet' }, { t: '🖼️ Frame', pool: 'frame', w: 8, d: 'Profile frame you do not own yet' }, { t: '👑 JACKPOT', c: 1500, g: 50, w: 1, jp: 1, d: 'JACKPOT: 🪙 1500 + 💎 50' }];
  const POOL = { dice: DICE.map((n) => 'dice:' + n), token: TOKS.map((n) => 'token:' + n), frame: ['frame:7', 'frame:8'] };
  const newState = () => ({ gems: 30, coins: 1250, tickets: 0, inv: [], eq: { dice: null, token: null }, tx: [], claims: {}, seen: 0, hist: [],
    daily: { cycle: 0, day: 0, last: '' }, week: { key: '', prog: { days: 0, games: 0, wins: 0, caps: 0, spins: 0 }, claimed: {} }, sp: { day: '', free: 0, ad: 0, tk: 0 } });
  const name = (it) => { const [ty, v] = it.split(':'); return ty === 'avatar' ? AV[v - 12] + ' Avatar' : ty === 'frame' ? '🖼️ ' + FRN[v - 6] + ' frame' : (ty === 'dice' ? '🎲 ' : '🎨 ') + v; };
  const describe = (r) => [r.c ? '🪙 ' + r.c : '', r.g ? '💎 ' + r.g : '', r.t ? '🎟️ ×' + r.t : '', r.item ? name(r.item) : ''].filter(Boolean).join(' + ');
  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  /* time: never goes backwards (clock rollback cannot reopen a claimed day); rolls the week and the daily spin counters */
  function tick(st, raw) { const now = Math.max(raw, st.seen || 0); st.seen = now; const k = wk(now); if (st.week.key !== k) st.week = { key: k, prog: { days: 0, games: 0, wins: 0, caps: 0, spins: 0 }, claimed: {} }; const d = iso(now); if (st.sp.day !== d) st.sp = { day: d, free: 0, ad: 0, tk: 0 }; return now; }
  /* credits exactly what it returns; an item already owned becomes coins (stated in the text) */
  function grant(st, r, src, now, key) {
    const out = { coins: r.c || 0, gems: r.g || 0, tickets: r.t || 0, item: null, text: '' };
    if (r.item) { if (st.inv.includes(r.item)) { out.coins += OWNED_BONUS; out.conv = r.item; } else { st.inv.push(r.item); out.item = r.item; } }
    st.coins += out.coins; st.gems += out.gems; st.tickets += out.tickets;
    out.text = describe(Object.assign({}, r, { item: out.item, c: out.coins, g: out.gems, t: out.tickets })) + (out.conv ? ' (you already own ' + name(out.conv) + ')' : '');
    st.tx.push({ id: uid(), ts: now, src, key, coins: out.coins, gems: out.gems, tickets: out.tickets, item: out.item }); if (st.tx.length > 300) st.tx.shift();
    return out;
  }
  /* Daily/weekly bonuses can require a watched rewarded ad: opt.requireAd + opt.adProof {verified:true, txId, kind}. The proof is single use. */
  function adGate(st, opt, kind) {
    if (!opt || !opt.requireAd) return null; const a = opt.adProof;
    if (!a || a.verified !== true || !a.txId || a.kind !== kind) return { ok: false, reason: 'ad_unverified' };
    if (st.claims['ad:' + a.txId]) return { ok: false, reason: 'ad_already_used' }; return null;
  }
  const useAd = (st, opt) => { if (opt && opt.requireAd) st.claims['ad:' + opt.adProof.txId] = 1; };
  function claimDaily(st, raw, opt) {
    const now = tick(st, raw), today = iso(now); if (st.daily.last === today || st.claims['daily:' + today]) return { ok: false, reason: 'already_claimed' };
    const g = adGate(st, opt, 'daily'); if (g) return g; useAd(st, opt);
    const d = st.daily; if (d.day >= 7) { d.cycle++; d.day = 0; }
    const r = DAILY[d.cycle % 3].d[d.day], res = grant(st, r, 'daily', now, 'daily:' + today);
    st.claims['daily:' + today] = 1; d.day++; d.last = today; st.week.prog.days++;
    return { ok: true, reward: res, prem: !!r.prem, day: d.day, cycle: d.cycle };
  }
  function dailyView(st, raw) {
    const now = tick(st, raw), d = st.daily, done = d.last === iso(now); let cyc = d.cycle, n = d.day; const fresh = n >= 7 && !done; if (fresh) { cyc++; n = 0; }
    const col = DAILY[cyc % 3];
    return { canClaim: !done, name: col.name, cycle: cyc + 1, resetMs: nextDay(now) - now, items: col.d.map((r, i) => ({ r, text: describe(r), prem: !!r.prem, status: i < n ? 'claimed' : (i === n && !done ? 'available' : 'locked') })) };
  }
  function weekView(st, raw) {
    const now = tick(st, raw), col = WEEKLY[(+st.week.key.split('-W')[1]) % 3], p = st.week.prog;
    return { key: st.week.key, name: col.name, resetMs: nextWeek(now) - now, tiers: col.t.map((r, i) => {
      const need = NEED[i], have = need.k === 'all' ? [0, 1, 2, 3].filter((j) => st.week.claimed[j]).length : p[need.k], claimed = !!st.week.claimed[i];
      return { r, text: describe(r), need: need.n, have: Math.min(have, need.n), kind: need.k, status: claimed ? 'claimed' : have >= need.n ? 'available' : 'locked' }; }) };
  }
  function claimWeekly(st, raw, i, opt) {
    const now = tick(st, raw), v = weekView(st, now), t = v.tiers[i], key = 'weekly:' + st.week.key + ':' + i;
    if (!t) return { ok: false, reason: 'bad_tier' }; if (st.claims[key] || t.status === 'claimed') return { ok: false, reason: 'already_claimed' }; if (t.status !== 'available') return { ok: false, reason: 'locked' };
    const g = adGate(st, opt, 'weekly'); if (g) return g; useAd(st, opt);
    const res = grant(st, t.r, 'weekly', now, key); st.claims[key] = 1; st.week.claimed[i] = 1; return { ok: true, reward: res, prem: i === 4 };
  }
  function progress(st, raw, stat, n = 1) { tick(st, raw); st.week.prog[stat] = (st.week.prog[stat] || 0) + n; }
  const total = WHEEL.reduce((a, s) => a + s.w, 0);
  const probabilities = () => WHEEL.map((s, i) => ({ i, t: s.t, p: +(s.w / total * 100).toFixed(1), d: s.d || (s.c ? '🪙 ' + s.c : '💎 ' + s.g) }));
  /* src: 'free' | 'ticket' | 'ad'. An ad spin needs a server-verified proof ({verified:true, txId}); without it nothing is consumed or granted. */
  function spin(st, raw, src, rng, opt = {}) {
    const now = tick(st, raw), sp = st.sp;
    if (opt.rid && st.claims['req:' + opt.rid]) return Object.assign({ ok: true, dup: true }, st.claims['req:' + opt.rid]);
    if (sp.free + sp.ad + sp.tk >= LIM.total) return { ok: false, reason: 'daily_limit' };
    if (src === 'free') { if (sp.free >= LIM.free) return { ok: false, reason: 'no_free' }; }
    else if (src === 'ticket') { if (sp.free < LIM.free) return { ok: false, reason: 'use_free_first' }; if (st.tickets < 1) return { ok: false, reason: 'no_ticket' }; }
    else if (src === 'ad') { const a = opt.adProof; if (!a || !a.verified || !a.txId) return { ok: false, reason: 'ad_unverified' }; if (st.claims['ad:' + a.txId]) return { ok: false, reason: 'ad_already_used' }; if (sp.ad >= LIM.ad) return { ok: false, reason: 'no_ad_spins' }; }
    else return { ok: false, reason: 'bad_source' };
    let x = rng() * total, i = 0; while (x >= WHEEL[i].w) { x -= WHEEL[i].w; i++; }
    const s = WHEEL[i]; let r = { c: s.c, g: s.g };
    if (s.pool) { const free = POOL[s.pool].filter((it) => !st.inv.includes(it)); if (free.length) r = { item: free[Math.floor(rng() * free.length)] }; else r = { c: 100 }; }
    if (src === 'free') sp.free++; else if (src === 'ticket') { sp.tk++; st.tickets--; } else { sp.ad++; st.claims['ad:' + opt.adProof.txId] = 1; }
    const res = grant(st, r, 'spin', now, 'spin'); st.week.prog.spins++;
    const out = { slice: i, jackpot: !!s.jp, reward: res }; st.hist.push({ ts: now, src, slice: i, text: res.text, jp: out.jackpot }); if (st.hist.length > 40) st.hist.shift();
    if (opt.rid) st.claims['req:' + opt.rid] = out; return Object.assign({ ok: true }, out);
  }
  return { LIM, WHEEL, DICE, TOKS, AV, FRN, DAILY, WEEKLY, NEED, newState, tick, claimDaily, dailyView, weekView, claimWeekly, progress, spin, probabilities, describe, name, iso, wk };
})();
if (typeof module !== 'undefined') module.exports = RW;
