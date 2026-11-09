import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests", testMatch: ["07-test-report-regressions.spec.ts", "08-v2-regressions.spec.ts"], workers: 1,
  timeout: 60000, expect: { timeout: 15000 },
  reporter: [["list"]], outputDir: "../test-reports/pethome-fixes/browser",
  use: { baseURL: "http://localhost:3100", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    { command: "node scripts/regression-api.mjs", port: 18000 },
    { command: "npm --prefix ../frontend run dev -- --port 3100", port: 3100, timeout: 120000, env: { INTERNAL_API_URL: "http://127.0.0.1:18000" } },
  ],
});
