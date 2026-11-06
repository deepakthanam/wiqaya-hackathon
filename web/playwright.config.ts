import { defineConfig, devices } from "@playwright/test";

// Expects the API on :8000 and the web app on :3000 (`make api` + `make web`, or `make e2e` which starts both).
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: process.env.E2E_BASE_URL || "http://localhost:3000", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
