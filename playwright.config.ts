import { defineConfig, devices } from "@playwright/test";

const WEB_URL = "http://localhost:5173";
const ADMIN_URL = "http://localhost:5174";
const API_URL = "http://localhost:8000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 1,
  timeout: 30_000,
  expect: { timeout: 8_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "web",
      use: { ...devices["Desktop Chrome"], baseURL: WEB_URL },
      testMatch: "web/**/*.spec.ts",
    },
    {
      name: "admin",
      use: { ...devices["Desktop Chrome"], baseURL: ADMIN_URL },
      testMatch: "admin/**/*.spec.ts",
    },
  ],
  webServer: [
    {
      command: "pnpm dev:web",
      url: WEB_URL,
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: "pnpm dev:admin",
      url: ADMIN_URL,
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      // uv may not be on PATH; the project venv has uvicorn. reuseExistingServer
      // means a manually-started API on :8000 is preferred.
      command:
        "cd apps/api && .venv/Scripts/python -m uvicorn main:app --port 8000",
      url: `${API_URL}/api/v1/health`,
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
