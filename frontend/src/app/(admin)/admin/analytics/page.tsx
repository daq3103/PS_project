"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import type { SystemReport, TrafficReport } from "@/lib/analytics";

const number = (value: number | null | undefined) => value == null ? "—" : new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(value);
const bytes = (value: number | null | undefined) => value == null ? "—" : value >= 1024 ** 3 ? `${number(value / 1024 ** 3)} GB` : `${number(value / 1024 ** 2)} MB`;
const names: Record<string, string> = { direct: "Trực tiếp", internal: "Liên kết trong website", search: "Công cụ tìm kiếm", social: "Mạng xã hội", referral: "Website khác", mobile: "Điện thoại", tablet: "Máy tính bảng", desktop: "Máy tính", shop: "Shop", rescue: "Trạm cứu hộ", account: "Tài khoản", postgres: "PostgreSQL", redis_cache: "Redis cache", redis_queue: "Redis hàng đợi" };
const vitalLabels: Record<string, [string, string, number]> = { LCP: ["Nội dung chính xuất hiện", "ms", 2500], INP: ["Phản hồi tương tác", "ms", 200], CLS: ["Độ xê dịch bố cục", "", 0.1], TTFB: ["Nhận byte đầu tiên", "ms", 800] };

export default function AnalyticsPage() {
  const [tab, setTab] = useState("traffic");
  const [days, setDays] = useState(7);
  const [section, setSection] = useState("all");
  const [auto, setAuto] = useState(true);
  const [traffic, setTraffic] = useState<TrafficReport | null>(null);
  const [system, setSystem] = useState<SystemReport | null>(null);
  const [trafficError, setTrafficError] = useState("");
  const [systemError, setSystemError] = useState("");
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  const invalidate = useCallback(() => { generation.current++; }, []);
  const load = useCallback(async () => {
    const id = ++generation.current;
    setLoading(true);
    const result = await Promise.allSettled([api.analyticsTraffic(days, section), api.analyticsSystem()]);
    if (id !== generation.current) return;
    if (result[0].status === "fulfilled") { setTraffic(result[0].value); setTrafficError(""); }
    else setTrafficError(result[0].reason instanceof Error ? result[0].reason.message : "Không tải được thống kê truy cập");
    if (result[1].status === "fulfilled") { setSystem(result[1].value); setSystemError(""); }
    else setSystemError(result[1].reason instanceof Error ? result[1].reason.message : "Không tải được thông tin server");
    setLoading(false);
  }, [days, section]);
  useEffect(() => {
    setTraffic(null); setSystem(null);
    void load();
    const timer = auto ? window.setInterval(() => { if (document.visibilityState === "visible") void load(); }, 30000) : undefined;
    return () => { clearInterval(timer); invalidate(); };
  }, [load, auto, invalidate]);
  const stamp = tab === "traffic" ? traffic?.generated_at : system?.generated_at;
  return <div className="mx-auto max-w-7xl space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-moss">Petshop Analytics</p><h1 className="mt-2 font-display text-3xl text-forest">Truy cập & hiệu năng</h1><p className="mt-2 text-sm text-ink-muted">Theo dõi Shop và Trạm cứu hộ ngay trong hệ thống.</p></div>
      <div className="flex flex-wrap items-center gap-3 text-sm"><label className="flex items-center gap-2"><input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} />Tự cập nhật 30 giây</label><button onClick={() => void load()} disabled={loading} className="rounded-full border border-line bg-surface px-4 py-2 disabled:opacity-50">{loading ? "Đang tải…" : "Làm mới"}</button></div>
    </div>
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
      <div className="flex gap-2" role="group" aria-label="Nội dung thống kê">{[["traffic", "Lượng truy cập"], ["system", "Server & API"]].map(([key, label]) => <button key={key} aria-pressed={tab === key} onClick={() => setTab(key)} className={`rounded-full px-4 py-2 text-sm font-medium ${tab === key ? "bg-forest text-white" : "bg-surface text-ink-muted"}`}>{label}</button>)}</div>
      <p className="text-xs text-ink-muted">Cập nhật: {stamp ? new Date(stamp).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "Chưa có dữ liệu"}</p>
    </div>
    {(tab === "traffic" ? trafficError : systemError) && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm text-danger">{tab === "traffic" ? trafficError : systemError}. Dữ liệu trước đó, nếu có, chưa được cập nhật.</p>}
    {tab === "traffic" ? <>
      <div className="flex flex-wrap gap-3"><label className="text-sm">Thời gian<select aria-label="Thời gian" value={days} onChange={e => setDays(Number(e.target.value))} className="ml-2 rounded-lg border border-line bg-surface p-2">{[1, 7, 30, 90].map(day => <option key={day} value={day}>{day === 1 ? "Hôm nay" : `${day} ngày`}</option>)}</select></label><label className="text-sm">Khu vực<select aria-label="Khu vực" value={section} onChange={e => setSection(e.target.value)} className="ml-2 rounded-lg border border-line bg-surface p-2"><option value="all">Toàn website</option><option value="shop">Shop</option><option value="rescue">Trạm cứu hộ</option><option value="account">Tài khoản chung</option></select></label></div>
      {!traffic ? <p className="py-10 text-center text-ink-muted">{trafficError ? "Chưa tải được dữ liệu truy cập." : "Đang lấy thống kê…"}</p> : <>
        {!traffic.enabled && <p className="rounded-lg bg-honey/10 p-3 text-sm">Thu thập thống kê đang tắt. Bên dưới là lịch sử đã lưu.</p>}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat label="Lượt xem trang" value={number(traffic.summary.views)} hint="Mỗi lần mở hoặc chuyển trang" /><Stat label="Khách truy cập ước tính" value={number(traffic.summary.visitors)} hint="Theo mã trình duyệt ẩn danh" /><Stat label="Phiên truy cập" value={number(traffic.summary.sessions)} hint="Phiên mới sau 30 phút không hoạt động" /><Stat label="Đang hoạt động" value={number(traffic.online)} hint="Phiên hoạt động trong 5 phút gần nhất" /></div>
        <Panel title="Xu hướng truy cập"><Trend data={traffic.daily} /><details className="mt-4 text-sm"><summary className="cursor-pointer text-forest">Xem số liệu từng ngày</summary><div className="mt-3 max-h-72 overflow-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-2">Ngày</th><th>Lượt xem</th><th>Khách</th><th>Phiên</th></tr></thead><tbody>{traffic.daily.map(day => <tr key={day.day} className="border-t border-line"><td className="p-2">{day.day}</td><td>{number(day.views)}</td><td>{number(day.visitors)}</td><td>{number(day.sessions)}</td></tr>)}</tbody></table></div></details></Panel>
        <div className="grid gap-5 lg:grid-cols-2"><Panel title="Nhóm trang được xem nhiều"><Distribution rows={traffic.dimensions.page} /></Panel><div className="space-y-5"><Panel title="Nguồn truy cập"><Distribution rows={traffic.dimensions.source} /></Panel><Panel title="Thiết bị"><Distribution rows={traffic.dimensions.device} /></Panel></div></div>
        <Panel title="Trải nghiệm thực tế trên trình duyệt"><p className="mb-4 text-sm text-ink-muted">Phân vị 75% (p75) theo lượt tải tài liệu. Chuyển trang trong ứng dụng không tạo mẫu Web Vitals mới.</p><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Object.entries(vitalLabels).map(([key, [label, unit, good]]) => {
          const metric = traffic.vitals.find(v => v.kind === key);
          return <div key={key} className="rounded-lg border border-line p-4"><div className="flex justify-between"><span className="font-semibold">{key}</span>{metric && <span className={`text-xs ${metric.p75 <= good ? "text-moss" : "text-honey"}`}>{metric.p75 <= good ? "Tốt" : "Cần cải thiện"}</span>}</div><p className="mt-2 text-2xl text-forest">{metric ? key === "CLS" ? metric.p75.toFixed(3) : number(metric.p75) : "—"} <span className="text-sm">{unit}</span></p><p className="mt-2 text-xs text-ink-muted">{label} · {metric ? `${number(metric.samples)} mẫu` : "Chưa có mẫu"}</p></div>;
        })}</div></Panel>
        <p className="text-xs leading-relaxed text-ink-muted">Múi giờ Việt Nam · Lưu {traffic.retention_days} ngày. Khách là mã trình duyệt, không phải số người xác minh. Trình chặn theo dõi, DNT/GPC, xóa dữ liệu trình duyệt và bot có thể làm số liệu chênh lệch. Nguồn truy cập dựa trên referrer, không suy đoán vị trí địa lý. Trang có ID được gộp theo mẫu đường dẫn.</p>
      </>}
    </> : !system ? <p className="py-10 text-center text-ink-muted">{systemError ? "Chưa tải được thông tin server." : "Đang lấy thông tin server…"}</p> : <SystemView data={system} />}
  </div>;
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return <div className="rounded-xl border border-line bg-surface p-5"><p className="text-sm text-ink-muted">{label}</p><p className="mt-3 text-3xl font-semibold tabular-nums text-forest">{value}</p><p className="mt-2 text-xs text-ink-muted">{hint}</p></div>;
}
function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="min-w-0 rounded-xl border border-line bg-surface p-5"><h2 className="mb-4 font-display text-xl text-forest">{title}</h2>{children}</section>;
}
function Distribution({ rows }: { rows: { label: string; count: number }[] }) {
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  return !rows.length ? <p className="text-sm text-ink-muted">Chưa có dữ liệu trong khoảng này.</p> : <ul className="space-y-4">{rows.map(row => <li key={row.label}><div className="flex justify-between gap-3 text-sm"><span className="min-w-0 break-all">{names[row.label] ?? row.label}</span><span className="shrink-0 tabular-nums">{number(row.count)} · {number(row.count / total * 100)}%</span></div><div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-forest/5"><div className="h-full rounded-full bg-moss" style={{ width: `${row.count / total * 100}%` }} /></div></li>)}</ul>;
}
function Trend({ data }: { data: TrafficReport["daily"] }) {
  const max = Math.max(1, ...data.map(d => d.views));
  const points = data.map((d, i) => `${data.length === 1 ? 350 : i / (data.length - 1) * 700},${145 - d.views / max * 130}`).join(" ");
  return <div><div className="mb-2 flex justify-between text-xs text-ink-muted"><span>Lượt xem / ngày</span><span>Đỉnh: {number(max === 1 && !data.some(d => d.views) ? 0 : max)}</span></div><svg role="img" aria-label="Biểu đồ lượt xem theo ngày, số liệu chi tiết ở bảng bên dưới" viewBox="-8 0 716 160" className="h-40 w-full overflow-visible"><path d="M0 145H700M0 80H700M0 15H700" fill="none" stroke="var(--color-line)" strokeDasharray="4 4" /><polyline points={points} fill="none" stroke="var(--color-moss)" strokeWidth="3" strokeLinejoin="round" />{data.length === 1 && <circle cx="350" cy={145 - data[0].views / max * 130} r="4" fill="var(--color-moss)" />}</svg><div className="flex justify-between text-xs text-ink-muted"><span>{data[0]?.day}</span><span>{data.at(-1)?.day}</span></div></div>;
}

function SystemView({ data }: { data: SystemReport }) {
  const r = data.resources, a = data.api;
  const container = r.container_memory_bytes != null && r.container_limit_bytes != null;
  const memoryPercent = container ? r.container_memory_bytes! / r.container_limit_bytes! * 100 : r.memory_percent;
  const warnings = [r.disk_percent >= 85 ? "Dung lượng ổ đĩa đã dùng từ 85%." : "", memoryPercent >= 85 ? "Bộ nhớ đã dùng từ 85%." : "", r.cpu_percent >= 85 ? "CPU đang sử dụng từ 85%." : "", a.requests && (a.server_errors ?? 0) / a.requests >= 0.01 ? "Tỷ lệ lỗi API 5xx đạt từ 1% trong cửa sổ đo." : "", ...Object.entries(data.services).filter(([, value]) => value.status === "down").map(([key]) => `${names[key] ?? key} không phản hồi.`)].filter(Boolean);
  return <>
    {!!warnings.length && <div role="status" className="rounded-xl border border-honey/30 bg-honey/10 p-4"><p className="font-semibold text-honey">Cần kiểm tra</p><ul className="mt-2 list-inside list-disc text-sm">{warnings.map(w => <li key={w}>{w}</li>)}</ul></div>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat label="CPU hệ thống khả kiến" value={`${number(r.cpu_percent)}%`} hint={`${number(r.cpu_cores)} CPU logic · mẫu đo 100 ms`} /><Stat label={container ? "RAM container API" : "RAM hệ thống khả kiến"} value={`${number(memoryPercent)}%`} hint={`${bytes(container ? r.container_memory_bytes : r.memory_used_bytes)} / ${bytes(container ? r.container_limit_bytes : r.memory_total_bytes)}`} /><Stat label="Ổ đĩa chứa API" value={`${number(r.disk_percent)}%`} hint={`${bytes(r.disk_used_bytes)} / ${bytes(r.disk_total_bytes)}`} /><Stat label="Worker API hiện tại" value={bytes(r.process_memory_bytes)} hint={`Uptime tiến trình: ${number(r.process_uptime_seconds / 3600)} giờ`} /></div>
    <Panel title="Kết nối dịch vụ"><div className="grid gap-4 lg:grid-cols-3">{Object.entries(data.services).map(([key, value]) => <div key={key} className="rounded-lg border border-line p-4"><div className="flex items-center justify-between gap-2"><h3 className="font-medium">{names[key] ?? key}</h3><span className={`rounded-full px-2 py-1 text-xs ${value.status === "up" ? "bg-moss/10 text-moss" : "bg-danger/10 text-danger"}`}>{value.status === "up" ? "Kết nối tốt" : "Mất kết nối"}</span></div><p className="mt-3 text-sm">Phản hồi: {number(value.latency_ms)} ms</p>{value.memory_bytes != null && <p className="mt-1 text-xs text-ink-muted">RAM: {bytes(value.memory_bytes)}</p>}{value.queued_jobs != null && <p className="mt-1 text-xs text-ink-muted">Tác vụ trong hàng đợi: {number(value.queued_jobs)}</p>}{value.worker_heartbeat_present !== undefined && <p className="mt-1 text-xs text-ink-muted">ARQ worker: {value.worker_heartbeat_present ? "Có heartbeat" : "Chưa thấy heartbeat"}</p>}</div>)}</div></Panel>
    <Panel title="Hiệu năng API · 15 phút gần nhất">{!a.available ? <p role="status" className="text-honey">Không lấy được bộ đếm Redis. Chưa thể kết luận lưu lượng hoặc tỷ lệ lỗi.</p> : <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat label="Tổng yêu cầu API" value={number(a.requests)} hint="Cửa sổ gồm phút hiện tại và 14 phút trước" /><Stat label="Độ trễ trung bình" value={a.average_ms == null ? "—" : `${number(a.average_ms)} ms`} hint="Thời gian xử lý và gửi phản hồi" /><Stat label="Độ trễ p95 · cận trên" value={a.p95_upper_ms == null ? "—" : a.p95_upper_ms === "inf" ? "> 60.000 ms" : `≤ ${number(a.p95_upper_ms)} ms`} hint="Ước lượng từ histogram độ trễ" /><Stat label="Lỗi server 5xx" value={number(a.server_errors)} hint={`${number(a.requests ? (a.server_errors ?? 0) / a.requests * 100 : 0)}% yêu cầu · ${number(a.client_errors)} phản hồi 4xx`} /></div><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead><tr className="text-ink-muted"><th className="py-3">Endpoint</th><th>Yêu cầu</th><th>TB (ms)</th><th>Lỗi 5xx</th></tr></thead><tbody>{a.routes?.map(route => <tr key={route.route} className="border-t border-line"><td className="py-3 pr-3 font-mono text-xs">{route.route}</td><td>{number(route.requests)}</td><td>{number(route.average_ms)}</td><td>{number(route.errors)}</td></tr>)}</tbody></table>{!a.requests && <p className="py-6 text-center text-ink-muted">Chưa có yêu cầu trong cửa sổ đo.</p>}</div></>}</Panel>
    <p className="text-xs leading-relaxed text-ink-muted">CPU/RAM hệ thống là tài nguyên nhìn thấy từ môi trường chạy API; có thể là host Docker. RAM container chỉ hiển thị khi đọc được cgroup v2. Ổ đĩa là filesystem của API. Đây chưa phải phép đo riêng cho container Next.js/Nginx hoặc toàn bộ VPS. Bộ đếm API nằm trong Redis cache và có thể mất khi cache bị xóa hoặc đẩy ra do thiếu bộ nhớ.</p>
  </>;
}
