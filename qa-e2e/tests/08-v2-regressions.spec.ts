import { test, expect } from "@playwright/test";

test.beforeEach(async ({ context }, info) => {
  test.skip(!info.config.configFile?.endsWith("regression.config.ts"), "Requires isolated fixture API");
  await context.addCookies([{name:"qa_session",value:crypto.randomUUID(),url:"http://localhost:3100"}]);
});
const staff = async (context: import("@playwright/test").BrowserContext) => context.addCookies([{name:"qa_role",value:"staff",url:"http://localhost:3100"}]);

test("v2 registration and recovery validate in Vietnamese and clear corrected errors", async ({page}) => {
  await page.goto("/register");
  await page.getByRole("button",{name:"Đăng ký",exact:true}).click();
  await expect(page.locator("ul[role=alert]")).toContainText("Tên tài khoản");
  await expect(page.locator("ul[role=alert]")).toContainText("Mật khẩu");
  await page.getByLabel("Tên tài khoản",{exact:true}).fill("tester_v2");
  await page.getByLabel("Mật khẩu (≥ 8 ký tự)",{exact:true}).fill("12345");
  await page.getByLabel("Xác nhận mật khẩu",{exact:true}).fill("12345");
  await page.getByRole("button",{name:"Đăng ký",exact:true}).click();
  await expect(page.locator("ul[role=alert]")).toContainText("ít nhất 8 ký tự");
  await page.getByLabel("Mật khẩu (≥ 8 ký tự)",{exact:true}).fill("Strong12345");
  await page.getByLabel("Xác nhận mật khẩu",{exact:true}).fill("Strong98765");
  await page.getByRole("button",{name:"Đăng ký",exact:true}).click();
  await expect(page.locator("p[role=alert]")).toContainText("không khớp");
  await page.getByLabel("Xác nhận mật khẩu",{exact:true}).fill("Strong12345");
  await expect(page.locator("p[role=alert]")).toHaveCount(0);
  await page.goto("/forgot-password");
  await page.getByLabel("Email đăng ký").fill("abc");
  await page.getByRole("button",{name:"Gửi mã xác minh"}).click();
  await expect(page.locator("ul[role=alert]")).toContainText("Email không đúng định dạng");
});

test("v2 product empty search, complete slug generation and all required form fields", async ({page,context}) => {
  await staff(context); await page.goto("/admin/products");
  const search=page.getByPlaceholder("Tên, tên trong đường dẫn hoặc mã hàng");
  await search.fill("zzz");
  await expect(page.getByRole("cell",{name:"Không có sản phẩm phù hợp với bộ lọc."})).toBeVisible();
  await page.getByRole("button",{name:"+ Thêm sản phẩm"}).click();
  await page.getByRole("button",{name:"Tạo sản phẩm",exact:true}).click();
  await expect(page.locator("ul[role=alert]")).toContainText("Tên sản phẩm");
  await expect(page.locator("ul[role=alert]")).toContainText("Giá (đ)");
  await expect(page.locator("ul[role=alert]")).toContainText("Cân nặng");
  await page.getByLabel("Tên sản phẩm",{exact:true}).pressSequentially("Thuc an cho meo",{delay:60});
  await expect(page.getByLabel("Tên trong đường dẫn",{exact:true})).toHaveValue("thuc-an-cho-meo");
  await page.getByLabel("Tên trong đường dẫn",{exact:true}).fill("tu-dat");
  await page.getByLabel("Tên sản phẩm",{exact:true}).fill("Ten moi");
  await expect(page.getByLabel("Tên trong đường dẫn",{exact:true})).toHaveValue("tu-dat");
});

test("v2 inventory text filters and refresh never send text as UUID; adjustment refreshes drawer", async ({page,context}) => {
  await staff(context); await page.goto("/admin/inventory-lots?stock=low");
  await expect(page.getByText("Chưa nhập lô · N · LOW-STOCK")).toBeVisible();
  const filter=page.getByPlaceholder("Mã hàng, tên mẫu hoặc mã lô");
  await filter.fill("zzzxxx");
  await expect(page.getByRole("cell",{name:"Không có lô hàng."})).toBeVisible();
  await page.getByRole("button",{name:"Làm mới",exact:true}).click();
  await expect(page.locator("p.text-danger")).toHaveCount(0);
  await filter.fill("SEED-001");
  await page.getByRole("button",{name:"Điều chỉnh",exact:true}).click();
  await page.getByLabel("Delta (+/−)").fill("-5");
  await page.getByLabel("Ghi chú",{exact:true}).last().fill("QA giảm tồn");
  await page.getByRole("button",{name:"Ghi điều chỉnh",exact:true}).click();
  await page.getByRole("button",{name:"Ghi",exact:true}).click();
  await expect(page.getByText("5",{exact:true}).last()).toBeVisible();
});

test("v2 cart automatically saves and preserves an edit on immediate reload", async ({page}) => {
  await page.goto("/cart"); const input=page.getByRole("spinbutton");
  await expect(input).toHaveValue("3");
  await input.fill("12");
  await expect(page.getByRole("link",{name:"Giỏ hàng (12)",exact:true})).toBeVisible();
  await input.fill("25");
  await page.reload();
  await expect(input).toHaveValue("25");
  await expect(page.getByRole("link",{name:"Giỏ hàng (25)",exact:true})).toBeVisible();
});

test("v2 adoption, rescue report and support expose Vietnamese empty-form errors", async ({page,context}) => {
  await staff(context);
  await page.goto("/tram-cuu-ho/test-adoption");
  await page.getByRole("button",{name:"Gửi hồ sơ",exact:true}).click();
  await expect(page.locator("ul[role=alert]")).toContainText("Họ tên");
  await expect(page.locator("ul[role=alert]")).toContainText("Điện thoại");
  await expect(page.getByText(", Hà Nội",{exact:true})).toHaveCount(0);
  await page.goto("/tram-cuu-ho/bao-tin");
  await page.getByRole("button",{name:"Gửi tin cho trạm"}).click();
  await expect(page.locator("ul[role=alert]")).toContainText("Thời điểm nhìn thấy");
  await page.goto("/account/support");
  await page.getByRole("button",{name:"Gửi yêu cầu",exact:true}).click();
  await expect(page.locator("ul[role=alert]")).toContainText("Tiêu đề");
  await expect(page.locator("ul[role=alert]")).toContainText("Nội dung");
});

test("v2 promotion dates, sales report and search filter alignment", async ({page,context},info) => {
  await staff(context); await page.goto("/admin/promotions");
  await page.getByLabel("Mã",{exact:true}).fill("TESTV2");
  await page.getByRole("button",{name:"Tạo mã",exact:true}).click();
  await expect(page.locator("ul[role=alert]")).toContainText("Bắt đầu");
  await expect(page.locator("ul[role=alert]")).toContainText("Kết thúc");
  await page.goto("/admin/reports");
  await expect(page.getByRole("heading",{name:"Báo cáo bán hàng",exact:true})).toBeVisible();
  await expect(page.getByText("Giá trị đơn đã giao",{exact:true}).first()).toBeVisible();
  await page.goto("/search");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1)).toBe(true);
  if(info.project.name==="desktop") {
    const brand=await page.locator('input[name="brand"]').boundingBox(); const age=await page.locator('select[name="life_stage"]').boundingBox();
    expect(Math.abs(brand!.y-age!.y)).toBeLessThanOrEqual(3);
  }
});
