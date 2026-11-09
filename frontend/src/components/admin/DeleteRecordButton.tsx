"use client";
import { useContext, useState } from "react";
import { api } from "@/lib/api-client";
import { canManagePlatform } from "@/lib/admin-navigation";
import { AdminUserContext } from "./AdminUserContext";

export function DeleteRecordButton({ kind, id, onDeleted }: {kind: "categories" | "products" | "lots" | "promotions" | "orders"; id: string; onDeleted: () => void | Promise<void>}) {
  const user = useContext(AdminUserContext);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!canManagePlatform(user)) return null;
  return <span className="inline-flex flex-col gap-1"><button type="button" disabled={busy} className="rounded-full border border-danger/30 px-3 py-1 text-xs text-danger disabled:opacity-50" onClick={async () => {
    if (!window.confirm("Xóa bản ghi khỏi danh sách quản lý? Lịch sử đơn hàng, thanh toán và kho vẫn được giữ để đối chiếu.")) return;
    setBusy(true); setError("");
    try { await api.removeAdminRecord(kind, id); await onDeleted(); }
    catch (e) { setError(e instanceof Error ? e.message : "Chưa xóa được bản ghi."); }
    finally { setBusy(false); }
  }}>{busy ? "Đang xóa…" : "Xóa"}</button>{error && <span role="alert" className="max-w-xs text-xs text-danger">{error}</span>}</span>;
}
