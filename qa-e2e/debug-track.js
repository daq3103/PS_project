const { chromium } = require('@playwright/test');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('PAGEERROR', e.message));
  page.on('console', m => { if (m.type()==='error') console.log('CONSOLE', m.text()); });
  await page.goto('http://localhost:3000/track-order');
  await page.waitForTimeout(1000);
  console.log('title', await page.title());
  console.log('body1', (await page.innerText('body')).slice(0,200));
  await page.locator('input').nth(0).fill('TOA8XHSTE6');
  await page.locator('input[type=tel]').fill('0977001122');
  await page.getByRole('button', { name: /Tra cứu/i }).click();
  await page.waitForTimeout(2000);
  console.log('body2', (await page.innerText('body')).slice(0,500));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
