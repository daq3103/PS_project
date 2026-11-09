// Visual/interaction checks against synthetic API responses; no shop data changes.
const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const { chromium, expect } = require('@playwright/test');

const root = path.resolve(__dirname, '../..');
const base = 'http://127.0.0.1:3117';
const shots = path.join(root, 'PetHome-screenshots');
const mock = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1:3118');
  let body = [];
  if (url.pathname.endsWith('/auth/me')) body = { user: null, csrf_token: null };
  else if (url.pathname.endsWith('/community/config')) body = { enabled: true };
  else if (url.pathname.endsWith('/analytics/config')) body = { enabled: false };
  else if (url.pathname.endsWith('/cart')) body = { item_count: 0, items: [], subtotal: 0 };
  res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(body));
});

(async () => {
  let app, browser;
  try {
    fs.mkdirSync(shots, { recursive: true });
    await new Promise(resolve => mock.listen(3118, '127.0.0.1', resolve));
    app = spawn(process.execPath, ['--max-old-space-size=256', 'node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', '3117'], {
      cwd: path.join(root, 'frontend'), env: { ...process.env, INTERNAL_API_URL: 'http://127.0.0.1:3118' },
      stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
    });
    app.stderr.on('data', chunk => process.stderr.write(chunk));
    await expect.poll(async () => { try { return (await fetch(base)).status; } catch { return 0; } }, { timeout: 60000 }).toBe(200);
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const viewport of [{ width: 1440, height: 960 }, { width: 390, height: 844 }, { width: 320, height: 640 }, { width: 667, height: 375 }]) {
      await page.setViewportSize(viewport);
      await page.goto(base);
      await page.evaluate(() => document.fonts.ready);
      await page.locator('footer').scrollIntoViewIfNeeded();
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      const footer = page.getByRole('navigation', { name: 'Mạng xã hội PetHome' });
      for (const name of ['Zalo', 'Facebook', 'TikTok']) {
        const link = footer.getByRole('link', { name: new RegExp(name) });
        await expect(link).toHaveAttribute('href', /^https:\/\//);
        await expect(link).toHaveAttribute('target', '_blank');
        await expect(link).toHaveAttribute('rel', /noopener/);
      }
      await page.screenshot({ path: path.join(shots, `contact-footer-${viewport.width}.png`) });
      await page.getByRole('button', { name: 'Liên hệ PetHome', exact: true }).click();
      const panel = page.getByRole('dialog', { name: 'Kết nối với PetHome' });
      await expect(panel).toBeVisible();
      await expect(panel.getByRole('tab', { name: 'Liên hệ', exact: true })).toBeFocused();
      await expect(panel.getByRole('link', { name: /Zalo/ })).toBeVisible();
      const box = await panel.boundingBox();
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.y).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
      await page.screenshot({ path: path.join(shots, `contact-widget-${viewport.width}.png`) });
      await panel.getByRole('tab', { name: 'Liên hệ', exact: true }).press('ArrowRight');
      await expect(panel.getByRole('tab', { name: 'Mạng xã hội' })).toBeFocused();
      await expect(panel.getByRole('link', { name: /TikTok/ })).toBeVisible();
      if (viewport.width === 390) await page.screenshot({ path: path.join(shots, 'contact-social-390.png') });
      await page.keyboard.press('Escape');
      await expect(panel).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Liên hệ PetHome', exact: true })).toBeFocused();
      await page.getByRole('button', { name: 'Liên hệ PetHome', exact: true }).click();
      await page.mouse.click(5, 5);
      await expect(page.getByRole('dialog', { name: 'Kết nối với PetHome' })).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    }
    expect(errors).toEqual([]);
    console.log('PASS: footer links, contact/social tabs, keyboard, outside click, focus restore, responsive bounds and screenshots');
  } finally {
    if (browser) await browser.close();
    if (app && app.exitCode === null) { const stopped = new Promise(resolve => app.once('exit', resolve)); app.kill(); await stopped; }
    await new Promise(resolve => mock.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
