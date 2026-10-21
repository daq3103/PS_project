"use client";

import { useEffect, useState } from "react";
import { api, type UserDto } from "@/lib/api-client";

export default function AdminSettingsPage() {
  const [user, setUser] = useState<UserDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [enroll, setEnroll] = useState<{ secret: string; provisioning_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [totpEnabled, setTotpEnabled] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    api
      .me()
      .then((res) => {
        setUser(res.user);
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function startEnroll() {
    setError("");
    setMessage("");
    try {
      const data = await api.adminTotpEnroll();
      setEnroll({ secret: data.secret, provisioning_uri: data.provisioning_uri });
      setTotpEnabled(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không thể tạo TOTP");
    }
  }

  async function verifyCode() {
    setError("");
    setMessage("");
    try {
      const res = await api.adminTotpVerify(code.trim());
      if (res.totp_enabled) {
        setTotpEnabled(true);
        setMessage("TOTP đã được kích hoạt.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Mã không đúng");
    }
  }

  return (
    <div>
      <h1 className="font-display text-3xl text-forest">Cài đặt</h1>
      <p className="mt-1 text-sm text-ink-muted">Tài khoản staff và bảo mật.</p>

      {loading && <p className="mt-6 text-ink-muted">Đang tải…</p>}

      {user && (
        <div className="mt-6 max-w-xl space-y-6">
          <div className="rounded-sm border border-line bg-surface p-4">
            <h2 className="font-display text-xl text-forest">Thông tin tài khoản</h2>
            <div className="mt-3 space-y-2 text-sm">
              <p>
                <span className="text-ink-muted">Họ tên:</span> {user.full_name}
              </p>
              <p>
                <span className="text-ink-muted">Email:</span> {user.email ?? "—"}
              </p>
              <p>
                <span className="text-ink-muted">SĐT:</span> {user.phone ?? "—"}
              </p>
              <p>
                <span className="text-ink-muted">Vai trò:</span>{" "}
                <span className="rounded-full bg-forest/10 px-2 py-0.5 font-medium text-forest">
                  {user.role}
                </span>
              </p>
            </div>
          </div>

          <div className="rounded-sm border border-line bg-surface p-4">
            <h2 className="font-display text-xl text-forest">TOTP / Authenticator</h2>
            <p className="mt-1 text-sm text-ink-muted">
              Yêu cầu mã 6 số cho mọi thao tác ghi trong admin.
            </p>

            {error && <p className="mt-3 text-sm text-danger">{error}</p>}
            {message && <p className="mt-3 text-sm text-forest">{message}</p>}

            {!enroll && !totpEnabled && (
              <button
                type="button"
                onClick={() => void startEnroll()}
                className="mt-4 rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep"
              >
                Thiết lập TOTP
              </button>
            )}

            {enroll && !totpEnabled && (
              <div className="mt-4 space-y-3">
                <p className="text-sm">Thêm key sau vào Google Authenticator:</p>
                <code className="block rounded-sm bg-ink/5 p-2 font-mono text-sm break-all">
                  {enroll.secret}
                </code>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="Nhập mã 6 số"
                  className="block w-40 rounded-sm border border-line bg-paper px-3 py-2 text-center font-mono tracking-widest"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => void verifyCode()}
                    disabled={code.length !== 6}
                    className="rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
                  >
                    Xác nhận
                  </button>
                  <button
                    type="button"
                    onClick={() => setEnroll(null)}
                    className="rounded-full border border-line px-4 py-2 text-sm text-ink-muted hover:border-forest hover:text-forest"
                  >
                    Huỷ
                  </button>
                </div>
              </div>
            )}

            {totpEnabled && (
              <p className="mt-4 text-sm text-forest">TOTP đã bật cho tài khoản này.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
