"use client";

const MOD_LABELS: Record<string, string> = {
  pending: "Chờ duyệt",
  approved: "Đã duyệt",
  rejected: "Từ chối",
  hidden: "Đã gỡ",
};

const MOD_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-forest/10 text-forest",
  rejected: "bg-danger/10 text-danger",
  hidden: "bg-ink/10 text-ink",
};

const LIFE_LABELS: Record<string, string> = {
  open: "Đang mở",
  resolved: "Đã giải quyết",
  closed: "Đã đóng",
  expired: "Hết hạn",
};

const LIFE_COLORS: Record<string, string> = {
  open: "bg-forest/10 text-forest",
  resolved: "bg-blue-100 text-blue-800",
  closed: "bg-ink/10 text-ink",
  expired: "bg-amber-100 text-amber-800",
};

export function PostStatusBadge({
  moderationStatus,
  lifecycleStatus,
}: {
  moderationStatus: string;
  lifecycleStatus: string;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${MOD_COLORS[moderationStatus]}`}>
        {MOD_LABELS[moderationStatus]}
      </span>
      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${LIFE_COLORS[lifecycleStatus]}`}>
        {LIFE_LABELS[lifecycleStatus]}
      </span>
    </div>
  );
}
