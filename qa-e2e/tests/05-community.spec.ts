import { test, expect, type Page } from "@playwright/test";
import { createHmac } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const seedPath = path.resolve(__dirname, "../community-qa.json");
type Credential = { email: string; password: string; totp: string };
const seed: Record<string, Credential> = fs.existsSync(seedPath) ? JSON.parse(fs.readFileSync(seedPath, "utf8")) : {};
test.skip(!seed.customer, "Requires isolated API started with backend/scripts/community_qa.py");

function totp(secret: string) {
  let bits = "";
  for (const char of secret) bits += "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567".indexOf(char).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g)!.map(byte => parseInt(byte, 2)));
  const counter = Buffer.alloc(8); counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const hash = createHmac("sha1", key).update(counter).digest();
  const value = hash.readUInt32BE(hash[19] & 15) & 0x7fffffff;
  return String(value % 1000000).padStart(6, "0");
}

async function login(page: Page, credential: Credential) {
  await page.goto("/login");
  await page.getByLabel("Email hoặc số điện thoại").fill(credential.email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(credential.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL(/\/(account|admin)$/);
}

async function confirmTotp(page: Page) {
  await expect(page.getByRole("heading", { name: "Xác thực TOTP" })).toBeVisible();
  await page.getByPlaceholder("000000").fill(totp(seed.owner.totp));
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Xác thực TOTP" })).toBeHidden();
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
    const png = await page.screenshot();
    await page.locator('input[type="file"]').setInputFiles({ name: "qa.png", mimeType: "image/png", buffer: png });
    await expect(page.getByRole("button", { name: "Xóa ảnh" })).toBeVisible();
    await page.getByRole("button", { name: "Lưu tin", exact: true }).click();
    await expect(page).toHaveURL(/\/account\/community$/);
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
    await login(staff, seed.owner);
    await staff.goto("/admin/community");
    await expect.poll(() => staff.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
    const row = staff.getByRole("row").filter({ hasText: title });
    await row.getByRole("button", { name: "Duyệt", exact: true }).click();
    await staff.getByRole("button", { name: "Xác nhận", exact: true }).click();
    await confirmTotp(staff);
    await expect(row).toContainText("Đã duyệt");
    await guest.goto("/tram-cuu-ho?post_type=lost_pet");
    await guest.getByRole("heading", { name: title }).click();
    await expect(guest.getByRole("heading", { name: title })).toBeVisible();
    await expect(guest.locator("body")).not.toContainText("0901234567");
    const image = guest.locator('img[alt="' + title + '"]').first();
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0);
    await guest.screenshot({ path: info.outputPath("rescue-detail.png"), fullPage: true });
    await page.reload();
    const ownPost = page.getByRole("article").filter({ hasText: title });
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
    await confirmTotp(staff);
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
    await confirmTotp(staff);
    await expect(article.getByRole("button", { name: "Chọn người nhận", exact: true })).toBeVisible();
    await article.getByRole("button", { name: "Chọn người nhận", exact: true }).click();
    await confirmTotp(staff);
    await expect(article.getByRole("button", { name: "Xác nhận bàn giao", exact: true })).toBeVisible();
    staff.once("dialog", dialog => dialog.accept());
    await article.getByRole("button", { name: "Xác nhận bàn giao", exact: true }).click();
    await confirmTotp(staff);
    await expect(article).toContainText("Đã bàn giao");
    await page.goto("/account/adoption-requests");
    await expect(page.getByRole("article").filter({ hasText: title })).toContainText("Đã bàn giao");
    await page.screenshot({ path: info.outputPath("adoption-completed.png"), fullPage: true });
  } finally { await staff.close(); }
});
