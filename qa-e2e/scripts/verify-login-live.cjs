const { chromium } = require("@playwright/test");
const assert = require("node:assert/strict");

async function main() {
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({baseURL:process.env.BASE_URL});
  try {
    const page = await context.newPage();
    await page.goto("/login");
    await page.getByRole("heading", {name:"Đăng nhập"}).waitFor();
    await page.locator('header a[href="/login"]').waitFor();
    const login = await context.request.post("/api/v1/auth/login", {data:{username:process.env.QA_USERNAME,password:process.env.QA_PASSWORD}});
    assert.equal(login.status(), 200);
    await page.goto("/login");
    await page.waitForURL("**/admin");
    console.log("Signed-in visit to /login redirects: passed");
    await page.goto("/");
    await page.locator('header button[aria-haspopup="menu"]').waitFor();
    await page.locator('header button[aria-haspopup="menu"]').click();
    await page.getByRole("menuitem", {name:"Đăng xuất"}).click();
    await page.waitForURL("**/login");
    await page.getByRole("heading", {name:"Đăng nhập"}).waitFor();
    assert.equal(await page.locator('header button[aria-haspopup="menu"]').count(), 0);
    console.log("User-menu logout clears visible session: passed");
  } finally { await context.close(); await browser.close(); }
}
main().catch(error => {console.error(error); process.exitCode = 1;});
