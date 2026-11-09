// Read-only public-site check of product quantity and configurable Shop links.
const { chromium } = require("@playwright/test");
const assert = require("node:assert/strict");

async function main() {
  const baseURL = process.env.BASE_URL;
  assert(baseURL);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ baseURL });
  try {
    const categoriesResponse = await context.request.get("/api/v1/categories");
    assert.equal(categoriesResponse.status(), 200);
    const categories = await categoriesResponse.json();
    const productsResponse = await context.request.get("/api/v1/products?status=active&limit=200");
    assert.equal(productsResponse.status(), 200);
    const products = await productsResponse.json();
    const product = products.find(p => p.variants?.some(v => v.is_active && v.cached_available_qty > 1));
    assert(product, "Need an in-stock product to inspect quantity selection");
    const page = await context.newPage();
    await page.goto(`/p/${product.slug}`);
    const variant = product.variants.find(v => v.is_active && v.cached_available_qty > 1);
    const unit = variant.options?.unit || "cái";
    const variantLabel = variant.title.toLocaleLowerCase("vi-VN").includes(unit.toLocaleLowerCase("vi-VN")) ? variant.title : `${variant.title} · ${unit}`;
    await page.getByRole("button", { name: variantLabel, exact: true }).click();
    await page.getByRole("button", { name: /Thêm vào giỏ/ }).waitFor();
    const quantity = page.getByRole("spinbutton", { name: /Số lượng/ });
    assert.equal(await quantity.count(), 1);
    await quantity.fill("2");
    assert.equal(await quantity.inputValue(), "2");
    assert.equal(await quantity.getAttribute("max"), String(Math.min(99, variant.cached_available_qty)));
    console.log("Product quantity selector: passed");

    const menu = page.getByRole("navigation", { name: "Menu Shop" });
    const expected = categories.filter(c => c.show_in_nav).sort((a,b) => a.sort_order - b.sort_order);
    for (const category of expected) await menu.getByRole("link", { name: category.name }).waitFor();
    const actual = await menu.locator('a[href^="/c/"]').allTextContents();
    assert.deepEqual(actual.map(s => s.trim()), expected.map(c => c.name));
    console.log("Configurable category navigation: passed");
  } finally { await context.close(); await browser.close(); }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
