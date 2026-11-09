import { test, expect } from "@playwright/test";

// Run only with regression.config.ts: all API data belongs to an isolated fixture server.
test.beforeEach(async ({ context }, testInfo) => {
  test.skip(!testInfo.config.configFile?.endsWith("regression.config.ts"), "Requires isolated fixture API");
  await context.addCookies([{ name: "qa_session", value: crypto.randomUUID(), url: "http://localhost:3100" }]);
});

test("quantity commits on blur and Enter, persists, updates badge and rejects invalid input", async ({ page }) => {
  let writes = 0;
  page.on("request", r => { if (r.method() === "PATCH" && r.url().includes("/cart/items/")) writes++; });
  await page.goto("/cart");
  const input = page.getByRole("spinbutton");
  await expect(input).toHaveValue("3");
  await input.fill("");
  await input.pressSequentially("12", { delay: 180 });
  await expect(input).toHaveValue("12");
  expect(writes).toBe(0);
  await input.press("Tab");
  await expect(page.getByRole("link", { name: "Giỏ hàng (12)", exact: true })).toBeVisible();
  expect(writes).toBe(1);
  await page.reload();
  await expect(input).toHaveValue("12");
  await input.fill("25"); await input.press("Enter");
  await expect(page.getByRole("link", { name: "Giỏ hàng (25)", exact: true })).toBeVisible();
  await input.fill("0"); await input.press("Tab");
  await expect(page.locator("p[role=alert]")).toContainText("từ 1 đến 99");
  await expect(input).toHaveValue("25");
  await input.fill("99"); await input.press("Tab");
  await expect(page.locator("p[role=alert]")).toContainText("Chỉ còn 47");
  await expect(input).toHaveValue("25");
  await input.fill(""); await input.pressSequentially("25"); await input.press("Tab");
  await expect(page.locator("p[role=alert]")).toHaveCount(0);
  await page.getByRole("button", { name: "Xóa", exact: true }).click();
  await expect(page.getByText("Chưa có sản phẩm trong giỏ.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Giỏ hàng", exact: true })).toBeVisible();
});

test("login and tracking display missing field messages", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.locator("p[role=alert]")).toContainText("tên tài khoản");
  await page.getByLabel("Tên tài khoản").fill("qatest");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.locator("p[role=alert]")).toContainText("mật khẩu");
  await page.goto("/track-order");
  await page.getByRole("button", { name: "Tra cứu", exact: true }).click();
  await expect(page.getByText("Vui lòng nhập mã đơn hàng.")).toBeVisible();
  await page.getByLabel("Mã đơn", { exact: true }).fill("QA123");
  await page.getByRole("button", { name: "Tra cứu", exact: true }).click();
  await expect(page.getByText("Vui lòng nhập số điện thoại đặt hàng.")).toBeVisible();
});

test("guest posts never display an empty authenticated list", async ({ page }) => {
  await page.goto("/account/community");
  await expect(page.locator("p[role=alert]")).toContainText("đăng nhập");
  await expect(page.getByText("Bạn chưa đăng tin nào.")).toHaveCount(0);
});

test("address phone validation and editing preserve location identifiers", async ({ page, context }) => {
  await context.addCookies([{ name: "qa_role", value: "member", url: "http://localhost:3100" }]);
  await page.goto("/account/addresses");
  await page.getByRole("button", { name: "Sửa", exact: true }).click();
  await page.getByLabel("SĐT", { exact: true }).fill("abc");
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await expect(page.locator("p[role=alert]")).toContainText("SĐT người nhận");
  await page.getByLabel("SĐT", { exact: true }).fill("0912345678");
  await page.getByLabel("Địa chỉ", { exact: true }).fill("99 Đường đã sửa");
  const request = page.waitForRequest(r => r.method() === "PATCH" && r.url().includes("/me/addresses/"));
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  expect((await request).postDataJSON()).toMatchObject({ province_id: 20, district_id: 21, ward_code: "22" });
  await page.reload();
  await expect(page.getByText("99 Đường đã sửa, Dịch Vọng, Cầu Giấy, Hà Nội")).toBeVisible();
});

test("member sees permission message without redirect to login", async ({ page, context }) => {
  await context.addCookies([{ name: "qa_role", value: "member", url: "http://localhost:3100" }]);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Bạn không có quyền truy cập quản trị." })).toBeVisible();
  await expect(page).toHaveURL(/\/admin$/);
});

test("admin filters show empty result and rejection updates without reload", async ({ page, context }) => {
  await context.addCookies([{ name: "qa_role", value: "staff", url: "http://localhost:3100" }]);
  await page.goto("/admin/community");
  const search = page.getByPlaceholder("Tiêu đề/mô tả");
  await search.fill("zzzznomatch");
  await expect(page.getByText("Không có kết quả phù hợp.")).toBeVisible();
  await search.fill("");
  await expect(page.getByRole("cell", { name: "Chờ duyệt", exact: true })).toBeVisible();
  page.once("dialog", dialog => dialog.accept("Nội dung thử nghiệm"));
  await page.getByRole("button", { name: "Từ chối", exact: true }).click();
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await expect(page.getByRole("cell", { name: "Từ chối", exact: true })).toBeVisible();
});

test("shop and tracking fit viewport; stock total explicitly covers variants", async ({ page }) => {
  for (const path of ["/shop", "/track-order", "/tram-cuu-ho"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
    if (path === "/shop") await expect(page.getByText("Tổng còn 90 (2 loại)")).toBeVisible();
  }
});
