import { Page, expect } from "@playwright/test";

export async function loginAs(page: Page, identifier: string, password: string) {
  await page.goto("/login");
  await page.getByLabel(/Email|điện thoại|phone/i).fill(identifier);
  await page.getByLabel(/Mật khẩu|Password/i).fill(password);
  await page.getByRole("button", { name: /Đăng nhập/i }).click();
  await page.waitForURL(/\/(admin|account)/, { timeout: 30_000 });
}

export function ownerCreds() {
  const email = process.env.OWNER_EMAIL || "owner@demo.com";
  const password = process.env.OWNER_PASSWORD || "OwnerPass123";
  return { email, password };
}
