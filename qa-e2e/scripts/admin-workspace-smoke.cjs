// Tests the production frontend against a synthetic API. No real account or database writes.
const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs');
const { spawn, spawnSync } = require('node:child_process');
const { chromium, expect } = require('@playwright/test');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'frontend/node_modules/typescript'));
const navigation = {};
require('node:vm').runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root, 'frontend/src/lib/admin-navigation.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports: navigation });
for (const route of ['/admin/rescue/finance', '/admin/rescue/activity', '/admin/community/adoptions']) {
  expect(navigation.activeAdminHref(route, navigation.ADMIN_GROUPS)).toBe(route);
}
expect(navigation.adminGroups('customer', ['warehouse'])).toEqual([]);
expect(navigation.adminGroups('warehouse_staff', [])).toEqual([]);
const name = 'pethome-admin-workspace-smoke';
const base = 'http://127.0.0.1:3147';
const stamp = new Date().toISOString();
let user, failedSource = false;
let calls = [];
const fixtureUser = (role, permissions = []) => ({ id: '11111111-1111-4111-8111-111111111111', full_name: 'Nhân viên thử nghiệm', email: 'fixture@example.com', role, staff_permissions: permissions, totp_enabled: true });
const server = http.createServer((req, res) => {
  const p = new URL(req.url, 'http://localhost').pathname;
  calls.push(p);
  let data = {};
  if (p.endsWith('/auth/me')) data = { user, admin_verified: true };
  else if (p.endsWith('/analytics/config')) data = { enabled: false };
  else if (p.endsWith('/admin/dashboard')) data = { orders_today: 5, revenue_today: 200000, pending_orders: 3, pending_reviews: 2, drift_count: 0, out_of_stock_variants: 1, low_stock_variants: 2, lots_expiring_30d: 0, recent_orders: [] };
  else if (p.endsWith('/community/metrics')) data = { pending_posts: 4, pending_reports: 1, active_applications: 2, completed_adoptions: 0, resolved_posts: 0, pending_jobs: 0, failed_jobs: 0, oldest_pending_at: null };
  else if (p.endsWith('/admin/operations')) data = { jobs: [], cases: [] };
  else if (p.endsWith('/analytics/traffic')) data = { enabled: true, summary: { visitors: 12, sessions: 14, views: 32 }, online: 2 };
  else if (p.endsWith('/analytics/system')) {
    if (failedSource) { res.writeHead(503, { 'Content-Type': 'application/json' }); res.end('{}'); return; }
    data = { generated_at: stamp, resources: { container_memory_bytes: 100, container_limit_bytes: 500, disk_percent: 30 }, services: { postgres: { status: 'up' }, redis_cache: { status: 'up' }, redis_queue: { status: 'up', worker_heartbeat_present: true } }, api: { available: true, server_errors: 0 } };
  }
  res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(data));
});
(async () => {
  let app, browser;
  try {
    await new Promise(resolve => server.listen(3148, '0.0.0.0', resolve));
    user = fixtureUser('owner');
    app = spawn('docker', ['run', '--rm', '--name', name, '--memory=256m', '--memory-swap=256m', '--cpus=1', '-p', '127.0.0.1:3147:3000', '-e', 'INTERNAL_API_URL=http://host.docker.internal:3148', '-e', 'NODE_OPTIONS=--max-old-space-size=192', process.env.ADMIN_TEST_IMAGE || 'pethome-admin-ui:local'], { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
    app.stderr.on('data', chunk => process.stderr.write(chunk));
    await expect.poll(async () => { try { return (await fetch(base + '/login')).status; } catch { return 0; } }, { timeout: 60000 }).toBe(200);
    browser = await chromium.launch({ headless: true });
    const cases = [
      { role: 'owner', permissions: [], groups: ['Điều hành', 'Trạm cứu hộ', 'Shop', 'Chăm sóc khách hàng', 'Hệ thống'], sources: ['dashboard', 'metrics', 'operations', 'system', 'traffic'] },
      { role: 'warehouse_staff', permissions: ['warehouse'], groups: ['Điều hành', 'Shop'], sources: ['dashboard'] },
      { role: 'cskh_staff', permissions: ['customer_support'], groups: ['Điều hành', 'Shop', 'Chăm sóc khách hàng'], sources: ['dashboard'] },
      { role: 'cskh_staff', permissions: ['rescue_manage'], groups: ['Điều hành', 'Trạm cứu hộ'], sources: ['metrics'] },
      { role: 'cskh_staff', permissions: ['rescue_care'], groups: ['Điều hành', 'Trạm cứu hộ'], sources: [] },
      { role: 'cskh_staff', permissions: ['rescue_finance'], groups: ['Điều hành', 'Trạm cứu hộ'], sources: [] },
      { role: 'warehouse_staff', permissions: ['warehouse', 'customer_support', 'rescue_manage'], groups: ['Điều hành', 'Trạm cứu hộ', 'Shop', 'Chăm sóc khách hàng'], sources: ['dashboard', 'metrics'] },
    ];
    const shotDir = path.join(root, 'PetHome-screenshots'); fs.mkdirSync(shotDir, { recursive: true });
    for (const fixture of cases) {
      user = fixtureUser(fixture.role, fixture.permissions);
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'vi-VN', timezoneId: 'Asia/Ho_Chi_Minh' });
      const page = await context.newPage(); const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      calls = [];
      await page.goto(base + '/admin');
      await expect(page.getByRole('heading', { name: fixture.role === 'owner' ? 'Tổng quan nền tảng' : 'Công việc của bạn', exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Làm mới', exact: true })).toBeEnabled();
      const nav = page.getByRole('navigation', { name: 'Điều hướng quản trị' }).first();
      await expect(nav.locator('summary > span:first-child')).toHaveText(fixture.groups);
      for (const source of ['dashboard', 'metrics', 'operations', 'system', 'traffic']) {
        expect(calls.some(p => p.endsWith('/' + source)), `API ${source}, permissions ${fixture.permissions}`).toBe(fixture.sources.includes(source));
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      if (fixture.role === 'owner') {
        await expect(page.getByText('Các mục đã kiểm tra đang ổn định')).toBeVisible();
        await expect(nav.getByRole('link', { name: 'Sản phẩm', exact: true })).toBeHidden();
        await nav.locator('summary').filter({ hasText: /^Shop/ }).click();
        await expect(nav.getByRole('link', { name: 'Sản phẩm', exact: true })).toBeVisible();
        await nav.locator('summary').filter({ hasText: /^Shop/ }).click();
        await page.screenshot({ path: path.join(shotDir, 'admin-overview-1280.png'), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
        await page.screenshot({ path: path.join(shotDir, 'admin-overview-390.png'), fullPage: true });
        await page.getByRole('button', { name: 'Menu', exact: true }).click();
        const mobile = page.locator('#admin-mobile-navigation');
        await mobile.locator('summary').filter({ hasText: /^Hệ thống/ }).click();
        await expect(mobile.getByRole('link', { name: 'Nhân viên & phân quyền' })).toBeVisible();
        await expect(mobile.getByRole('button', { name: 'Đăng xuất' })).toBeVisible();
        await page.getByRole('button', { name: 'Đóng', exact: true }).click();
        failedSource = true;
        await page.getByRole('button', { name: 'Làm mới', exact: true }).click();
        await expect(page.getByRole('alert').filter({ hasText: 'Chưa tải được' })).toContainText('Hệ thống');
        await expect(page.getByText('Chưa có kết quả kiểm tra')).toBeVisible();
        failedSource = false;
      } else {
        await expect(page.getByRole('heading', { name: 'Tình trạng hệ thống', exact: true })).toHaveCount(0);
        if (fixture.permissions.length === 1 && fixture.permissions[0] === 'rescue_care') {
          await page.setViewportSize({ width: 390, height: 844 });
          await page.screenshot({ path: path.join(shotDir, 'admin-care-workspace-390.png'), fullPage: true });
        }
        calls = [];
        await page.goto(base + '/admin/staff');
        await expect(page.getByRole('heading', { name: 'Bạn chưa được cấp quyền cho khu vực này' })).toBeVisible();
        expect(calls.some(p => p.includes('/admin/staff'))).toBe(false);
      }
      expect(errors).toEqual([]);
      await context.close();
    }
    user = fixtureUser('customer');
    const context = await browser.newContext(); const page = await context.newPage();
    await page.goto(base + '/admin'); await expect(page).toHaveURL(/\/login\?/);
    await context.close();
    console.log('PASS: owner, five staff permissions, combined permissions, restricted data requests, direct-page denial, partial failures, desktop/mobile and customer redirect.');
  } finally {
    if (browser) await browser.close();
    spawnSync('docker', ['stop', '--time', '3', name], { stdio: 'ignore', windowsHide: true });
    if (app && app.exitCode === null) app.kill();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
