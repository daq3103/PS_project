// Read-only verification of a deployed site; never creates, edits or deletes records.
const { chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
async function main() {
  const base = process.env.BASE_URL;
  assert(base && process.env.QA_USERNAME && process.env.QA_PASSWORD, "Supply BASE_URL, QA_USERNAME and QA_PASSWORD");
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({baseURL:base,viewport:{width:1440,height:900}});
  try {
    const response = await context.request.post("/api/v1/auth/login", {data:{username:process.env.QA_USERNAME,password:process.env.QA_PASSWORD}});
    assert.equal(response.status(),200,"Login");
    assert((await response.json()).staff_permissions.includes("platform_manage"));
    for (const path of ["/api/v1/admin/reports/sales","/api/v1/admin/stock-alerts","/api/v1/admin/lots","/api/v1/admin/catalog/products","/api/v1/admin/catalog/categories"]) {
      const r = await context.request.get(path); assert.equal(r.status(),200,path); console.log(path+": 200");
    }
    assert.equal((await context.request.get("/api/v1/admin/staff/users")).status(),403);
    const page = await context.newPage();
    await page.goto("/admin/community");
    await page.getByPlaceholder("Tiêu đề/mô tả").fill("zzzznomatch");
    await page.getByRole("cell",{name:"Không có kết quả phù hợp."}).waitFor();
    console.log("Community empty filter: passed");
    await page.goto("/admin/inventory-lots?stock=low");
    await page.getByText(/Mặt hàng hết hoặc sắp hết/).first().waitFor();
    await page.getByPlaceholder("Mã hàng, tên mẫu hoặc mã lô").fill("zzzznomatch");
    await page.getByRole("button",{name:"Làm mới",exact:true}).click();
    await page.getByRole("cell",{name:"Không có lô hàng."}).waitFor();
    assert.equal(await page.locator("p.text-danger").count(),0);
    console.log("Inventory text filter and refresh: passed");
    await page.goto("/admin/products");
    await page.getByPlaceholder("Tên, tên trong đường dẫn hoặc mã hàng").fill("zzzznomatch");
    await page.getByRole("cell",{name:"Không có sản phẩm phù hợp với bộ lọc."}).waitFor();
    await page.getByRole("button",{name:"+ Thêm sản phẩm"}).click();
    await page.getByRole("button",{name:"Tạo sản phẩm",exact:true}).click();
    assert((await page.locator("ul[role=alert]").innerText()).includes("Tên sản phẩm"));
    await page.getByLabel("Tên sản phẩm",{exact:true}).pressSequentially("Thuc an QA");
    assert.equal(await page.getByLabel("Tên trong đường dẫn",{exact:true}).inputValue(),"thuc-an-qa");
    console.log("Product search, form and slug: passed");
    await page.goto("/admin/promotions");
    await page.getByRole("button",{name:"Tạo mã",exact:true}).click();
    assert((await page.locator("ul[role=alert]").innerText()).includes("Bắt đầu"));
    console.log("Promotion missing dates: passed");
    await page.goto("/admin/reports");
    await page.getByRole("heading",{name:"Báo cáo bán hàng",exact:true}).waitFor();
    await page.getByText("Giá trị đơn đã thanh toán (không hủy)",{exact:true}).waitFor();
    console.log("Sales report: passed");
    await page.goto("/admin/categories");
    await page.getByRole("button",{name:"Xóa",exact:true}).first().waitFor();
    console.log("Authorized delete controls: present; no records deleted");
    await page.goto("/search");
    const brand=await page.locator('input[name="brand"]').boundingBox(), age=await page.locator('select[name="life_stage"]').boundingBox();
    assert(Math.abs(brand.y-age.y)<=3);
    console.log("Search alignment: passed");
    const csrf=(await context.cookies()).find(c=>c.name==="csrf_token")?.value;
    await context.request.post("/api/v1/auth/logout",{headers:csrf?{"X-CSRF-Token":csrf}:{}});
    console.log("Verification session logged out");
  } finally { await context.close(); await browser.close(); }
}
main().catch(error=>{ console.error(error); process.exitCode=1; });
