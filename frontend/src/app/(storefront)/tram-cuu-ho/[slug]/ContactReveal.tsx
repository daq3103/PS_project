"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api-client";

export function ContactReveal({ slug }: { slug: string }) {
  const [contacts, setContacts] = useState<{
    contact_phone: string;
    contact_zalo: string | null;
    contact_facebook: string | null;
  } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function reveal() {
    setBusy(true);
    setError("");
    try {
      setContacts(await api.revealCommunityContact(slug));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không thể xem liên hệ");
    } finally {
      setBusy(false);
    }
  }

  if (contacts) {
    return (
      <div className="space-y-2 rounded-sm bg-paper p-4 text-sm">
        <p>
          <span className="text-ink-muted">Điện thoại:</span>{" "}
          <a href={`tel:${contacts.contact_phone}`} className="font-medium text-forest hover:underline">
            {contacts.contact_phone}
          </a>
        </p>
        {contacts.contact_zalo && (
          <p>
            <span className="text-ink-muted">Zalo:</span>{" "}
            <a href={`https://zalo.me/${contacts.contact_zalo}`} className="font-medium text-forest hover:underline" target="_blank" rel="noreferrer">
              {contacts.contact_zalo}
            </a>
          </p>
        )}
        {contacts.contact_facebook && (
          <p>
            <span className="text-ink-muted">Facebook:</span>{" "}
            <a href={contacts.contact_facebook} className="font-medium text-forest hover:underline" target="_blank" rel="noreferrer">
              Xem trang
            </a>
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => void reveal()}
        disabled={busy}
        className="rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-forest-deep disabled:opacity-60"
      >
        {busy ? "Đang tải…" : "Xem liên hệ"}
      </button>
      {error && (
        <div className="text-sm text-danger">
          {error.includes("Authentication") || error.includes("đăng nhập") ? (
            <span>
              Bạn cần{" "}
              <Link href="/login?next=/tram-cuu-ho" className="underline">
                đăng nhập
              </Link>{" "}
              để xem liên hệ.
            </span>
          ) : (
            error
          )}
        </div>
      )}
    </div>
  );
}
