import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { qaTotp } from "../helpers/qa-totp";

const seedPath = path.resolve(__dirname, "../community-qa.json");
type Credential = { email: string; password: string; totp: string };
const seed: Record<string, Credential> = fs.existsSync(seedPath) ? JSON.parse(fs.readFileSync(seedPath, "utf8")) : {};
test.skip(!seed.owner, "Requires isolated API started with backend/scripts/community_qa.py");

async function login(page: Page, credential: Credential) {
  await page.goto("/login");
  await page.getByLabel("Tên tài khoản").fill(credential.email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(credential.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  if (credential.email === seed.owner?.email) {
    await page.getByLabel("Mã xác thực 6 số").fill(qaTotp(credential.totp));
    await page.getByRole("button", { name: "Xác minh và đăng nhập" }).click();
  }
  await page.waitForURL(/\/(account|admin)$/);
}

test("first-party analytics: real events, owner dashboard, privacy and permissions", async ({ page, browser }, info) => {
  await login(page, seed.owner);
  await page.goto("/admin/analytics");
  await expect(page.getByRole("heading", { name: "Truy cập & hiệu năng" })).toBeVisible();
  await expect(page.getByText("Đang lấy thống kê…", { exact: true })).toHaveCount(0);
  await expect(page.locator("main").getByRole("alert")).toHaveCount(0);
  const endpoint = "/api/proxy/api/v1/admin/analytics/traffic?days=1&section=all";
  const before = await (await page.request.get(endpoint)).json();
  const guest = await browser.newContext({ baseURL: process.env.BASE_URL || "http://localhost:3100" });
  const visitor = await guest.newPage();
  try {
    const event = visitor.waitForResponse(response => response.url().includes("/analytics/events") && response.request().postDataJSON()?.kind === "page_view");
    await visitor.goto("/tram-cuu-ho");
    expect((await event).status()).toBe(204);
    if ((info.project.use.viewport?.width ?? 1440) < 1024) {
      // A new context defaults to desktop viewport, so only expand if the toggle is visible.
      const toggle = visitor.getByRole("button", { name: "Khám phá cứu hộ" });
      if (await toggle.isVisible()) await toggle.click();
    }
    await visitor.getByRole("navigation", { name: "Menu Trạm cứu hộ" }).getByRole("link", { name: "Nhận nuôi", exact: true }).click();
    await expect(visitor).toHaveURL(/post_type=adoption/);
    const shopView = visitor.waitForResponse(response => response.url().includes("/analytics/events") && response.request().postDataJSON()?.kind === "page_view");
    await visitor.getByRole("navigation", { name: "Khu vực chính" }).getByRole("link", { name: "Shop", exact: true }).click();
    expect((await shopView).status()).toBe(204);
    await expect.poll(async () => (await (await page.request.get(endpoint)).json()).summary.views).toBe(before.summary.views + 2);
    const after = await (await page.request.get(endpoint)).json();
    expect(after.online).toBeGreaterThanOrEqual(1);
    const recent = after.dimensions.page.map((row: { label: string }) => row.label);
    expect(recent).toContain("/tram-cuu-ho");
    await page.getByRole("combobox", { name: "Khu vực", exact: true }).selectOption("rescue");
    await expect(page.getByText("Đang lấy thống kê…", { exact: true })).toHaveCount(0);
    await expect(page.locator("main").getByRole("alert")).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath("analytics-traffic.png"), fullPage: true });
    await page.getByRole("button", { name: "Tình trạng hệ thống", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Các bộ phận của hệ thống" })).toBeVisible();
    await expect(page.getByText("Kết nối tốt", { exact: true })).toHaveCount(3);
    await expect(page.getByText("Chưa lấy được số liệu xử lý.", { exact: false })).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath("analytics-system.png"), fullPage: true });
  } finally { await guest.close(); }

  const privateContext = await browser.newContext({ baseURL: process.env.BASE_URL || "http://localhost:3100" });
  await privateContext.addInitScript(() => { Object.defineProperty(navigator, "doNotTrack", { get: () => "1" }); });
  const privatePage = await privateContext.newPage();
  const sent: string[] = [];
  privatePage.on("request", request => { if (request.url().includes("/analytics/events")) sent.push(request.url()); });
  await privatePage.goto("/tram-cuu-ho");
  await expect(privatePage.getByRole("heading", { name: "Cùng đưa các bé về nhà" })).toBeVisible();
  await privatePage.getByRole("navigation", { name: "Khu vực chính" }).getByRole("link", { name: "Shop", exact: true }).click();
  await expect(privatePage).toHaveURL(/\/shop$/);
  expect(sent).toHaveLength(0);
  await privateContext.close();

  const customerContext = await browser.newContext({ baseURL: process.env.BASE_URL || "http://localhost:3100" });
  const customer = await customerContext.newPage();
  await login(customer, seed.customer);
  expect((await customer.request.get(endpoint)).status()).toBe(403);
  expect((await customer.request.get("/api/proxy/api/v1/admin/analytics/system")).status()).toBe(403);
  await customerContext.close();
});
