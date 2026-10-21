"use client";

import { setTotpRequestHandler } from "@/lib/api-client";
import { useEffect, useRef, useState } from "react";

export function TotpProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const resolversRef = useRef<Array<(code: string) => void>>([]);

  useEffect(() => {
    setTotpRequestHandler(
      () =>
        new Promise<string>((resolve) => {
          resolversRef.current.push(resolve);
          setOpen(true);
        }),
    );
    return () => {
      setTotpRequestHandler(null);
    };
  }, []);

  function submit() {
    const trimmed = code.trim();
    if (!/^\d{6}$/.test(trimmed)) return;
    const resolvers = resolversRef.current;
    resolversRef.current = [];
    resolvers.forEach((r) => r(trimmed));
    setCode("");
    setOpen(false);
  }

  function cancel() {
    const resolvers = resolversRef.current;
    resolversRef.current = [];
    resolvers.forEach((r) => r(""));
    setCode("");
    setOpen(false);
  }

  return (
    <>
      {children}
      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-sm rounded-sm border border-line bg-paper p-6 shadow-lg">
            <h2 className="font-display text-xl text-forest">Xác thực TOTP</h2>
            <p className="mt-1 text-sm text-ink-muted">
              Thao tác quản trị cần mã 6 số từ app Authenticator.
            </p>
            <input
              type="text"
              inputMode="numeric"
              autoFocus
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
                if (e.key === "Escape") cancel();
              }}
              placeholder="000000"
              className="mt-4 block w-full rounded-sm border border-line bg-surface px-3 py-2 text-center font-mono text-lg tracking-widest focus:border-moss"
            />
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={cancel}
                className="rounded-full border border-line px-4 py-1.5 text-sm text-ink-muted hover:border-forest hover:text-forest"
              >
                Huỷ
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={!/\d{6}/.test(code)}
                className="rounded-full bg-forest px-4 py-1.5 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
              >
                Xác nhận
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
