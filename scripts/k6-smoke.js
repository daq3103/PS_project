import http from "k6/http";
import { check, sleep } from "k6";

/**
 * Smoke: browse catalog + guest checkout (requires seeded catalog + inventory).
 * Run: k6 run -e BASE_URL=https://staging.example scripts/k6-smoke.js
 */
const BASE = __ENV.BASE_URL || "http://localhost";

export const options = {
  vus: 5,
  duration: "30s",
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<800"],
  },
};

function jsonHeaders(extra = {}) {
  return { "Content-Type": "application/json", ...extra };
}

export default function () {
  const home = http.get(`${BASE}/`);
  check(home, { "home 200": (r) => r.status === 200 });

  const products = http.get(`${BASE}/api/proxy/api/v1/products?status=active&limit=5`);
  check(products, { "products 200": (r) => r.status === 200 });

  let variantId = null;
  try {
    const list = products.json();
    if (Array.isArray(list) && list[0]?.variants?.[0]?.id) {
      variantId = list[0].variants[0].id;
    }
  } catch {
    /* ignore */
  }

  if (variantId) {
    http.post(
      `${BASE}/api/proxy/api/v1/cart/items`,
      JSON.stringify({ variant_id: variantId, qty: 1 }),
      { headers: jsonHeaders() },
    );
  }

  const idempotencyKey = `${__VU}-${__ITER}-${Date.now()}`;
  const checkout = http.post(
    `${BASE}/api/proxy/api/v1/checkout`,
    JSON.stringify({
      idempotency_key: idempotencyKey,
      customer_name: "k6 Smoke",
      customer_phone: "0900000001",
      shipping_address: {
        province: "Hà Nội",
        district: "Ba Đình",
        ward: "Phúc Xá",
        street: "1 Test",
      },
      payment_method: "cod",
    }),
    { headers: jsonHeaders() },
  );
  check(checkout, {
    "checkout ok": (r) => r.status === 200 || r.status === 201 || r.status === 409,
  });

  sleep(1);
}
