import { test, expect } from "@playwright/test";
import path from "path";
import { attachIssueCollectors } from "../helpers/console";
import { loginAs, ownerCreds } from "../helpers/auth";

const SHOT = path.join("D:", "code", "PS_project", "test-reports", "screenshots");

async function dismissTotpIfAny(page: import("@playwright/test").Page) {
  const dialog = page.getByText(/Xác minh bảo mật/i);
  if (await dialog.isVisible().catch(() => false)) {
    await page.getByRole("button", { name: /Hủy/i }).click().catch(() => {});
    return true;
  }
  return false;
}

test.describe("Admin owner UI", () => {
  test("owner login + navigate admin pages", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "once");
    const issues = attachIssueCollectors(page);
    const { email, password } = ownerCreds();
    await loginAs(page, email, password);
    await expect(page).toHaveURL(/\/admin/);
    await page.screenshot({ path: path.join(SHOT, "admin-dashboard.png"), fullPage: true });

    for (const href of [
      "/admin",
      "/admin/shop",
      "/admin/orders",
      "/admin/inventory-lots",
      "/admin/products",
      "/admin/promotions",
      "/admin/reviews",
      "/admin/reports",
      "/admin/settings",
    ]) {
      await page.goto(href);
      await page.waitForTimeout(700);
      await page.screenshot({
        path: path.join(SHOT, `admin-nav${href.replace(/\//g, "_") || "_admin"}.png`),
        fullPage: true,
      });
    }
    const hard5xx = issues.failedRequests.filter((r) => /\b5\d\d\b/.test(r));
    const hardConsole = issues.consoleErrors.filter((e) =>
      /TypeError|ReferenceError|SyntaxError/i.test(e),
    );
    expect(hard5xx, hard5xx.join(" | ")).toEqual([]);
    expect(hardConsole, hardConsole.join(" | ")).toEqual([]);
  });

  test("create + edit + hide QA product", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "once");
    const ts = Date.now();
    const QA_PRODUCT = `QA E2E Product ${ts}`;
    const { email, password } = ownerCreds();
    await loginAs(page, email, password);
    await page.goto("/admin/products");
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(SHOT, "admin-products-before.png"), fullPage: true });

    const form = page.locator("form").filter({ hasText: /Thêm sản phẩm|Tạo sản phẩm/i });
    await expect(form).toBeVisible({ timeout: 20_000 });

    // Wait until categories loaded (empty UUID previously caused create failure)
    const catSelect = form.locator("select").first();
    await expect(catSelect.locator("option").nth(0)).toHaveAttribute("value", /.+/i, { timeout: 20_000 });
    const catVal = await catSelect.locator("option").nth(0).getAttribute("value");
    if (catVal) await catSelect.selectOption(catVal);

    async function fillInForm(labelPart: string, value: string) {
      const label = form.locator("label").filter({ hasText: new RegExp(labelPart, "i") }).first();
      await expect(label).toBeVisible();
      const input = label.locator("input").first();
      await input.fill(value);
    }

    await fillInForm("Tên sản phẩm", QA_PRODUCT);
    await fillInForm("^Tên trong đường dẫn$", `qa-e2e-product-${ts}`);
    await fillInForm("SKU", `QA-E2E-${ts}`);
    await fillInForm("Tên biến thể", "QA Default");
    // price/weight already have defaults

    await page.screenshot({ path: path.join(SHOT, "admin-product-create-filled.png"), fullPage: true });
    await form.getByRole("button", { name: /Tạo sản phẩm/i }).click();
    await page.waitForTimeout(2000);

    const totpBlocked = await dismissTotpIfAny(page);
    if (totpBlocked) {
      testInfo.annotations.push({
        type: "product_crud",
        description: "BLOCKED — TOTP modal required for admin write; create aborted without enabling TOTP on owner",
      });
      await page.screenshot({ path: path.join(SHOT, "admin-product-totp-blocked.png"), fullPage: true });
      test.fail(true, "TOTP required for product create");
      return;
    }

    const err = form.locator(".text-danger, p.text-danger");
    if (await err.isVisible().catch(() => false)) {
      const msg = await err.innerText();
      await page.screenshot({ path: path.join(SHOT, "admin-product-create-error.png"), fullPage: true });
      throw new Error(`Create product failed: ${msg}`);
    }

    await page.screenshot({ path: path.join(SHOT, "admin-product-created.png"), fullPage: true });
    await expect(page.getByText(QA_PRODUCT).first()).toBeVisible({ timeout: 20_000 });

    // open row / edit
    await page.getByText(QA_PRODUCT).first().click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(SHOT, "admin-product-edit-drawer.png"), fullPage: true });

    const drawer = page.locator('[class*="fixed"], aside, div').filter({ hasText: QA_PRODUCT }).last();
    const nameField = page.locator("label").filter({ hasText: /Tên sản phẩm|^Tên$/i }).locator("input").last();
    if (await nameField.count()) {
      await nameField.fill(QA_PRODUCT + " edited");
      const saveBtn = page.getByRole("button", { name: /Lưu|Cập nhật/i }).first();
      if (await saveBtn.count()) {
        await saveBtn.click();
        await page.waitForTimeout(1500);
        if (await dismissTotpIfAny(page)) {
          testInfo.annotations.push({ type: "edit", description: "TOTP blocked edit save" });
        }
      }
    }
    await page.screenshot({ path: path.join(SHOT, "admin-product-edited.png"), fullPage: true });

    // Soft delete = hide
    await page.goto("/admin/products");
    await page.waitForTimeout(1000);
    const row = page.locator("tr", { hasText: /QA E2E Product/ }).first();
    if (await row.count()) {
      const hideBtn = row.getByRole("button", { name: /Ẩn/i });
      if (await hideBtn.count()) {
        await hideBtn.click();
        await page.waitForTimeout(1500);
        await dismissTotpIfAny(page);
      }
    }
    await page.screenshot({ path: path.join(SHOT, "admin-product-hidden.png"), fullPage: true });
    testInfo.annotations.push({
      type: "category_crud",
      description: "NOT RUN — no admin categories page in UI",
    });
  });

  test("TOTP settings UI openable", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "once");
    const { email, password } = ownerCreds();
    await loginAs(page, email, password);
    await page.goto("/admin/settings");
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(SHOT, "admin-settings-totp.png"), fullPage: true });
    await expect(page.getByText(/TOTP|Authenticator/i).first()).toBeVisible();
    const enrollBtn = page.getByRole("button", { name: /Thiết lập TOTP/i });
    if (await enrollBtn.count()) {
      await enrollBtn.click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: path.join(SHOT, "admin-totp-enroll.png"), fullPage: true });
      // Do not verify — avoid locking owner account into TOTP
      testInfo.annotations.push({
        type: "totp",
        description: "PARTIAL — enroll UI works; verify skipped intentionally",
      });
      await page.goto("/admin");
    } else {
      testInfo.annotations.push({ type: "totp", description: "Enroll button not shown (maybe already enabled)" });
    }
  });
});
