// Exercise category creation and draft product flow without changing the shop database.
const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const { chromium, expect } = require('@playwright/test');

const root = path.resolve(__dirname, '../..');
const baseURL = 'http://127.0.0.1:3115';
const mockPort = 3116;
const shots = path.join(root, 'PetHome-screenshots');
fs.mkdirSync(shots, { recursive: true });
let category = null;
let product = null;
let createdProductStatus = null;
const ownerFixture = { id: '00000000-0000-0000-0000-000000000001', full_name: 'Admin QA', email: 'admin@example.com', phone: null, role: 'owner', staff_permissions: [], totp_enabled: true };

const mock = http.createServer(async (req, res) => {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : {};
  const url = new URL(req.url, `http://127.0.0.1:${mockPort}`);
  let status = 200;
  let value = {};
  if (url.pathname === '/api/v1/auth/me') value = { user: req.headers.cookie?.includes('access_token=fixture-only') ? ownerFixture : null, admin_verified: true, csrf_token: null };
  else if (url.pathname === '/api/v1/auth/login') {
    if (!body.totp_code) value = { requires_totp: true };
    else if (body.totp_code !== '123456') { status = 401; value = { detail: 'Mã xác thực không đúng hoặc đã hết hạn.' }; }
    else { value = ownerFixture; res.setHeader('Set-Cookie', ['access_token=fixture-only; HttpOnly; Path=/; SameSite=Lax', 'refresh_token=fixture-refresh; HttpOnly; Path=/; SameSite=Lax', 'csrf_token=fixture-csrf; Path=/; SameSite=Lax']); }
  }
  else if (url.pathname === '/api/v1/auth/refresh') {
    if (!req.headers.cookie?.includes('refresh_token=fixture-refresh') || req.headers['x-csrf-token'] !== 'fixture-csrf') { status = 401; value = { detail: 'Phiên đăng nhập đã hết hạn.' }; }
    else { value = ownerFixture; res.setHeader('Set-Cookie', 'access_token=fixture-only; HttpOnly; Path=/; SameSite=Lax'); }
  }
  else if (['/api/v1/categories', '/api/v1/admin/catalog/categories'].includes(url.pathname) && req.method === 'GET') value = category ? [category] : [];
  else if (url.pathname === '/api/v1/categories' && req.method === 'POST') {
    status = 201;
    category = { id: '00000000-0000-0000-0000-000000000002', parent_id: null, ...body, created_at: new Date().toISOString() };
    value = category;
  } else if (url.pathname === `/api/v1/categories/${category?.id}` && req.method === 'PATCH') {
    category = { ...category, ...body }; value = category;
  } else if (url.pathname === '/api/v1/admin/catalog/products' && req.method === 'GET') value = product ? [product] : [];
  else if (url.pathname === '/api/v1/products' && req.method === 'POST') {
    status = 201;
    createdProductStatus = body.status;
    product = { id: '00000000-0000-0000-0000-000000000003', ...body, description: null, variants: body.variants.map((variant, i) => ({ id: `00000000-0000-0000-0000-00000000000${i + 4}`, ...variant, cached_available_qty: 0 })), images: [] };
    value = product;
  } else if (url.pathname === '/api/v1/community/config') value = { enabled: true, turnstile_site_key: '' };
  else if (url.pathname === '/api/v1/cart') value = { item_count: 0, items: [], subtotal: 0 };
  else { status = 404; value = { detail: 'Mock route not found' }; }
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(value));
});

(async () => {
  let app, browser;
  try {
    await new Promise(resolve => mock.listen(mockPort, '127.0.0.1', resolve));
    app = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', '3115'], {
      cwd: path.join(root, 'frontend'),
      env: { ...process.env, INTERNAL_API_URL: `http://127.0.0.1:${mockPort}` },
      stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
    });
    app.stderr.on('data', data => process.stderr.write(data));
    await expect.poll(async () => { try { return (await fetch(baseURL)).status; } catch { return 0; } }, { timeout: 60000 }).toBe(200);
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${baseURL}/login`);
    await page.getByLabel('Tên tài khoản').fill('admin@example.com');
    await page.getByLabel('Mật khẩu', { exact: true }).fill('qa-password-only');
    await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
    await expect(page.getByLabel('Mã xác thực 6 số')).toBeVisible();
    expect((await context.cookies()).some(cookie => cookie.name === 'access_token')).toBe(false);
    await page.getByLabel('Mã xác thực 6 số').fill('000000');
    await page.getByRole('button', { name: 'Xác minh và đăng nhập' }).click();
    await expect(page.getByText('Mã xác thực không đúng hoặc đã hết hạn.', { exact: true })).toBeVisible();
    await page.getByLabel('Mã xác thực 6 số').fill('123456');
    await page.getByRole('button', { name: 'Xác minh và đăng nhập' }).click();
    await expect(page).toHaveURL(`${baseURL}/admin`);
    await context.clearCookies({ name: 'access_token' });
    await page.goto(`${baseURL}/admin`);
    await expect(page).toHaveURL(`${baseURL}/admin`);
    await page.goto(`${baseURL}/admin/products`);
    await page.getByRole('button', { name: '+ Thêm sản phẩm' }).click();
    await expect(page.getByRole('button', { name: 'Tạo sản phẩm' })).toBeDisabled();
    await page.getByRole('button', { name: '+ Tạo danh mục mới' }).click();
    await page.getByPlaceholder('Ví dụ: Đồ chơi, Thức ăn, Phụ kiện').fill('Đồ chơi');
    await page.getByRole('button', { name: 'Tạo danh mục', exact: true }).click();
    await expect.poll(() => category?.id ?? null).not.toBeNull();
    await expect(page.getByRole('combobox', { name: 'Danh mục', exact: true }).last()).toHaveValue(category.id);
    await page.screenshot({ path: path.join(shots, 'admin-product-create-1440.png'), fullPage: true });
    await page.getByRole('textbox', { name: 'Tên sản phẩm' }).fill('Bóng cao su');
    await page.getByRole('spinbutton', { name: 'Giá (đ)' }).fill('89000');
    await page.getByRole('spinbutton', { name: 'Cân nặng (g)' }).fill('120');
    await page.getByRole('button', { name: 'Tạo sản phẩm' }).click();
    await expect(page.getByRole('heading', { name: 'Bóng cao su' })).toBeVisible();
    expect(createdProductStatus).toBe('draft');
    await page.goto(`${baseURL}/admin/categories`);
    await expect(page.getByRole('heading', { name: 'Danh mục sản phẩm' })).toBeVisible();
    await expect(page.getByText('Đồ chơi', { exact: true })).toBeVisible();
    await page.screenshot({ path: path.join(shots, 'admin-categories-1440.png'), fullPage: true });
    expect(errors).toEqual([]);
    console.log('PASS: owner login challenge, invalid code, verified login, then category/product writes without more code prompts');
  } finally {
    if (browser) await browser.close();
    if (app && app.exitCode === null) { const stopped = new Promise(resolve => app.once('exit', resolve)); app.kill(); await stopped; }
    await new Promise(resolve => mock.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
