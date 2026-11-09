// Navigation checks against a local fixture API; no real accounts or database writes.
const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const { chromium, expect } = require('@playwright/test');

const root = path.resolve(__dirname, '../..');
const baseURL = 'http://127.0.0.1:3110';
let rescueEnabled = true;
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const role = /qa_role=([^;]+)/.exec(req.headers.cookie || '')?.[1];
  let value = {};
  if (url.pathname.endsWith('/auth/me')) value = { user: role ? { id: 'qa', full_name: 'Navigation QA', email: 'navigation@example.test', phone: null, role } : null };
  else if (url.pathname.endsWith('/community/config')) value = { enabled: rescueEnabled, turnstile_site_key: '' };
  else if (url.pathname.endsWith('/analytics/config')) value = { enabled: false };
  else if (url.pathname.endsWith('/community/locations')) value = { version: 'test', provinces: [] };
  else if (url.pathname.endsWith('/community/pet-options')) value = { breeds: { dog: [], cat: [], other: [] }, colors: {}, coat_lengths: {}, patterns: {}, sexes: {}, sizes: {} };
  else if (url.pathname.endsWith('/community/posts')) value = { items: [], next_cursor: null };
  else if (url.pathname.includes('/products') || url.pathname.includes('/categories')) value = [];
  else if (url.pathname.endsWith('/cart')) value = { id: 'qa', items: [], item_count: 0, subtotal: 0 };
  else if (url.pathname.includes('/dashboard')) value = { orders_today: 0, revenue_today: 0, pending_orders: 0, pending_reviews: 0, out_of_stock_variants: 0, low_stock_variants: 0, lots_expiring_30d: 0, drift_count: 0, recent_orders: [] };
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(value));
});

(async () => {
  let app, browser;
  const output = path.join(root, 'test-reports/screenshots/platform');
  fs.mkdirSync(output, { recursive: true });
  try {
    await new Promise((resolve, reject) => { server.once('error', reject); server.listen(18010, '127.0.0.1', resolve); });
    app = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', '3110'], {
      cwd: path.join(root, 'frontend'), env: { ...process.env, INTERNAL_API_URL: 'http://127.0.0.1:18010' }, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
    });
    app.stderr.on('data', data => process.stderr.write(data));
    await expect.poll(async () => { try { return (await fetch(baseURL)).status; } catch { return 0; } }, { timeout: 60000 }).toBe(200);
    browser = await chromium.launch({ headless: true });
    for (const width of [1440, 390, 320]) {
      const context = await browser.newContext({ baseURL, viewport: { width, height: 900 } });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const primary = page.getByRole('navigation', { name: 'Khu vực chính', exact: true });
      await page.goto('/');
      await expect(page).toHaveTitle(/PetHome/);
      await expect(page.getByRole('heading', { name: 'Shop', exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Trạm cứu hộ', exact: true })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Khám phá Trạm cứu hộ' })).toBeVisible();
      await expect(primary.locator('[aria-current]')).toHaveCount(0);
      await expect(page.getByRole('link', { name: /^Giỏ hàng/ })).toHaveCount(0);
      await expect(page.locator('#section-navigation')).toHaveCount(0);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({ path: path.join(output, `home-${width}.png`), fullPage: true });
      await primary.getByRole('link', { name: 'Shop', exact: true }).click();
      await expect(page).toHaveURL(/\/shop$/);
      await expect(page).toHaveTitle('Shop | PetHome');
      await expect(primary.getByRole('link', { name: 'Shop', exact: true })).toHaveAttribute('aria-current', 'true');
      await expect(page.getByRole('link', { name: /^Giỏ hàng/ })).toBeVisible();
      await page.screenshot({ path: path.join(output, `shop-${width}.png`), fullPage: true });
      await primary.getByRole('link', { name: 'Trạm cứu hộ', exact: true }).click();
      await expect(page).toHaveURL(/\/tram-cuu-ho$/);
      await expect(page).toHaveTitle('Trạm cứu hộ | PetHome');
      await expect(page.getByRole('heading', { name: 'Cùng đưa các bé về nhà' })).toBeVisible();
      await expect(primary.getByRole('link', { name: 'Trạm cứu hộ', exact: true })).toHaveAttribute('aria-current', 'true');
      await expect(page.getByRole('link', { name: /^Giỏ hàng/ })).toHaveCount(0);
      await page.screenshot({ path: path.join(output, `rescue-${width}.png`), fullPage: true });
      if (width < 1024) await page.getByRole('button', { name: 'Khám phá cứu hộ' }).click();
      await page.getByRole('navigation', { name: 'Menu Trạm cứu hộ' }).getByRole('link', { name: 'Nhận nuôi', exact: true }).click();
      await expect(page).toHaveURL(/post_type=adoption/);
      await page.getByRole('link', { name: 'PetHome — Trang chủ', exact: true }).click();
      await expect(page).toHaveURL(baseURL + '/');
      await page.goto('/login');
      await expect(page.locator('#section-navigation')).toHaveCount(0);
      await context.addCookies([{ name: 'access_token', value: 'fixture-only', url: baseURL }, { name: 'qa_role', value: 'owner', url: baseURL }]);
      await page.goto('/account');
      await expect(page.getByRole('heading', { name: 'Shop', exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Trạm cứu hộ', exact: true })).toBeVisible();
      await page.screenshot({ path: path.join(output, `account-${width}.png`), fullPage: true });
      await page.goto('/admin');
      await expect(page.getByRole('heading', { name: 'Quản trị PetHome', exact: true })).toBeVisible();
      await expect(page.locator('main').getByRole('heading', { name: 'Shop', exact: true })).toBeVisible();
      await expect(page.locator('main').getByRole('heading', { name: 'Trạm cứu hộ', exact: true })).toBeVisible();
      if (width < 768) await page.getByRole('button', { name: 'Menu', exact: true }).click();
      const adminNav = page.getByRole('navigation', { name: 'Điều hướng quản trị' }).filter({ visible: true });
      await expect(adminNav.getByRole('region', { name: 'Shop', exact: true })).toBeVisible();
      await expect(adminNav.getByRole('region', { name: 'Trạm cứu hộ', exact: true })).toBeVisible();
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({ path: path.join(output, `admin-${width}.png`), fullPage: true });
      await adminNav.getByRole('link', { name: 'Tổng quan Shop', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Tổng quan Shop', exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Đơn mới nhất', exact: true })).toBeVisible();
      await page.screenshot({ path: path.join(output, `admin-shop-${width}.png`), fullPage: true });
      for (const role of ['warehouse_staff', 'cskh_staff']) {
        await context.addCookies([{ name: 'qa_role', value: role, url: baseURL }]);
        await page.goto('/admin');
        await expect(page.locator('main').getByRole('heading', { name: 'Shop', exact: true })).toBeVisible();
        await expect(page.locator('main').getByRole('heading', { name: 'Trạm cứu hộ', exact: true })).toHaveCount(role === 'cskh_staff' ? 1 : 0);
        await expect(page.getByRole('link', { name: 'Truy cập & hiệu năng', exact: true })).toHaveCount(0);
      }
      await context.addCookies([{ name: 'qa_role', value: 'customer', url: baseURL }]);
      await page.goto('/admin');
      await expect(page).toHaveURL(/\/login\?next=/);
      rescueEnabled = false;
      await page.goto('/');
      await expect(page.getByText('Trạm cứu hộ hiện chưa sẵn sàng.', { exact: false })).toBeVisible();
      await expect(primary.getByRole('link', { name: 'Trạm cứu hộ', exact: true })).toHaveCount(0);
      rescueEnabled = true;
      expect(errors).toEqual([]);
      await context.close();
      console.log(`PASS: platform navigation, admin roles, feature flag and layout at ${width}px`);
    }
  } finally {
    if (browser) await browser.close();
    if (app && app.exitCode === null) { const exited = new Promise(resolve => app.once('exit', resolve)); app.kill(); await exited; }
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
