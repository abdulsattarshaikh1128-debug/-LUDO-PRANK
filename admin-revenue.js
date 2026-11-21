// Admin-only AdMob revenue endpoint. SERVER SIDE ONLY: never ship these credentials in the app.
// Needs: AdMob API enabled, an OAuth client, and a refresh token from the AdMob account owner.
// Verify field names/types against the current AdMob API reference before production.
import express from 'express';
import { google } from 'googleapis';

const app = express();
const need = ['ADMOB_PUBLISHER_ID', 'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN'];
const connected = need.every((k) => process.env[k]);
let lastSync = null, cache = null;

// IMPORTANT: replace with real authentication (verify your own signed-in user and an admin role).
// Denies everyone by default so the dashboard can never be exposed by accident.
async function isAdmin(req) { return false; }

const ymd = (d) => ({ year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() });

async function pull() {
  const auth = new google.auth.OAuth2(process.env.GOOGLE_CLIENT_ID, process.env.GOOGLE_CLIENT_SECRET);
  auth.setCredentials({ refresh_token: process.env.GOOGLE_REFRESH_TOKEN });
  const admob = google.admob({ version: 'v1', auth });
  const end = new Date(), start = new Date(end.getTime() - 30 * 864e5);
  const res = await admob.accounts.networkReport.generate({
    parent: `accounts/${process.env.ADMOB_PUBLISHER_ID}`,
    requestBody: { reportSpec: {
      dateRange: { startDate: ymd(start), endDate: ymd(end) },
      dimensions: ['DATE', 'FORMAT'],
      metrics: ['IMPRESSIONS', 'ESTIMATED_EARNINGS', 'OBSERVED_ECPM'],
    } },
  });
  const rows = (res.data || []).filter((r) => r.row).map((r) => ({
    date: r.row.dimensionValues.DATE.value,
    format: r.row.dimensionValues.FORMAT.value,            // banner / interstitial / rewarded ...
    impressions: Number(r.row.metricValues.IMPRESSIONS.integerValue || 0),
    estimatedEarnings: Number(r.row.metricValues.ESTIMATED_EARNINGS.microsValue || 0) / 1e6,
    ecpm: Number(r.row.metricValues.OBSERVED_ECPM.microsValue || 0) / 1e6,
  }));
  lastSync = new Date().toISOString();
  cache = rows;
  return rows;
}

const sum = (rows, from) => rows.filter((r) => r.date >= from).reduce((a, r) => a + r.estimatedEarnings, 0);

app.get('/admin/revenue', async (req, res) => {
  if (!(await isAdmin(req))) return res.status(403).json({ error: 'forbidden' });
  if (!connected) return res.json({ status: 'not_connected' });   // never invent numbers
  try {
    const rows = await pull();
    const day = (n) => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10).replace(/-/g, '');
    res.json({
      status: 'ok', lastSuccessfulSync: lastSync,
      note: 'Estimated earnings only. Confirmed payments appear in the AdMob payments report, not here.',
      byFormat: rows,
      estimatedRevenue: { daily: sum(rows, day(1)), weekly: sum(rows, day(7)), monthly: sum(rows, day(30)) },
      rewardedCompletions: 'read from your own verified rewarded-ad (SSV) table',
      activeUsersNewUsersCompletedMatches: 'read from your own analytics database',
    });
  } catch (e) {
    res.json({ status: 'error', lastSuccessfulSync: lastSync, cached: cache ? 'previous data available' : null });
  }
});

app.listen(process.env.PORT || 3000);
