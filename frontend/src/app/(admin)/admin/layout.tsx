import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

const STAFF_ROLES = new Set(["owner", "warehouse_staff", "cskh_staff"]);

export default async function AdminPageLayout({
  children,
}: {
  children: ReactNode;
}) {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://fastapi-api:8000";

  let user: { role?: string } | null = null;
  try {
    const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
      headers: { Cookie: cookieHeader },
      cache: "no-store",
    });
    if (res.ok) {
      const data = await res.json();
      user = data.user ?? null;
    }
  } catch {
    user = null;
  }

  if (!user || !STAFF_ROLES.has(user.role ?? "")) {
    redirect("/login?next=/admin");
  }

  return <>{children}</>;
}
