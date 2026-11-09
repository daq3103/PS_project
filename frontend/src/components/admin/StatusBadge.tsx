"use client";

const STATUS_MAP: Record<string, { label: string; tone: Tone }> = {
  pending: { label: "Chờ", tone: "honey" },
  confirmed: { label: "Xác nhận", tone: "moss" },
  packed: { label: "Đóng gói", tone: "forest" },
  shipped: { label: "Đang giao", tone: "moss" },
  delivered: { label: "Đã giao", tone: "forest" },
  cancelled: { label: "Huỷ", tone: "danger" },
  returned: { label: "Hoàn", tone: "danger" },
  active: { label: "Hiện", tone: "forest" },
  hidden: { label: "Ẩn", tone: "ink" },
  draft: { label: "Nháp", tone: "honey" },
  unpaid: { label: "Chưa thanh toán", tone: "honey" },
  paid: { label: "Đã thanh toán", tone: "forest" },
  cod: { label: "COD", tone: "moss" },
  vietqr: { label: "VietQR", tone: "moss" },
};

type Tone = "forest" | "moss" | "honey" | "danger" | "ink";

const TONE_STYLES: Record<Tone, string> = {
  forest: "bg-forest/10 text-forest border-forest/20",
  moss: "bg-moss/10 text-moss border-moss/20",
  honey: "bg-honey/10 text-honey border-honey/20",
  danger: "bg-danger/10 text-danger border-danger/20",
  ink: "bg-ink/5 text-ink-muted border-ink/10",
};

export function StatusBadge({
  status,
  label,
}: {
  status: string;
  label?: string;
}) {
  const mapped = STATUS_MAP[status] ?? { label: status, tone: "ink" };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_STYLES[mapped.tone]}`}
    >
      {label ?? mapped.label}
    </span>
  );
}
