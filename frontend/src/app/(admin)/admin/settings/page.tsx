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
        setTotpEnabled(res.user?.totp_enabled === true);
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
      setError(e instanceof Error ? e.message : "Không thể thiết lập bảo mật");
    }
  }

  async function verifyCode() {
    setError("");
    setMessage("");
    try {
      const res = await api.adminTotpVerify(code.trim());
      if (res.totp_enabled) {
        setTotpEnabled(true);
        setEnroll(null);
        setCode("");
        setMessage("Xác minh hai bước đã được kích hoạt.");
        window.setTimeout(() => window.location.assign("/admin"), 600);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Mã không đúng");
    }
  }

  return (
    <div>
      <h1 className="font-display text-3xl text-forest">Cài đặt</h1>
      <p className="mt-1 text-sm text-ink-muted">Thông tin tài khoản và xác minh hai bước. Quản lý quyền nhân viên ở mục “Nhân viên & quyền”.</p>

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
                  {user.role === "owner" ? "Quản trị viên" : user.staff_permissions?.length === 2 ? "Nhân viên kho & chăm sóc khách hàng" : ({ warehouse_staff: "Nhân viên kho", cskh_staff: "Nhân viên chăm sóc khách hàng", customer: "Khách hàng" } as Record<string, string>)[user.role] ?? "Thành viên"}
                </span>
              </p>
            </div>
          </div>

          {user.role === "owner" ? <div className="rounded-sm border border-line bg-surface p-4">
            <h2 className="font-display text-xl text-forest">Xác minh hai bước</h2>
            <p className="mt-1 text-sm text-ink-muted">
              Quản trị viên xác minh một lần khi đăng nhập. Các thao tác sau đó không hỏi lại mã trong cùng phiên.
            </p>

            {error && <p className="mt-3 text-sm text-danger">{error}</p>}
            {message && <p className="mt-3 text-sm text-forest">{message}</p>}

            {!enroll && !totpEnabled && (
              <button
                type="button"
                onClick={() => void startEnroll()}
                className="mt-4 rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep"
              >
                Thiết lập xác minh hai bước
              </button>
            )}

            {enroll && !totpEnabled && (
              <div className="mt-4 space-y-3">
                <p className="text-sm">Thêm khóa này vào ứng dụng xác thực, chẳng hạn Google Authenticator:</p>
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
              <p className="mt-4 text-sm text-forest">Xác minh hai bước đã bật cho tài khoản này.</p>
            )}
          </div> : <p className="rounded-sm border border-line bg-surface p-4 text-sm text-ink-muted">Tài khoản nhân viên thao tác theo quyền được cấp và không cần thiết lập mã xác thực hai bước.</p>}
        </div>
      )}
    </div>
  );
}
