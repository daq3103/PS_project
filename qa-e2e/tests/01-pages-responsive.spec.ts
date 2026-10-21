import { test, expect } from "@playwright/test";
import path from "path";
import { attachIssueCollectors } from "../helpers/console";

const PAGES = [
  { path: "/", name: "home" },
  { path: "/search", name: "search" },
  { path: "/cart", name: "cart" },
  { path: "/login", name: "login" },
  { path: "/register", name: "register" },
  { path: "/checkout", name: "checkout" },
  { path: "/track-order", name: "track-order" },
  { path: "/account", name: "account" },
  { path: "/admin", name: "admin" },
];

const SHOT = path.join("D:", "code", "PS_project", "test-reports", "screenshots");

test.describe("Main pages — load + console/network", () => {
  for (const p of PAGES) {
    test(`${p.name} loads`, async ({ page }, testInfo) => {
      const issues = attachIssueCollectors(page);
      const res = await page.goto(p.path, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(800);
      const status = res?.status() ?? 0;
      expect(status, `${p.path} HTTP`).toBeLessThan(500);

      const shotName = `${testInfo.project.name}-${p.name}.png`;
      await page.screenshot({
        path: path.join(SHOT, shotName),
        fullPage: true,
      });

      // Soft-collect issues into test annotation for report
      testInfo.annotations.push({
        type: "consoleErrors",
        description: JSON.stringify(issues.consoleErrors.slice(0, 20)),
      });
      testInfo.annotations.push({
        type: "failedRequests",
        description: JSON.stringify(issues.failedRequests.slice(0, 20)),
      });

      // Fail on pageerror-level or many 5xx
      const hardConsole = issues.consoleErrors.filter((e) =>
        /TypeError|ReferenceError|SyntaxError|Hydration|Unhandled/i.test(e),
      );
      const hardNet = issues.failedRequests.filter((r) => /\b5\d\d\b/.test(r));
      expect(hardConsole, `hard console on ${p.path}: ${hardConsole.join(" | ")}`).toEqual([]);
      expect(hardNet, `5xx on ${p.path}: ${hardNet.join(" | ")}`).toEqual([]);
    });
  }
});
