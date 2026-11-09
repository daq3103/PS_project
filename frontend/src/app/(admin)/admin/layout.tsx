import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";
export const metadata = { title: "Quản trị" };

const STAFF_ROLES = new Set(["owner", "warehouse_staff", "cskh_staff"]);

export default async function AdminPageLayout({
  children,
}: {
  children: ReactNode;
}) {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://fastapi-api:8000";

  let user: { role?: string; staff_permissions?: string[]; totp_enabled?: boolean } | null = null;
  let verified = false;
  try {
    const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
      headers: { Cookie: cookieHeader },
      cache: "no-store",
    });
    if (res.ok) {
      const data = await res.json();
      user = data.user ?? null;
      verified = data.admin_verified === true;
    }
  } catch {
    user = null;
  }

  if (!user) {
    redirect(cookieStore.get("refresh_token") ? "/login?next=/admin&resume=1" : "/login?next=/admin");
  }

  if (!STAFF_ROLES.has(user.role ?? "") || (user.role !== "owner" && !user.staff_permissions?.length)) {
    return <main className="mx-auto max-w-xl p-8"><h1 className="text-2xl font-semibold">Bạn không có quyền truy cập quản trị.</h1><a href="/account" className="mt-4 inline-block underline">Về tài khoản của tôi</a></main>;
  }

  if (user.role === "owner" && user.totp_enabled && !verified) redirect("/login?next=/admin");

  return <>{children}</>;
}
