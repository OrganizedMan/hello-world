import { defineConfig, devices } from "@playwright/test";


export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["line"]],
  use: {
    baseURL: "http://127.0.0.1:5178",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:5178/health-proxy-check",
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      HEARTHVIEW_API_PORT: "8008",
      HEARTHVIEW_WEB_PORT: "5178",
      HEARTHVIEW_FIXED_PORTS: "1",
      HEARTHVIEW_DATA_DIR: "work/e2e-data",
    },
  },
});
