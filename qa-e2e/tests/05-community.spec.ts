import { test, expect, type Page } from "@playwright/test";
import { qaTotp } from "../helpers/qa-totp";
import fs from "node:fs";
import path from "node:path";

const seedPath = path.resolve(__dirname, "../community-qa.json");
type Credential = { email: string; password: string; totp: string };
const seed: Record<string, Credential> = fs.existsSync(seedPath) ? JSON.parse(fs.readFileSync(seedPath, "utf8")) : {};
test.skip(!seed.customer, "Requires isolated API started with backend/scripts/community_qa.py");

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

async function assertNoTotpPrompt(page: Page) {
  await expect(page.getByRole("heading", { name: "Xác minh bảo mật" })).toHaveCount(0);
}

async function createFields(page: Page, title: string) {
  await page.getByLabel("Tiêu đề", { exact: true }).fill(title);
  await page.getByLabel("Mô tả", { exact: true }).fill("Bé mèo thử nghiệm cho luồng cứu hộ tự động.");
  await page.locator('select[name="province_id"]').selectOption("1");
  await page.locator('input[name="contact_phone"]').fill("0901234567");
}

test("lost/found: upload, staff approval, public privacy, resolution", async ({ page, browser }, info) => {
  test.skip(info.project.name === "tablet", "desktop and mobile exercise full workflow");
  const title = `QA lost ${info.project.name} ${Date.now()}`;
  const staff = await browser.newPage({ baseURL: String(info.project.use.baseURL || process.env.BASE_URL || "http://localhost:3100") });
  const guest = await browser.newPage({ baseURL: process.env.BASE_URL || "http://localhost:3100" });
  try {
    await login(page, seed.customer);
    await page.goto("/tram-cuu-ho/dang-tin");
    await createFields(page, title);
    await page.getByLabel("Loài", { exact: true }).selectOption("cat");
    await page.getByLabel("Giống", { exact: true }).fill("ALN");
    await page.getByRole("checkbox", { name: "Xám", exact: true }).check();
    await page.getByRole("checkbox", { name: "Trắng", exact: true }).check();
    await page.getByLabel("Độ dài lông", { exact: true }).selectOption("short");
    await page.getByLabel("Giới tính", { exact: true }).selectOption("female");
    await page.getByLabel("Hoa văn lông", { exact: true }).selectOption("bicolor");
    await page.getByLabel("Cân nặng ước tính (kg)", { exact: true }).fill("2.5");
    await page.getByLabel("Dấu hiệu nhận dạng", { exact: true }).fill("Đuôi cụt, vòng cổ đỏ");
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
    const png = await page.screenshot();
    await page.locator('input[type="file"]').setInputFiles([
      { name: "qa.png", mimeType: "image/png", buffer: png },
      { name: "qa-second.png", mimeType: "image/png", buffer: png },
    ]);
    await expect(page.getByRole("button", { name: "Xóa ảnh" })).toHaveCount(2);
    const cover = await page.getByAltText("Ảnh đính kèm 2", { exact: true }).getAttribute("src");
    await page.getByRole("button", { name: "Làm ảnh đại diện" }).click();
    await expect(page.getByAltText("Ảnh đính kèm 1", { exact: true })).toHaveAttribute("src", cover!);
    await page.getByRole("button", { name: "Lưu tin", exact: true }).click();
    await expect(page).toHaveURL(/\/account\/community$/);
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
    await login(staff, seed.owner);
    await staff.goto("/admin/community");
    await expect.poll(() => staff.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
    const row = staff.getByRole("row").filter({ hasText: title });
    await row.getByRole("button", { name: "Duyệt", exact: true }).click();
    await staff.getByRole("button", { name: "Xác nhận", exact: true }).click();
    await assertNoTotpPrompt(staff);
    await expect(row).toContainText("Đã duyệt");
    await guest.goto("/tram-cuu-ho?post_type=lost_pet");
    await guest.getByLabel("Tìm theo từ khóa", { exact: true }).fill("ALN xam duoi cut");
    await guest.getByLabel("Loài", { exact: true }).selectOption("cat");
    await guest.getByRole("checkbox", { name: "Xám", exact: true }).check();
    await guest.getByRole("checkbox", { name: "Trắng", exact: true }).check();
    await guest.getByText("Lọc thêm", { exact: true }).click();
    await guest.getByLabel("Giống", { exact: true }).fill("ALN");
    await guest.getByLabel("Độ dài lông", { exact: true }).selectOption("short");
    await guest.getByRole("button", { name: "Tìm tin", exact: true }).click();
    await expect(guest).toHaveURL(/colors=gray%2Cwhite/);
    await expect(guest.getByRole("link", { name: "Xóa bộ lọc" })).toHaveAttribute("href", "/tram-cuu-ho?post_type=lost_pet");
    await expect.poll(() => guest.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
    await guest.screenshot({ path: info.outputPath("rescue-filters.png"), fullPage: true });
    const filteredUrl = guest.url();
    await guest.goto("/tram-cuu-ho?post_type=lost_pet&date_from=2026-10-23&date_to=2026-10-22");
    await expect(guest.getByRole("alert").filter({ hasText: "Chưa tải được tin." })).toContainText("ngày bắt đầu không sau ngày kết thúc");
    await expect(guest.getByRole("button", { name: "Tìm tin", exact: true })).toBeVisible();
    await guest.goto(filteredUrl);
    await guest.getByRole("heading", { name: title }).click();
    await expect(guest.getByRole("heading", { name: title })).toBeVisible();
    await expect(guest.locator("body")).not.toContainText("0901234567");
    const image = guest.locator('img[alt="' + title + '"]').first();
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0);
    await expect(image).toHaveAttribute("src", cover!);
    await expect(guest.getByText("Đuôi cụt, vòng cổ đỏ", { exact: false })).toBeVisible();
    await expect(guest.getByText("2,5 kg", { exact: true })).toBeVisible();
    await guest.getByRole("button", { name: `Xem ảnh 1 của ${title}`, exact: true }).click();
    const gallery = guest.getByRole("dialog", { name: `Ảnh của ${title}`, exact: true });
    await expect(gallery).toBeVisible();
    await gallery.getByRole("button", { name: "Phóng to", exact: true }).click();
    await expect(gallery.getByRole("button", { name: "Thu nhỏ", exact: true })).toBeVisible();
    await gallery.getByRole("button", { name: "Ảnh tiếp →", exact: true }).click();
    await expect(gallery.getByText("Ảnh 2 / 2", { exact: true })).toBeVisible();
    await guest.screenshot({ path: info.outputPath("rescue-gallery.png"), fullPage: true });
    await gallery.getByRole("button", { name: "Đóng ảnh", exact: true }).click();
    await expect(gallery).toBeHidden();
    await guest.screenshot({ path: info.outputPath("rescue-detail.png"), fullPage: true });
    await page.reload();
    const ownPost = page.getByRole("article").filter({ hasText: title });
    await ownPost.getByRole("link", { name: "Sửa tin", exact: true }).click();
    await expect(page.getByLabel("Giống", { exact: true })).toHaveValue("Mèo Anh lông ngắn");
    await expect(page.getByRole("checkbox", { name: "Xám", exact: true })).toBeChecked();
    await expect(page.getByLabel("Độ dài lông", { exact: true })).toHaveValue("short");
    await expect(page.getByLabel("Dấu hiệu nhận dạng", { exact: true })).toHaveValue("Đuôi cụt, vòng cổ đỏ");
    await page.goto("/account/community");
    page.once("dialog", dialog => dialog.accept());
    await ownPost.getByRole("button", { name: "Đã đoàn tụ", exact: true }).click();
    await expect(ownPost).toContainText("Đã giải quyết");
    await guest.reload();
    await expect(guest.getByText("Đã đoàn tụ", { exact: true })).toBeVisible();
    await expect(guest.getByRole("button", { name: "Xem liên hệ" })).toHaveCount(0);
  } finally { await staff.close(); await guest.close(); }
});

test("adoption: publish, apply, choose recipient and confirm handover", async ({ page, browser }, info) => {
  test.skip(info.project.name === "tablet", "desktop and mobile exercise full workflow");
  const title = `QA adoption ${info.project.name} ${Date.now()}`;
  const staff = await browser.newPage({ baseURL: process.env.BASE_URL || "http://localhost:3100" });
  try {
    await login(staff, seed.owner);
    await staff.goto("/admin/community/new");
    await createFields(staff, title);
    await staff.getByLabel("Tuổi ước tính (tháng)").fill("8");
    await staff.getByRole("button", { name: "Lưu tin", exact: true }).click();
    await assertNoTotpPrompt(staff);
    await expect(staff).toHaveURL(/\/admin\/community$/);
    await login(page, seed.customer);
    await page.goto("/tram-cuu-ho?post_type=adoption");
    await page.getByRole("heading", { name: title }).click();
    await page.getByLabel("Họ tên", { exact: true }).fill("Người nhận QA");
    await page.getByLabel("Điện thoại", { exact: true }).fill("0902345678");
    await page.getByLabel("Địa chỉ", { exact: true }).fill("Địa chỉ chỉ dùng kiểm thử");
    await page.getByLabel("Điều kiện sống và kinh nghiệm chăm sóc").fill("Có nhà ở và kinh nghiệm chăm sóc mèo.");
    await page.getByRole("button", { name: "Gửi hồ sơ", exact: true }).click();
    await expect(page.getByText("Đã gửi hồ sơ.", { exact: false })).toBeVisible();
    await staff.goto("/admin/community/adoptions");
    const article = staff.getByRole("article").filter({ hasText: title });
    await article.getByRole("button", { name: "Đã liên hệ", exact: true }).click();
    await assertNoTotpPrompt(staff);
    await expect(article.getByRole("button", { name: "Chọn người nhận", exact: true })).toBeVisible();
    await article.getByRole("button", { name: "Chọn người nhận", exact: true }).click();
    await assertNoTotpPrompt(staff);
    await expect(article.getByRole("button", { name: "Xác nhận bàn giao", exact: true })).toBeVisible();
    staff.once("dialog", dialog => dialog.accept());
    await article.getByRole("button", { name: "Xác nhận bàn giao", exact: true }).click();
    await assertNoTotpPrompt(staff);
    await expect(article).toContainText("Đã bàn giao");
    await page.goto("/account/adoption-requests");
    await expect(page.getByRole("article").filter({ hasText: title })).toContainText("Đã bàn giao");
    await page.screenshot({ path: info.outputPath("adoption-completed.png"), fullPage: true });
  } finally { await staff.close(); }
});
