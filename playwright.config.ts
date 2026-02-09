import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for Atomic Decision E2E Tests
 * 
 * Usage:
 *   npx playwright test                           # Run all tests
 *   npx playwright test atomic-decision.spec.ts   # Run specific test
 *   npx playwright test --headed                  # Show browser
 *   npx playwright test --debug                   # Debug mode
 */

export default defineConfig({
  testDir: './tests/e2e',
  
  // Timeout for each test (15s)
  timeout: 15 * 1000,
  
  // Test output directory
  outputDir: 'test-results/',
  
  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,
  
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  
  // Opt out of parallel tests on CI
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter to use
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
    ['json', { outputFile: 'test-results/results.json' }]
  ],
  
  use: {
    // Base URL for tests
    baseURL: process.env.BASE_URL || 'https://beta.beatvegas.app',
    
    // Collect trace when retrying the failed test
    trace: 'on-first-retry',
    
    // Screenshot on failure
    screenshot: 'only-on-failure',
    
    // Video on failure
    video: 'retain-on-failure',
    
    // Maximum time for actions like click, fill, etc
    actionTimeout: 10 * 1000,
  },

  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],

  // Run your local dev server before starting the tests (optional)
  // webServer: {
  //   command: 'npm run dev',
  //   url: 'http://localhost:5173',
  //   reuseExistingServer: !process.env.CI,
  // },
});
