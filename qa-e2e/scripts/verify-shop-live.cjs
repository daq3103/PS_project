// Read-only post-deploy check. It does not create or edit any Shop data.
const { chromium } = require("@playwright/test");
const assert = require("node:assert/strict");

async function main() {
  const base = process.env.BASE_URL;
  assert(base && process.env.QA_USERNAME && process.env.QA_PASSWORD);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ baseURL: base });
  try {
    const login = await context.request.post("/api/v1/auth/login", { data: { username: process.env.QA_USERNAME, password: process.env.QA_PASSWORD } });
    assert.equal(login.status(), 200);
    for (const path of ["/api/v1/admin/reports/overview", "/api/v1/admin/shop-expenses", "/api/v1/admin/catalog/products"]) {
      const response = await context.request.get(path);
      assert.equal(response.status(), 200, path);
      console.log(path, response.status());
    }
    const overview = await (await context.request.get("/api/v1/admin/reports/overview")).json();
    assert.equal(overview.daily.length, 7);
    const page = await context.newPage();
    await page.goto("/admin/shop/insights");
    await page.getByRole("heading", { name: "Biểu đồ & chi phí Shop" }).waitFor();
    await page.getByRole("button", { name: "Số đơn" }).click();
    assert.equal(await page.getByRole("button", { name: "Số đơn" }).getAttribute("aria-pressed"), "true");
    await page.getByText("Sổ chi phí Shop và chứng từ").waitFor();
    await page.getByRole("button", { name: "Doanh thu", exact: true }).click();
    await page.getByText("Chi phí: giá vốn + phí ship + khoản chi đã ghi").waitFor();
    const todayCost = page.locator('[title*="chi phí"]').last();
    assert(await todayCost.count());
    console.log("Cost column:", await todayCost.getAttribute("title"));
    console.log("Shop insight tab and charts: passed");
    await page.goto("/admin/orders");
    assert.equal(await page.getByRole("button", {name:"Cần xử lý"}).getAttribute("aria-pressed"), "true");
    await page.getByRole("button", {name:"Đã hoàn tất"}).click();
    assert.equal(await page.getByRole("button", {name:"Đã hoàn tất"}).getAttribute("aria-pressed"), "true");
    await page.getByRole("button", {name:"Tất cả", exact:true}).click();
    console.log("Order work queue tabs: passed");
    const orderRow = page.locator('tbody tr[role="button"]').first();
    await orderRow.waitFor();
    await orderRow.locator("td").nth(2).click();
    await page.waitForURL(/open=/);
    assert(new URL(page.url()).searchParams.get("open"), "Whole order row should open details");
    console.log("Whole order row click: passed");
    await page.goto("/admin/reports");
    await page.locator("th").filter({hasText:"Trạng thái các đơn"}).waitFor();
    await page.locator("th").filter({hasText:"Tình trạng ngày"}).waitFor();
    const sales = await (await context.request.get("/api/v1/admin/reports/sales")).json();
    if (sales.daily.length) assert(Array.isArray(sales.daily[0].status_breakdown) && typeof sales.daily[0].cod_pending_orders === "number" && typeof sales.daily[0].handled === "boolean");
    console.log("Daily order status summary: passed");
    const movements = page.getByRole("heading", { name: "Sổ kho" }).locator("..").locator("tbody tr:not(.animate-pulse)");
    await movements.first().waitFor();
    if (await movements.count()) {
      const border = await movements.first().locator("td").first().evaluate(cell => ({ width: getComputedStyle(cell).borderLeftWidth, color: getComputedStyle(cell).borderLeftColor }));
      assert.equal(border.width, "4px", "Daily movement marker");
      console.log("Daily movement edge marker: passed", border.color);
      await movements.first().locator("td").nth(1).click();
      await page.getByRole("button", {name:"Đóng"}).waitFor();
      await page.getByRole("button", {name:"Đóng"}).click();
      console.log("Movement detail row click: passed");
    }
    await page.getByRole("link", {name:/Tổng số đơn/}).click();
    await page.waitForURL(/report_metric=all/);
    console.log("Sales report drilldown: passed");
    await page.goto("/admin/products");
    const productRow = page.locator('tbody tr[role="button"]').first();
    await productRow.waitFor();
    await productRow.locator("td").nth(3).click();
    await page.getByRole("button", {name:"Đóng"}).waitFor();
    console.log("Whole product row click: passed");
    await page.getByRole("button", {name:"Đóng"}).click();
    await page.getByRole("button", { name: "+ Thêm sản phẩm" }).click();
    await page.getByLabel("Đơn vị bán / nhập kho").waitFor();
    console.log("Product unit field: passed");
    const csrf = (await context.cookies()).find(cookie => cookie.name === "csrf_token")?.value;
    await context.request.post("/api/v1/auth/logout", { headers: csrf ? { "X-CSRF-Token": csrf } : {} });
  } finally { await context.close(); await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
