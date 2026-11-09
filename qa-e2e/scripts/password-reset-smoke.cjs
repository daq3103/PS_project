// UI-only checks: mocked recovery responses never send mail or change real accounts.
const { chromium, expect } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [390, 1440]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      let configured = false;
      let resetCount = 0;
      await page.route('**/api/proxy/api/v1/auth/password-reset/**', async route => {
        const url = new URL(route.request().url());
        if (url.pathname.endsWith('/config')) return route.fulfill({ json: { available: configured } });
        const body = route.request().postDataJSON();
        if (url.pathname.endsWith('/request')) {
          expect(body.email).toBe('customer@gmail.com');
          return route.fulfill({ status: 202, json: { message: 'Kiểm tra hộp thư' } });
        }
        if (url.pathname.endsWith('/verify-code')) {
          expect(body.email).toBe('customer@gmail.com');
          return body.code === '012345'
            ? route.fulfill({ json: { token: 'ui-fixture-reset-token-only' } })
            : route.fulfill({ status: 400, json: { detail: 'Mã không đúng hoặc đã hết hạn.' } });
        }
        expect(body.token).toBe('ui-fixture-reset-token-only');
        expect(body.password).toBe('NewPassword123');
        resetCount++;
        return route.fulfill({ status: 204 });
      });
      await page.goto('http://localhost/forgot-password');
      await expect(page.getByRole('button', { name: 'Gửi mã xác minh', exact: true })).toBeDisabled();
      await expect(page.getByText('Gửi email lấy lại mật khẩu hiện chưa sẵn sàng.', { exact: false })).toBeVisible();
      configured = true;
      await page.reload();
      await page.getByLabel('Email đăng ký').fill('customer@gmail.com');
      await page.getByRole('button', { name: 'Gửi mã xác minh', exact: true }).click();
      await expect(page.getByRole('button', { name: /Gửi lại mã sau/ })).toBeDisabled();
      await page.getByLabel('Mã xác minh', { exact: true }).fill('111111');
      await page.getByRole('button', { name: 'Xác minh mã', exact: true }).click();
      await expect(page.getByRole('alert').filter({ hasText: 'Mã không đúng' })).toBeVisible();
      await page.getByLabel('Mã xác minh', { exact: true }).fill('012345');
      await page.getByRole('button', { name: 'Xác minh mã', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Đặt mật khẩu mới' })).toBeVisible();
      await page.getByLabel('Mật khẩu mới', { exact: true }).fill('NewPassword123');
      await page.getByLabel('Nhập lại mật khẩu mới', { exact: true }).fill('WrongPassword123');
      await page.getByRole('button', { name: 'Lưu mật khẩu mới' }).click();
      await expect(page.getByRole('alert').filter({ hasText: 'Hai mật khẩu chưa khớp.' })).toBeVisible();
      expect(resetCount).toBe(0);
      await page.getByLabel('Nhập lại mật khẩu mới', { exact: true }).fill('NewPassword123');
      await page.getByRole('button', { name: 'Lưu mật khẩu mới' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'Mật khẩu đã được đổi' })).toBeVisible();
      expect(resetCount).toBe(1);
      expect(page.url()).not.toContain('token');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.close();
      console.log(`OTP recovery UI passed at ${width}px`);
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
