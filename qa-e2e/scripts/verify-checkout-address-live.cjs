// Read-only check for the compact address flow and navigation.
const { chromium } = require("@playwright/test");
const assert = require("node:assert/strict");

async function main() {
  const baseURL = process.env.BASE_URL;
  assert(baseURL && process.env.QA_USERNAME && process.env.QA_PASSWORD);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ baseURL });
  try {
    const page = await context.newPage();
    await page.goto("/checkout");
    await page.waitForURL(/\/login\?next=/);
    assert.equal(new URL(page.url()).searchParams.get("next"), "/checkout");
    console.log("Guest checkout redirect: passed");

    const login = await context.request.post("/api/v1/auth/login", { data: { username: process.env.QA_USERNAME, password: process.env.QA_PASSWORD } });
    assert.equal(login.status(), 200);
    await page.goto("/checkout");
    await page.getByText("Địa chỉ nhận hàng (số nhà, đường, phường/xã, tỉnh/thành phố)").waitFor();
    for (const oldLabel of ["Tỉnh / Thành phố", "Quận / Huyện", "Phường / Xã", "Email (tuỳ chọn)"]) {
      assert.equal(await page.getByText(oldLabel, { exact: true }).count(), 0, oldLabel);
    }
    console.log("Compact checkout fields: passed");

    await page.goto("/account/addresses");
    await page.getByText("Địa chỉ đầy đủ (số nhà, đường, phường/xã, tỉnh/thành phố)").waitFor();
    assert.equal(await page.getByText("Quận / Huyện", { exact: true }).count(), 0);
    console.log("Compact address book: passed");

    await page.goto("/admin/shop/insights");
    const selected = page.getByRole("navigation", { name: "Các trang Shop" }).getByRole("link", { name: "Biểu đồ & chi phí" });
    assert.equal(await selected.getAttribute("aria-current"), "page");
    assert.match(await selected.getAttribute("class"), /bg-forest/);
    console.log("Active Shop tab: passed");
    const csrf = (await context.cookies()).find(cookie => cookie.name === "csrf_token")?.value;
    await context.request.post("/api/v1/auth/logout", { headers: csrf ? { "X-CSRF-Token": csrf } : {} });
  } finally { await context.close(); await browser.close(); }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
