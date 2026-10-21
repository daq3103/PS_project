import { test } from "@playwright/test";
import fs from "fs";
import path from "path";

test("ESLint non-interactive check on frontend", async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "once");
  const fe = path.join("D:", "code", "PS_project", "frontend");
  const hasConfig =
    fs.existsSync(path.join(fe, "eslint.config.mjs")) ||
    fs.existsSync(path.join(fe, "eslint.config.js")) ||
    fs.existsSync(path.join(fe, ".eslintrc.json")) ||
    fs.existsSync(path.join(fe, ".eslintrc.js"));
  const hasEslint = fs.existsSync(path.join(fe, "node_modules", "eslint"));

  testInfo.annotations.push({
    type: "eslint",
    description: `NOT RUN — eslintInstalled=${hasEslint} config=${hasConfig}; next lint opens interactive wizard`,
  });
  test.skip(true, "ESLint not configured for non-interactive run");
});
