// docs/15: every /app/* page now requires a session. Register the sole
// test account once, before any spec runs, and save the resulting session
// cookie to storageState.json (referenced by playwright.config.js's
// `use.storageState`) so every test's browser context starts already
// logged in -- these specs are testing search/queue behavior, not auth
// (see tests/test_auth_routes.py for that).
const { request } = require('@playwright/test');

module.exports = async (config) => {
  const baseURL = config.projects[0].use.baseURL;
  const context = await request.newContext({ baseURL });

  // Idempotent across repeated local runs against the same dev DB
  // (search.spec.js's own comments note tests share one dev-server DB):
  // registration only succeeds once, so treat a non-2xx response as "an
  // account already exists" and fall back to logging in instead.
  const creds = { username: 'e2e-test', password: 'e2e-test-password' };
  const registerResp = await context.post('/register', { form: creds });
  if (!registerResp.ok()) {
    await context.post('/login', { form: creds });
  }

  await context.storageState({ path: `${__dirname}/storageState.json` });
  await context.dispose();
};
