"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type UserDto } from "@/lib/api-client";

const ROLE_LABELS: Record<string, string> = {
  customer: "Khách hàng",
  owner: "Chủ shop",
  warehouse_staff: "Nhân viên kho",
  cskh_staff: "Nhân viên CSKH",
};

export function UserMenu({ user, communityEnabled = true }: { user: UserDto; communityEnabled?: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const isStaff = ["owner", "warehouse_staff", "cskh_staff"].includes(user.role);
  const roleLabel = ROLE_LABELS[user.role] ?? user.role;

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  async function logout() {
    setOpen(false);
    try {
      await api.logout();
    } catch {
      /* ignore */
    }
    window.dispatchEvent(new Event("petshop:auth"));
    router.push("/");
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex max-w-[9rem] items-center gap-1.5 rounded-full bg-forest/10 px-3 py-2 text-sm font-semibold text-forest transition hover:bg-forest/20 lg:max-w-[12rem]"
      >
        <span className="truncate">{user.full_name}</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`}
        >
          <path
            fillRule="evenodd"
            d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 max-h-[calc(100dvh-5rem)] w-64 min-w-[16rem] overflow-y-auto rounded-sm border border-line bg-paper py-2 shadow-lg">
          <div className="px-4 py-3">
            <p className="truncate font-medium text-ink">{user.full_name}</p>
            <p className="truncate text-xs text-ink-muted">
              {user.email ?? user.phone}
            </p>
            <span className="mt-1 inline-block rounded-full bg-forest/10 px-2 py-0.5 text-xs font-medium text-forest">
              {roleLabel}
            </span>
          </div>

          <div className="border-t border-line" />
          <SectionTitle>Tài khoản</SectionTitle>
          <nav className="py-1" role="menu">
            <MenuLink href="/account/profile" onClick={() => setOpen(false)}>
              <UserIcon />
              Hồ sơ
            </MenuLink>
            <MenuLink href="/account/addresses" onClick={() => setOpen(false)}>
              <AddressIcon />
              Sổ địa chỉ
            </MenuLink>
          </nav>

          <div className="border-t border-line" />
          <SectionTitle>Shop</SectionTitle>
          <nav className="py-1" role="menu">
            <MenuLink href="/account/orders" onClick={() => setOpen(false)}><OrderIcon />Đơn hàng của tôi</MenuLink>
          </nav>
          {communityEnabled && <>
            <div className="border-t border-line" />
            <SectionTitle>Trạm cứu hộ</SectionTitle>
            <nav className="py-1" role="menu">
              <MenuLink href="/account/community" onClick={() => setOpen(false)}>Tin cứu hộ và thông báo</MenuLink>
              <MenuLink href="/account/adoption-requests" onClick={() => setOpen(false)}>Hồ sơ nhận nuôi</MenuLink>
            </nav>
          </>}

          {isStaff && (
            <>
              <div className="border-t border-line" />
              <SectionTitle>Quản trị</SectionTitle>
              <nav className="py-1" role="menu">
                <MenuLink href="/admin" onClick={() => setOpen(false)}>
                  <AdminIcon />
                  Trang quản trị viên
                </MenuLink>
              </nav>
            </>
          )}

          <div className="border-t border-line" />
          <button
            type="button"
            onClick={() => void logout()}
            className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-danger transition hover:bg-danger/5"
            role="menuitem"
          >
            <LogoutIcon />
            Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="px-4 pb-1 pt-2 text-xs font-medium uppercase tracking-wide text-ink-muted">
      {children}
    </p>
  );
}

function MenuLink({
  href,
  children,
  onClick,
}: {
  href: string;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="flex items-center gap-2 px-4 py-2 text-sm text-ink transition hover:bg-forest/5 hover:text-forest"
      role="menuitem"
    >
      {children}
    </Link>
  );
}

function UserIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 opacity-70">
      <path d="M10 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM3.465 14.493a1.23 1.23 0 0 0 .41 1.412A9.957 9.957 0 0 0 10 18c2.31 0 4.438-.784 6.131-2.1.43-.333.604-.903.408-1.412A7.002 7.002 0 0 0 3.465 14.493Z" />
    </svg>
  );
}

function OrderIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 opacity-70">
      <path fillRule="evenodd" d="M4.5 2A2.5 2.5 0 0 0 2 4.5v11A2.5 2.5 0 0 0 4.5 18h11a2.5 2.5 0 0 0 2.5-2.5v-11A2.5 2.5 0 0 0 15.5 2h-11ZM3.5 4.5a1 1 0 0 1 1-1h11a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1v-11ZM5 6a.75.75 0 0 1 .75-.75h8.5a.75.75 0 0 1 0 1.5h-8.5A.75.75 0 0 1 5 6Zm0 3.5a.75.75 0 0 1 .75-.75h8.5a.75.75 0 0 1 0 1.5h-8.5A.75.75 0 0 1 5 9.5Zm0 3.5a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5A.75.75 0 0 1 5 13Z" clipRule="evenodd" />
    </svg>
  );
}

function AddressIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 opacity-70">
      <path fillRule="evenodd" d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 0 0 .281-.14c.186-.096.446-.24.757-.433.62-.378 1.458-.995 2.317-1.806C15.075 14.54 16 13.106 16 11.5c0-1.72-.833-3.258-2.143-4.293A6.038 6.038 0 0 0 10 5.5c-2.273 0-4.21 1.254-5.357 3.207C3.833 8.742 3 10.28 3 12c0 1.606.925 3.04 2.312 4.143.859.811 1.697 1.428 2.317 1.806.311.193.571.337.757.433.104.055.198.103.281.14l.018.008.006.003ZM10 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" clipRule="evenodd" />
    </svg>
  );
}

function AdminIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 opacity-70">
      <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-11.25a.75.75 0 0 0-1.5 0v2.5h-2.5a.75.75 0 0 0 0 1.5h2.5v2.5a.75.75 0 0 0 1.5 0v-2.5h2.5a.75.75 0 0 0 0-1.5h-2.5v-2.5Z" clipRule="evenodd" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 opacity-70">
      <path fillRule="evenodd" d="M3 4.25A2.25 2.25 0 0 1 5.25 2h5.5A2.25 2.25 0 0 1 13 4.25v1.5a.75.75 0 0 1-1.5 0v-1.5a.75.75 0 0 0-.75-.75h-5.5a.75.75 0 0 0-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 0 0 .75-.75v-1.5a.75.75 0 0 1 1.5 0v1.5A2.25 2.25 0 0 1 10.75 18h-5.5A2.25 2.25 0 0 1 3 15.75V4.25Z" clipRule="evenodd" />
      <path fillRule="evenodd" d="M6 10a.75.75 0 0 1 .75-.75h6.19l-1.47-1.47a.75.75 0 1 1 1.06-1.06l2.75 2.75a.75.75 0 0 1 0 1.06l-2.75 2.75a.75.75 0 1 1-1.06-1.06l1.47-1.47H6.75A.75.75 0 0 1 6 10Z" clipRule="evenodd" />
    </svg>
  );
}
