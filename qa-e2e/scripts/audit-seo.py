"""Read public HTML only; record reproducible SEO observations without changing the site."""
import concurrent.futures
import json
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.h1 = []
        self.meta = {}
        self.canonical = []
        self.links = []
        self.images = []
        self.jsonld_count = 0
        self.capture = None
        self.lang = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html": self.lang = a.get("lang")
        if tag == "title": self.capture = "title"
        if tag == "h1": self.capture = "h1"; self.h1.append("")
        if tag == "meta": self.meta[a.get("name", a.get("property", ""))] = a.get("content", "")
        if tag == "link" and a.get("rel") == "canonical": self.canonical.append(a.get("href"))
        if tag == "a" and a.get("href"): self.links.append(a["href"])
        if tag == "img": self.images.append({k: a.get(k) for k in ("src", "alt", "width", "height", "loading")})
        if tag == "script" and a.get("type") == "application/ld+json": self.jsonld_count += 1

    def handle_endtag(self, tag):
        if tag == self.capture: self.capture = None

    def handle_data(self, data):
        if self.capture == "title": self.title += data
        if self.capture == "h1": self.h1[-1] += data


origin = sys.argv[1].rstrip("/")
output = Path(sys.argv[2])


def inspect(path):
    started = time.monotonic()
    try:
        req = Request(origin + path, headers={"User-Agent": "PetHome-SEO-Audit/1.0"})
        try: response = urlopen(req, timeout=25)
        except HTTPError as exc: response = exc
        body = response.read().decode("utf-8", errors="replace")
        result = {"path": path, "status": response.status, "final_url": response.url,
                  "elapsed_seconds": round(time.monotonic()-started, 3), "html_bytes": len(body.encode()),
                  "x_robots_tag": response.headers.get("X-Robots-Tag"), "content_type": response.headers.get("Content-Type")}
        if "text/html" in result["content_type"]:
            p = Page(); p.feed(body)
            result.update(title=p.title, description=p.meta.get("description"), robots=p.meta.get("robots"),
                          canonical=p.canonical, h1=p.h1, lang=p.lang, jsonld_count=p.jsonld_count,
                          links=list(dict.fromkeys(p.links)), images=p.images, viewport=p.meta.get("viewport"))
        else: result["body_excerpt"] = body[:4000]
        return result
    except Exception as exc:
        return {"path": path, "error": str(exc)}


paths = ["/", "/shop", "/robots.txt", "/sitemap.xml", "/cart", "/checkout", "/login", "/account/profile", "/admin", "/track-order"]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(inspect, paths))
    shop = next(r for r in results if r["path"] == "/shop")
    products = [urlsplit(link).path for link in shop.get("links", []) if link.startswith("/p/")][:3]
    more = ["/c/thuc-an-hat", "/c/phu-kien", "/c/thuc-an-hat?sort=price_asc", "/p/seo-audit-not-a-product-20261107"] + products
    results.extend(pool.map(inspect, more))
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({"origin": origin, "checked_at": datetime.now(timezone.utc).isoformat(), "pages": results}, ensure_ascii=False, indent=2), encoding="utf-8")
for r in results:
    print(json.dumps({k:v for k,v in r.items() if k not in ("images", "links", "body_excerpt")}, ensure_ascii=False))
print("Saved:", output)
