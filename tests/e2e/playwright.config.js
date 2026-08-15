const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: '.',
  timeout: 30000,
  fullyParallel: false, // shares one dev-server DB across specs (see search.spec.js cleanup)
  globalSetup: require.resolve('./global-setup.js'),
  use: {
    baseURL: 'http://127.0.0.1:8000',
    // Populated by global-setup.js (docs/15: /app/* now requires a
    // session) -- every test's browser context starts already logged in.
    storageState: `${__dirname}/storageState.json`,
  },
});
