import { defineConfig } from '@playwright/test'

const appPort = Number(process.env.PLAYWRIGHT_APP_PORT || '4173')
const apiPort = Number(process.env.PLAYWRIGHT_API_PORT || '8001')

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: '../output/playwright/report', open: 'never' }],
  ],
  outputDir: '../output/playwright/test-results',
  use: {
    baseURL: `http://127.0.0.1:${appPort}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'node scripts/e2e/start-backend.mjs',
      port: apiPort,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'node scripts/e2e/start-frontend.mjs',
      port: appPort,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
