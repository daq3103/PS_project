import { Page } from "@playwright/test";

export type PageIssues = {
  consoleErrors: string[];
  failedRequests: string[];
};

export function attachIssueCollectors(page: Page): PageIssues {
  const issues: PageIssues = { consoleErrors: [], failedRequests: [] };
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const t = msg.text();
      // Ignore noisy Next.js hydration / favicon noise selectively
      if (/favicon|Download the React DevTools/i.test(t)) return;
      issues.consoleErrors.push(t);
    }
  });
  page.on("pageerror", (err) => {
    issues.consoleErrors.push(String(err));
  });
  page.on("response", (res) => {
    const status = res.status();
    if (status >= 400) {
      const url = res.url();
      // Ignore expected auth probes
      if (url.includes("/api/v1/auth/me") && status === 401) return;
      issues.failedRequests.push(`${status} ${res.request().method()} ${url}`);
    }
  });
  return issues;
}
