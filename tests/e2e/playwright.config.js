const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: '.',
  timeout: 30000,
  fullyParallel: false, // shares one dev-server DB across specs (see search.spec.js cleanup)
  use: {
    baseURL: 'http://127.0.0.1:8000',
  },
});
