const assert = require('node:assert/strict');
const base = process.env.SEO_TEST_BASE || 'http://127.0.0.1:3000';
const production = process.env.SEO_TEST_PRODUCTION === 'true';
(async () => {
  async function page(path) {
    const r = await fetch(base + path);
    assert.equal(r.status, 200, path);
    return {r, text: await r.text()};
  }
  const product = await page('/p/pate-ca-hoi-85g');
  assert.match(product.text, /<title>Pate cá hồi 85g \| PetHome<\/title>/);
  const category = await page('/c/thuc-an-hat');
  assert.match(category.text, /<title>Thức ăn hạt \| PetHome<\/title>/);
  const profile = await page('/account/profile');
  assert.match(profile.r.headers.get('x-robots-tag'), /noindex/);
  const robots = await page('/robots.txt');
  const sitemap = await page('/sitemap.xml');
  if (production) {
    assert.match(product.text, /name="robots" content="index, follow"/);
    assert.match(product.text, /rel="canonical" href="https:\/\/seo-check.example\/p\/pate-ca-hoi-85g"/);
    const data = product.text.match(/<script type="application\/ld\+json">(.*?)<\/script>/s);
    assert.ok(data, 'Product JSON-LD');
    const parsed = JSON.parse(data[1]);
    assert.equal(parsed['@type'], 'Product');
    assert.ok(parsed.offers.length);
    assert.equal(parsed.offers[0].priceCurrency, 'VND');
    assert.match(sitemap.text, /https:\/\/seo-check.example\/p\/pate-ca-hoi-85g/);
    assert.match(robots.text, /Allow: \//);
    const second = await page('/c/thuc-an-hat?page=2');
    assert.match(second.text, /rel="canonical" href="https:\/\/seo-check.example\/c\/thuc-an-hat\?page=2"/);
  } else {
    assert.match(product.text, /name="robots" content="noindex, nofollow"/);
    assert.match(robots.text, /Disallow: \//);
    assert.doesNotMatch(sitemap.text, /<loc>/);
  }
  console.log(`SEO ${production ? 'production simulation' : 'preview'} checks passed`);
})().catch(e => { console.error(e); process.exit(1); });
