import { test, expect } from "@playwright/test";
import path from "path";
import { attachIssueCollectors } from "../helpers/console";

const SHOT = path.join("D:", "code", "PS_project", "test-reports", "screenshots");

test.describe("Customer storefront flow", () => {
  test("browse → cart → COD checkout → track", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "customer flow once on desktop");
    const issues = attachIssueCollectors(page);
    const ts = Date.now();
    const guestPhone = `0977${String(ts).slice(-6)}`;

    await page.goto("/shop");
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SHOT, "flow-home.png"), fullPage: true });

    const productLink = page.locator('a[href^="/p/"]').first();
    await expect(productLink).toBeVisible({ timeout: 20_000 });
    await productLink.click();
    await page.waitForURL(/\/p\//);
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(SHOT, "flow-product.png"), fullPage: true });

    const addBtn = page.getByRole("button", { name: /Thêm vào giỏ/i });
    await expect(addBtn).toBeVisible({ timeout: 15_000 });
    await addBtn.click();
    await expect(page.getByText(/Đã thêm vào giỏ|thêm vào giỏ/i).first()).toBeVisible({ timeout: 10_000 }).catch(() => {});
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(SHOT, "flow-added-cart.png"), fullPage: true });

    await page.goto("/cart");
    await page.waitForTimeout(800);
    await expect(page.getByRole("heading", { name: /Giỏ hàng/i })).toBeVisible();
    await expect(page.getByText(/Chưa có sản phẩm trong giỏ/i)).toHaveCount(0);
    await page.screenshot({ path: path.join(SHOT, "flow-cart.png"), fullPage: true });

    await page.goto("/checkout");
    await page.waitForTimeout(500);

    async function fillField(labelText: string, value: string) {
      const label = page.locator("label").filter({ hasText: labelText }).first();
      await expect(label).toBeVisible({ timeout: 10_000 });
      await label.locator("input").fill(value);
    }

    await fillField("Họ tên", "QA E2E Guest");
    await fillField("Số điện thoại", guestPhone);
    await fillField("Email", `qa.e2e.guest.${ts}@example.com`);
    await fillField("Tỉnh", "HCM");
    await fillField("Quận", "Q1");
    await fillField("Phường", "Ben Nghe");
    await fillField("Địa chỉ", "99 QA E2E Street");

    await page.locator('input[type="radio"][name="payment"]').nth(0).check({ force: true });
    await page.screenshot({ path: path.join(SHOT, "flow-checkout-filled.png"), fullPage: true });

    await page.getByRole("button", { name: /Kiểm tra tổng tiền/i }).click();
    await expect(page.getByRole("region", { name: "Chi tiết thanh toán" })).toBeVisible();
    await page.getByRole("button", { name: /Xác nhận đặt hàng/i }).click();
    await expect(page.getByText(/Đặt hàng thành công/i)).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(SHOT, "flow-checkout-result.png"), fullPage: true });

    const codeEl = page.locator("strong.font-mono").first();
    await expect(codeEl).toBeVisible();
    const orderCode = (await codeEl.innerText()).trim();
    expect(orderCode.length).toBeGreaterThan(4);

    // Probe query-param deep link (known crash path)
    await page.goto(`/track-order?order_code=${encodeURIComponent(orderCode)}&phone=${encodeURIComponent(guestPhone)}`);
    await page.waitForTimeout(1500);
    const crashed = await page.getByText(/Application error|client-side exception/i).isVisible().catch(() => false);
    await page.screenshot({ path: path.join(SHOT, "flow-track-query.png"), fullPage: true });
    if (crashed) {
      testInfo.annotations.push({
        type: "bug",
        description: "P1 — /track-order?order_code&phone throws client-side Application error",
      });
    }

    // Manual form path (workaround)
    await page.goto("/track-order");
    await page.waitForTimeout(500);
    await page.locator("input.font-mono, input[placeholder*='AB12']").first().fill(orderCode);
    await page.locator('input[type="tel"]').first().fill(guestPhone);
    await page.getByRole("button", { name: /^Tra cứu$/i }).click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOT, "flow-track.png"), fullPage: true });
    const manualCrash = await page.getByText(/Application error|client-side exception/i).isVisible().catch(() => false);
    expect(manualCrash, "track manual form should not crash").toBeFalsy();
    await expect(page.getByText(/Kết quả/i).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("body")).toContainText(orderCode);
    // Surface query-param crash as test failure if present
    expect(crashed, "track-order query deep link should not crash").toBeFalsy();

    const hardNet = issues.failedRequests.filter((r) => /\b5\d\d\b/.test(r));
    expect(hardNet, hardNet.join(" | ")).toEqual([]);
  });

  test("VietQR checkout shows payment status", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "once");
    const ts = Date.now();
    await page.goto("/shop");
    await page.locator('a[href^="/p/"]').first().click();
    await page.waitForURL(/\/p\//);
    await page.getByRole("button", { name: /Thêm vào giỏ/i }).click();
    await page.waitForTimeout(800);
    await page.goto("/checkout");

    async function fillField(labelText: string, value: string) {
      const label = page.locator("label").filter({ hasText: labelText }).first();
      await label.locator("input").fill(value);
    }
    await fillField("Họ tên", "QA E2E VietQR");
    await fillField("Số điện thoại", `0988${String(ts).slice(-6)}`);
    await fillField("Email", `qa.e2e.vietqr.${ts}@example.com`);
    await fillField("Tỉnh", "HCM");
    await fillField("Quận", "Q1");
    await fillField("Phường", "Ben Nghe");
    await fillField("Địa chỉ", "12 QA VietQR");
    test.skip(!(await page.locator('input[type="radio"][name="payment"]').nth(1).isVisible()), "Online payment is not configured in this environment");
    await page.locator('input[type="radio"][name="payment"]').nth(1).check({ force: true });
    await page.getByRole("button", { name: /Kiểm tra tổng tiền/i }).click();
    await expect(page.getByRole("region", { name: "Chi tiết thanh toán" })).toBeVisible();
    await page.getByRole("button", { name: /Xác nhận đặt hàng/i }).click();
    await expect(page.getByText(/Đặt hàng thành công/i)).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(SHOT, "flow-vietqr-result.png"), fullPage: true });
    const body = await page.innerText("body");
    expect(/VietQR/i.test(body)).toBeTruthy();
    expect(/chờ|thanh toán|QR/i.test(body)).toBeTruthy();
  });
});
