"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type DashboardOut, type OperationsReport, type UserDto } from "@/lib/api-client";
import type { SystemReport, TrafficReport } from "@/lib/analytics";
import { adminGroups, canManagePlatform } from "@/lib/admin-navigation";
import { BRAND } from "@/lib/brand";

type CommunityMetrics = Awaited<ReturnType<typeof api.adminCommunityMetrics>>;
type Summary = { shop?: DashboardOut; community?: CommunityMetrics; operations?: OperationsReport; system?: SystemReport; traffic?: TrafficReport };
type Attention = { label: string; count: number; href: string };
const count = (value?: number | null) => value == null ? "—" : value.toLocaleString("vi-VN");

export default function AdminHomePage() {
  const [user, setUser] = useState<UserDto | null>(null);
  const [data, setData] = useState<Summary>({});
  const [loading, setLoading] = useState(true);
  const [failures, setFailures] = useState<string[]>([]);
  const [updatedAt, setUpdatedAt] = useState("");
  const requestId = useRef(0);
  const load = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setData({});
    setFailures([]);
    try {
      const { user: current } = await api.me();
      if (id !== requestId.current) return;
      setUser(current);
      const groups = adminGroups(current?.role, current?.staff_permissions);
      const can = (href: string) => groups.some(group => group.links.some(link => link.href === href));
      const next: Summary = {};
      const tasks: { label: string; run: () => Promise<void> }[] = [];
      if (can("/admin/shop")) tasks.push({ label: "Shop", run: async () => { next.shop = await api.adminDashboard(); } });
      if (can("/admin/community")) tasks.push({ label: "Tin cứu hộ", run: async () => { next.community = await api.adminCommunityMetrics(); } });
      if (canManagePlatform(current)) tasks.push(
        { label: "Công việc chờ", run: async () => { next.operations = await api.operations(); } },
        { label: "Hệ thống", run: async () => { next.system = await api.analyticsSystem(); } },
        { label: "Lượt truy cập", run: async () => { next.traffic = await api.analyticsTraffic(1, "all"); } },
      );
      const results = await Promise.allSettled(tasks.map(task => task.run()));
      if (id !== requestId.current) return;
      setData(next);
      setFailures(results.flatMap((result, index) => result.status === "rejected" ? [tasks[index].label] : []));
      setUpdatedAt(new Date().toLocaleTimeString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit" }));
    } catch {
      if (id === requestId.current) setFailures(["Thông tin phiên đăng nhập"]);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, []);
  useEffect(() => { const generation = requestId; void load(); return () => { generation.current++; }; }, [load]);

  const groups = adminGroups(user?.role, user?.staff_permissions);
  const can = (href: string) => groups.some(group => group.links.some(link => link.href === href));
  const owner = canManagePlatform(user);
  const workGroups = groups.filter(group => !["Điều hành", "Hệ thống"].includes(group.label));
  const attention: Attention[] = [];
  if (data.shop) {
    attention.push({ label: "Đơn hàng chờ xử lý", count: data.shop.pending_orders, href: "/admin/orders?status=pending" });
    if (can("/admin/reviews")) attention.push({ label: "Đánh giá chờ duyệt", count: data.shop.pending_reviews, href: "/admin/reviews" });
    if (can("/admin/inventory-lots")) attention.push({ label: "Mặt hàng hết hoặc sắp hết", count: data.shop.out_of_stock_variants + data.shop.low_stock_variants, href: "/admin/inventory-lots?stock=low" });
  }
  if (data.community) attention.push(
    { label: "Tin cứu hộ chờ duyệt", count: data.community.pending_posts, href: "/admin/community" },
    { label: "Báo cáo vi phạm cần xem", count: data.community.pending_reports, href: "/admin/community/reports" },
    { label: "Công việc tin cứu hộ bị lỗi", count: data.community.failed_jobs, href: "/admin/community/metrics" },
  );
  if (data.operations) attention.push(
    { label: "Khoản tiền cần đối soát", count: data.operations.cases.length, href: "/admin/operations" },
    { label: "Công việc Shop bị lỗi", count: data.operations.jobs.filter(job => job.status === "failed").length, href: "/admin/operations" },
  );
  const pending = attention.filter(item => item.count > 0);
  const cards = owner ? [
    { label: "Khách truy cập hôm nay", value: data.traffic?.enabled ? data.traffic.summary.visitors : undefined, href: "/admin/analytics", note: data.traffic?.enabled === false ? "Đang tắt thống kê truy cập" : "Ước tính theo thiết bị" },
    { label: "Đang truy cập", value: data.traffic?.enabled ? data.traffic.online : undefined, href: "/admin/analytics", note: "Hoạt động trong 5 phút gần đây" },
    { label: "Đơn chờ xử lý", value: data.shop?.pending_orders, href: "/admin/orders?status=pending", note: "Shop" },
    { label: "Tin chờ duyệt", value: data.community?.pending_posts, href: "/admin/community", note: "Trạm cứu hộ" },
  ] : [
    ...(can("/admin/shop") ? [{ label: "Đơn chờ xử lý", value: data.shop?.pending_orders, href: "/admin/orders?status=pending", note: "Shop" }] : []),
    ...(can("/admin/reviews") ? [{ label: "Đánh giá chờ duyệt", value: data.shop?.pending_reviews, href: "/admin/reviews", note: "Chăm sóc khách hàng" }] : []),
    ...(can("/admin/community") ? [{ label: "Tin chờ duyệt", value: data.community?.pending_posts, href: "/admin/community", note: "Trạm cứu hộ" }, { label: "Hồ sơ nhận nuôi đang xử lý", value: data.community?.active_applications, href: "/admin/community/adoptions", note: "Trạm cứu hộ" }] : []),
  ];
  const services = data.system ? Object.values(data.system.services) : [];
  const memory = data.system?.resources;
  const memoryPercent = memory?.container_memory_bytes != null && memory.container_limit_bytes ? Math.round(memory.container_memory_bytes / memory.container_limit_bytes * 100) : null;
  const systemWarning = data.system && (services.some(service => service.status !== "up") || data.system.services.redis_queue?.worker_heartbeat_present !== true || (data.system.api.server_errors ?? 0) > 0 || (memoryPercent ?? 0) >= 90 || data.system.resources.disk_percent >= 90);

  return <div className="mx-auto max-w-6xl space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div>
      <p className="text-sm text-ink-muted">{owner ? `Điều hành ${BRAND.name}` : "Khu vực làm việc"}</p>
      <h1 className="mt-1 font-display text-3xl text-forest">{owner ? "Tổng quan nền tảng" : "Công việc của bạn"}</h1>
      <p className="mt-2 max-w-2xl text-sm text-ink-muted">{owner ? "Theo dõi tình hình website và giao việc cho các bộ phận." : "Chọn công việc trong phạm vi được giao. Liên hệ quản trị viên khi cần thêm quyền."}</p>
    </div><div className="flex items-center gap-3 text-xs text-ink-muted">{updatedAt && <span>Cập nhật {updatedAt}</span>}<button onClick={() => void load()} disabled={loading} className="rounded-full border border-line bg-surface px-4 py-2 text-sm text-forest disabled:opacity-50">{loading ? "Đang tải…" : "Làm mới"}</button></div></header>
    {failures.length > 0 && <p role="alert" className="rounded-xl border border-line bg-surface p-4 text-sm text-danger">Chưa tải được: {failures.join(", ")}. Bấm Làm mới để thử lại. Dấu — nghĩa là chưa có số liệu.</p>}
    {cards.length > 0 && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(card => <Link key={card.label} href={card.href} className="rounded-2xl border border-line bg-surface p-5 transition hover:border-forest/40"><p className="text-sm text-ink-muted">{card.label}</p><p className="mt-2 text-3xl font-semibold text-forest">{count(card.value)}</p><p className="mt-2 text-xs text-ink-muted">{card.note}</p></Link>)}</div>}
    {owner && <section className="rounded-2xl border border-line bg-surface p-5"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-display text-xl text-forest">Tình trạng hệ thống</h2><Link href="/admin/analytics?tab=system" className="text-sm font-medium text-forest underline">Xem hiệu năng & chi tiết</Link></div>
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-3 text-sm"><p className={systemWarning ? "text-danger" : "text-forest"}>{!data.system ? "Chưa có kết quả kiểm tra" : systemWarning ? "Có mục cần kiểm tra" : "Các mục đã kiểm tra đang ổn định"}</p>{data.system && <><p>Dịch vụ phản hồi: {services.filter(service => service.status === "up").length}/{services.length}</p><p>Bộ nhớ xử lý web: {memoryPercent == null ? "Chưa có số liệu" : `${memoryPercent}% giới hạn`}</p><p>Lỗi xử lý: {data.system.api.available ? count(data.system.api.server_errors) : "Chưa có số liệu"}</p></>}</div>
      <p className="mt-3 text-xs text-ink-muted">Kiểm tra kết nối dữ liệu, bộ nhớ đệm và xử lý nền khi mở trang hoặc bấm Làm mới.</p>
    </section>}
    <section className="rounded-2xl border border-line bg-surface p-5"><h2 className="font-display text-xl text-forest">Cần xử lý</h2>
      {loading ? <p role="status" className="mt-4 text-sm text-ink-muted">Đang kiểm tra công việc…</p> : pending.length ? <ul className="mt-3 divide-y divide-line">{pending.map(item => <li key={item.label}><Link href={item.href} className="flex items-center justify-between gap-4 py-3 text-sm hover:text-forest"><span>{item.label}</span><span className="shrink-0 rounded-full bg-forest/10 px-3 py-1 font-semibold text-forest">{count(item.count)} ↗</span></Link></li>)}</ul> : <p className="mt-4 text-sm text-ink-muted">{attention.length ? failures.length ? "Các mục đã tải chưa có việc chờ xử lý. Một số mục chưa có số liệu." : "Các mục đã kiểm tra chưa có việc chờ xử lý." : "Mở khu vực làm việc bên dưới để xem hồ sơ, lịch hẹn và việc được giao."}</p>}
      {can("/admin/rescue/coordination") && <Link href="/admin/rescue/coordination" className="mt-4 inline-block text-sm font-medium text-forest underline">Xem lịch hẹn & công việc tại trạm</Link>}
    </section>
    <section><h2 className="font-display text-xl text-forest">{owner ? "Khu vực vận hành" : "Khu vực được giao"}</h2><div className="mt-3 grid gap-4 md:grid-cols-2">{workGroups.map(group => <article key={group.label} className="rounded-2xl border border-line bg-surface p-5"><h3 className="font-display text-xl text-forest">{group.label}</h3><p className="mt-2 text-sm text-ink-muted">{group.description}</p><Link href={group.links[0].href} className="mt-4 inline-flex min-h-10 items-center rounded-lg bg-forest/10 px-4 py-2 text-sm font-medium text-forest transition hover:bg-forest/20">Mở {group.label.toLocaleLowerCase("vi-VN")} ↗</Link><details className="mt-4 border-t border-line pt-3"><summary className="cursor-pointer rounded-lg px-3 py-2 text-sm text-ink-muted hover:bg-forest/5">Các chức năng được phép</summary><ul className="mt-3 grid gap-1 sm:grid-cols-2">{group.links.map(link => <li key={link.href}><Link href={link.href} className="block rounded-lg px-3 py-2.5 text-sm text-forest transition hover:bg-forest/10">{link.label}</Link></li>)}</ul></details></article>)}</div></section>
    {owner && <section className="flex flex-wrap gap-3 border-t border-line pt-5">{groups.find(group => group.label === "Hệ thống")?.links.slice(1).map(link => <Link key={link.href} href={link.href} className="rounded-full border border-line px-4 py-2 text-sm text-forest hover:bg-forest/5">{link.label}</Link>)}</section>}
  </div>;
}
