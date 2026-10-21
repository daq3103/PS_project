"""Seed sample categories + active products for local UI.

Usage (host, stack đang chạy):
  python scripts/seed_catalog.py
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://localhost:8000"
SEED_PATH = Path(__file__).with_name("seed_catalog.json")


def _req(method: str, path: str, data: dict | None = None):
    body = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        raise SystemExit(f"{method} {path} -> {exc.code}: {raw}") from exc


def main() -> None:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    existing_cats = {c["slug"]: c["id"] for c in _req("GET", "/api/v1/categories")}
    cat_map: dict[str, str] = {}
    for cat in seed["categories"]:
        if cat["slug"] in existing_cats:
            cat_map[cat["slug"]] = existing_cats[cat["slug"]]
            print(f"category exists: {cat['slug']}")
            continue
        out = _req("POST", "/api/v1/categories", {**cat, "is_active": True})
        cat_map[cat["slug"]] = out["id"]
        print(f"category created: {cat['slug']}")

    existing_products = {p["slug"] for p in _req("GET", "/api/v1/products")}
    for product in seed["products"]:
        if product["slug"] in existing_products:
            print(f"product exists: {product['slug']}")
            continue
        payload = {
            "category_id": cat_map[product["category_slug"]],
            "name": product["name"],
            "slug": product["slug"],
            "pet_type": product["pet_type"],
            "brand": product.get("brand"),
            "status": product["status"],
            "short_description": product.get("short_description"),
            "has_expiry": product.get("has_expiry", False),
            "variants": product["variants"],
        }
        out = _req("POST", "/api/v1/products", payload)
        print(f"product created: {out['slug']}")

    active = _req("GET", "/api/v1/products?status=active")
    print(f"done — {len(active)} active product(s). Open http://localhost:3000")


if __name__ == "__main__":
    main()
