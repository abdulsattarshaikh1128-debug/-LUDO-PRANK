/* TEST-ONLY launcher: starts the real server with (a) a fake Google verifier, (b) a test SSV signing key, (c) /__test/ssv to emulate Google's SSV callback.
   Never used in production. Env: PORT, TEST_CLIENT_ID ('' = Google not configured), TEST_ADS_MODE (ssv|dev), TEST_DATA_DIR */
'use strict';
const crypto = require('crypto'), path = require('path');
const api = require('../server/account-api'); const orig = api.create;
const { privateKey, publicKey } = crypto.generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
const users = { 'good-alice-token-000000000000': { sub: 'g-alice', email: 'alice@example.com', name: 'Alice' }, 'good-bob-token-00000000000000': { sub: 'g-bob', email: 'bob@example.com', name: 'Bob' } };
api.create = (o) => orig(Object.assign({}, o, { googleClientId: process.env.TEST_CLIENT_ID === undefined ? 'test.apps.googleusercontent.com' : process.env.TEST_CLIENT_ID, adsMode: process.env.TEST_ADS_MODE || 'dev', dataDir: process.env.TEST_DATA_DIR, ssvKeys: { 1: publicKey.export({ type: 'spki', format: 'pem' }) }, verifyGoogle: async (t) => { if (!users[t]) throw new Error('rejected'); return users[t]; } }));
const { server } = require('../server/ludo-server');
const handlers = server.listeners('request'); server.removeAllListeners('request');
server.on('request', (req, res) => {
  const u = new URL(req.url, 'http://x');
  if (u.pathname === '/__test/ssv') { const q = 'ad_network=1&ad_unit=1&reward_amount=1&reward_item=x&timestamp=' + Date.now() + '&transaction_id=' + u.searchParams.get('tx') + '&user_id=d&custom_data=' + u.searchParams.get('nonce') + '&key_id=1'; const sig = crypto.sign('sha256', Buffer.from(q), privateKey).toString('base64url'); req.url = '/api/ads/ssv?' + q + '&signature=' + sig; }
  handlers.forEach((h) => h.call(server, req, res));
});
server.listen(+process.env.PORT, () => console.log('test server up'));
