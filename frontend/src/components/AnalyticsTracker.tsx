"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { onCLS, onINP, onLCP, onTTFB } from "web-vitals";
import { readCookie } from "@/lib/format";

type Source = "direct" | "internal" | "search" | "social" | "referral";
type Session = { id: string; visitor: string; active: number; source: Source };
let fallbackSession: Session | null = null;
let vitalsStarted = false;
const uuid = () => crypto.randomUUID();

function optedOut() {
  try {
    return navigator.doNotTrack === "1" || (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl === true || localStorage.getItem("petshop:analytics:optout") === "1";
  } catch { return true; }
}

function source(): Source {
  try {
    if (!document.referrer) return "direct";
    const host = new URL(document.referrer).hostname;
    if (host === location.hostname) return "internal";
    if (/(^|\.)(google\.[a-z.]+|bing\.com|coccoc\.com|search\.yahoo\.com|duckduckgo\.com)$/.test(host)) return "search";
    if (/(^|\.)(facebook\.com|instagram\.com|tiktok\.com|youtube\.com|zalo\.me|t\.co|x\.com)$/.test(host)) return "social";
    return "referral";
  } catch { return "direct"; }
}

function session(): Session {
  const now = Date.now();
  try {
    const stored = JSON.parse(localStorage.getItem("petshop:analytics:visitor") ?? "null");
    const visitor = stored?.expires > now ? stored.id : uuid();
    if (!stored || stored.expires <= now) localStorage.setItem("petshop:analytics:visitor", JSON.stringify({ id: visitor, expires: now + 90 * 86400000 }));
    const previous = JSON.parse(localStorage.getItem("petshop:analytics:session") ?? "null") as Session | null;
    const next = previous && now - previous.active < 30 * 60000 && previous.visitor === visitor ? { ...previous, active: now } : { id: uuid(), visitor, active: now, source: source() };
    localStorage.setItem("petshop:analytics:session", JSON.stringify(next));
    return next;
  } catch {
    if (!fallbackSession || now - fallbackSession.active >= 30 * 60000) fallbackSession = { id: uuid(), visitor: uuid(), active: now, source: source() };
    fallbackSession.active = now;
    return fallbackSession;
  }
}

function device() {
  return /iPad|Tablet|Android(?!.*Mobile)/i.test(navigator.userAgent) ? "tablet" : /Mobi|iPhone/i.test(navigator.userAgent) ? "mobile" : "desktop";
}

function send(path: string, eventId: string, kind = "page_view", value?: number, identity = session()) {
  if (optedOut()) return;
  const csrf = readCookie("csrf_token");
  void fetch("/api/proxy/api/v1/analytics/events", {
    method: "POST", credentials: "same-origin", keepalive: true,
    headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
    body: JSON.stringify({ event_id: eventId, visitor_id: identity.visitor, session_id: identity.id, kind, path: path.slice(0, 512), source: identity.source, device: device(), ...(value !== undefined ? { value } : {}) }),
  }).catch(() => { /* Measurement must never interrupt navigation or checkout. */ });
}

export function AnalyticsTracker() {
  const pathname = usePathname();
  const lastPage = useRef("");
  const current = useRef<{ path: string; id: string } | null>(null);
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    if (optedOut()) return;
    void fetch("/api/proxy/api/v1/analytics/config", { cache: "no-store" }).then(res => res.ok ? res.json() : { enabled: false }).then(config => setEnabled(config.enabled === true)).catch(() => {});
  }, []);
  useEffect(() => {
    if (!enabled || optedOut() || pathname.startsWith("/admin") || lastPage.current === pathname) return;
    lastPage.current = pathname;
    const eventId = uuid();
    current.current = { path: pathname, id: eventId };
    send(pathname, eventId);
    if (!vitalsStarted) {
      vitalsStarted = true;
      // Web Vitals describe the document, not each client-side route transition.
      const identity = session();
      const report = (metric: { name: string; value: number }) => {
        if (Number.isFinite(metric.value)) send(pathname, eventId, metric.name, metric.value, identity);
      };
      onCLS(report); onINP(report); onLCP(report); onTTFB(report);
    }
  }, [pathname, enabled]);
  useEffect(() => {
    if (!enabled) return;
    let activity = Date.now();
    const onActivity = () => { activity = Date.now(); };
    for (const name of ["pointerdown", "keydown", "scroll"]) window.addEventListener(name, onActivity, { passive: true });
    const timer = window.setInterval(() => {
      if (current.current && document.visibilityState === "visible" && Date.now() - activity < 5 * 60000) send(current.current.path, current.current.id, "heartbeat");
    }, 60000);
    return () => {
      clearInterval(timer);
      for (const name of ["pointerdown", "keydown", "scroll"]) window.removeEventListener(name, onActivity);
    };
  }, [enabled]);
  return null;
}
