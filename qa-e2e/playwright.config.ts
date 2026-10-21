import { defineConfig, devices } from "@playwright/test";
import path from "path";
import fs from "fs";

const envPath = path.join(__dirname, ".env");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf-8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!m) continue;
    if (!process.env[m[1]]) process.env[m[1]] = m[2];
  }
}

const SCREENSHOT_DIR = path.join("D:", "code", "PS_project", "test-reports", "screenshots");
const chromium = { ...devices["Desktop Chrome"] };

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 20_000 },
  reporter: [
    ["list"],
    ["json", { outputFile: path.join("D:", "code", "PS_project", "test-reports", "playwright-results.json") }],
  ],
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    ...chromium,
    channel: undefined,
    browserName: "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    locale: "vi-VN",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "tablet", use: { viewport: { width: 768, height: 1024 }, isMobile: true, hasTouch: true } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  outputDir: path.join(SCREENSHOT_DIR, "test-output"),
});
