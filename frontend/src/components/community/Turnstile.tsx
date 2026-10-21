"use client";
import Script from "next/script";
import { useEffect, useRef, useState } from "react";

type TurnstileApi = { render: (element: HTMLElement, options: Record<string, unknown>) => string; remove: (id: string) => void };
declare global { interface Window { turnstile?: TurnstileApi } }

export function Turnstile({ siteKey, onToken, resetKey }: { siteKey: string; onToken: (token: string) => void; resetKey: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!ready || !ref.current || !window.turnstile) return;
    const id = window.turnstile.render(ref.current, { sitekey: siteKey, callback: onToken,
      "expired-callback": () => onToken(""), "error-callback": () => onToken("") });
    return () => { window.turnstile?.remove(id); };
  }, [ready, siteKey, onToken, resetKey]);
  if (!siteKey) return null;
  return <><Script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" onReady={() => setReady(true)} /><div ref={ref} /></>;
}
