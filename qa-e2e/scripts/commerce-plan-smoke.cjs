// UI contract tests with synthetic data only; no shop writes or provider requests.
const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const { chromium, expect } = require('@playwright/test');
const root = path.resolve(__dirname, '../..');
const base = 'http://127.0.0.1:3127';
const now = new Date().toISOString();
const owner = { id: '11111111-1111-4111-8111-111111111111', full_name: 'Nhân viên thử nghiệm', email: 'qa@example.com', role: 'owner', totp_enabled: true, staff_permissions: [] };
let online = false, checkoutCount = 0, lastCheckout, tickets = [], messages = [];
const mock = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1:3128');
  let input = '';
  for await (const chunk of req) input += chunk;
  const body = input ? JSON.parse(input) : {};
  const p = url.pathname;
  let result = [];
  if (p.endsWith('/auth/me')) result = { user: owner, admin_verified: true, csrf_token: null };
  else if (p.endsWith('/community/config')) result = { enabled: true };
  else if (p.endsWith('/analytics/config')) result = { enabled: false };
  else if (p.endsWith('/cart')) result = { item_count: 2, items: [], subtotal: 420000 };
  else if (p.endsWith('/checkout/methods')) result = { methods: [{ id: 'cod', available: true }, { id: 'vietqr', available: online }] };
  else if (p.endsWith('/checkout/quote')) result = { quote_id: '22222222-2222-4222-8222-222222222222', expires_at: new Date(Date.now() + 600000).toISOString(), subtotal_amount: 420000, discount_amount: 30000, shipping_fee: 25000, shipping_discount: 0, total_amount: 415000 };
  else if (p.endsWith('/checkout') && req.method === 'POST') {
    checkoutCount++; lastCheckout = body;
    result = { id: '33333333-3333-4333-8333-333333333333', order_code: 'QA12345678', status: 'pending', payment_method: body.payment_method, payment_status: 'unpaid', total_amount: 415000, tracking_token: 'synthetic-ui-token' };
  } else if (p.endsWith('/payment')) result = { status: 'pending', checkout_url: 'https://pay.payos.vn/web/' + 'a'.repeat(32) };
  else if (/\/support\/tickets\/[^/]+\/messages$/.test(p)) {
    messages.push({ id: String(messages.length), author_type: 'customer', content: body.content, created_at: now });
    result = { status: 'received' };
  } else if (/\/support\/tickets\/[^/]+$/.test(p)) {
    if (req.method === 'PATCH') tickets[0].status = body.status;
    result = { ...tickets[0], messages };
  } else if (p.endsWith('/support/tickets')) {
    if (req.method === 'POST') {
      const ticket = { id: '44444444-4444-4444-8444-444444444444', subject: body.subject, topic: body.topic, status: 'open', created_at: now, updated_at: now };
      tickets.push(ticket); messages = [{ id: 'first', author_type: 'customer', content: body.content, created_at: now }]; result = ticket;
    } else result = tickets;
  } else if (p.endsWith('/admin/operations')) result = {
    jobs: [{ id: 'job1', task: 'send_order_confirmation_email', status: 'failed', attempts: 5, last_error: 'RuntimeError', created_at: now }],
    cases: [{ id: 'case1', order_code: 'QA12345678', kind: 'refund_required', amount: 415000, status: 'open', created_at: now }],
  };
  res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(result));
});

(async () => {
  let app, browser;
  const screenshots = path.join(root, 'PetHome-screenshots');
  try {
    fs.mkdirSync(screenshots, { recursive: true });
    await new Promise(resolve => mock.listen(3128, '127.0.0.1', resolve));
    app = spawn(process.execPath, ['--max-old-space-size=256', 'node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', '3127'], {
      cwd: path.join(root, 'frontend'), env: { ...process.env, INTERNAL_API_URL: 'http://127.0.0.1:3128' }, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
    });
    app.stderr.on('data', chunk => process.stderr.write(chunk));
    await expect.poll(async () => { try { return (await fetch(base)).status; } catch { return 0; } }, { timeout: 60000 }).toBe(200);
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));
    for (const width of [1280, 390]) {
      online = false;
      await page.setViewportSize({ width, height: 900 });
      await page.goto(base + '/checkout');
      await expect(page.getByRole('radio')).toHaveCount(1);
      for (const [label, value] of [['Họ tên', 'Khách thử nghiệm'], ['Số điện thoại', '0900000000'], ['Tỉnh / Thành phố', 'Hà Nội'], ['Quận / Huyện', 'Quận thử'], ['Phường / Xã', 'Phường thử'], ['Địa chỉ (số nhà, đường)', 'Địa chỉ thử nghiệm']]) {
        await page.getByLabel(label, { exact: true }).fill(value);
      }
      const previousCount = checkoutCount;
      await page.getByRole('button', { name: 'Kiểm tra tổng tiền', exact: true }).click();
      await expect(page.getByRole('region', { name: 'Chi tiết thanh toán' })).toBeVisible();
      expect(checkoutCount).toBe(previousCount);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(screenshots, `plan-checkout-${width}.png`), fullPage: true });
      await page.getByRole('button', { name: 'Xác nhận đặt hàng', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Đặt hàng thành công' })).toBeVisible();
      expect(lastCheckout.quote_id).toBe('22222222-2222-4222-8222-222222222222');
      expect(lastCheckout.payment_method).toBe('cod');
      expect(lastCheckout.total_amount).toBeUndefined();
      await page.goto(base + '/account/support');
      await expect(page.getByRole('heading', { name: 'Hỗ trợ khách hàng', exact: true })).toBeVisible();
      if (!tickets.length) {
        await page.getByLabel('Tiêu đề', { exact: true }).fill('Đơn hàng cần kiểm tra');
        await page.getByLabel('Nội dung', { exact: true }).fill('Tôi muốn được hỗ trợ kiểm tra đơn hàng của mình.');
        await page.getByRole('button', { name: 'Gửi yêu cầu', exact: true }).click();
      } else await page.getByRole('button', { name: /Đơn hàng cần kiểm tra/ }).click();
      await expect(page.getByRole('heading', { name: 'Đơn hàng cần kiểm tra', exact: true })).toBeVisible();
      await page.getByLabel('Phản hồi', { exact: true }).fill('Tôi bổ sung thông tin cho yêu cầu hỗ trợ.');
      await page.getByRole('button', { name: 'Gửi phản hồi', exact: true }).click();
      await expect(page.getByRole('list', { name: 'Lịch sử trao đổi' })).toContainText('Tôi bổ sung thông tin');
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(screenshots, `plan-support-${width}.png`), fullPage: true });
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    }
    online = true;
    await page.goto(base + '/checkout');
    await expect(page.getByRole('radio')).toHaveCount(2);
    await page.goto(base + '/admin/support');
    await page.getByRole('button', { name: /Đơn hàng cần kiểm tra/ }).click();
    await page.getByLabel('Trạng thái xử lý').selectOption('closed');
    await expect(page.getByRole('button', { name: 'Gửi phản hồi', exact: true })).toHaveCount(0);
    await page.goto(base + '/admin/operations');
    await expect(page.getByRole('heading', { name: 'Tiền cần đối chiếu' })).toBeVisible();
    await expect(page.getByText('Gửi email xác nhận đơn', { exact: true })).toBeVisible();
    await page.screenshot({ path: path.join(screenshots, 'plan-operations-390.png'), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    expect(errors).toEqual([]);
    console.log('PASS: quote before checkout, COD without online keys, payOS visibility, customer support, staff status, operations and responsive screenshots');
  } finally {
    if (browser) await browser.close();
    if (app && app.exitCode === null) { const done = new Promise(resolve => app.once('exit', resolve)); app.kill(); await done; }
    await new Promise(resolve => mock.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
