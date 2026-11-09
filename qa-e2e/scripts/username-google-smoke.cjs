// Browser contract checks with mocked authentication; no real account is created.
const { chromium, expect } = require('@playwright/test');
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [390, 1440]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      await page.route('**/api/proxy/api/v1/auth/google/config', r => r.fulfill({ json: { client_id: 'test-client', nonce: 'test-nonce' } }));
      await page.route('https://accounts.google.com/gsi/client', r => r.fulfill({ contentType: 'application/javascript', body: `window.google={accounts:{id:{initialize(o){window.testGoogle=o},renderButton(el){const b=document.createElement('button');b.textContent='Google test';b.onclick=()=>window.testGoogle.callback({credential:'fixture-google-token'});el.appendChild(b)}}}};` }));
      await page.route('**/api/proxy/api/v1/auth/register', async r => {
        const body = r.request().postDataJSON();
        expect(body.username).toBe('new_account');
        expect(body.email).toBeUndefined(); expect(body.phone).toBeUndefined();
        await r.fulfill({ status: 409, json: { detail: 'Tên tài khoản đã được sử dụng' } });
      });
      await page.goto('http://localhost/register');
      await page.getByLabel('Tên tài khoản', { exact: true }).fill('new_account');
      await expect(page.getByText('Email hoặc số điện thoại', { exact: true })).toHaveCount(0);
      await page.getByLabel('Mật khẩu (≥ 8 ký tự)').fill('Password123');
      await page.getByLabel('Xác nhận mật khẩu').fill('Password123');
      await page.getByRole('button', { name: 'Đăng ký', exact: true }).click();
      await expect(page.getByText('Tên tài khoản đã được sử dụng', { exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Google test' })).toBeVisible();
      await page.route('**/api/proxy/api/v1/auth/google', async r => {
        expect(r.request().postDataJSON().id_token).toBe('fixture-google-token');
        await r.fulfill({ json: { requires_totp: true } });
      });
      await page.getByRole('button', { name: 'Google test' }).click();
      await expect(page.getByLabel('Mã xác thực quản trị')).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.close();
      console.log(`Username and Google UI passed at ${width}px`);
    }
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
