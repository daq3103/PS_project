"use client";

export function KpiCard({
  label,
  value,
  tone = "forest",
  href,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "forest" | "honey" | "danger" | "ink";
  href?: string;
}) {
  const tones = {
    forest: "border-l-forest",
    honey: "border-l-honey",
    danger: "border-l-danger",
    ink: "border-l-ink",
  };

  const content = (
    <div
      className={`rounded-sm border border-line border-l-4 bg-surface p-4 ${tones[tone]}`}
    >
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-1 font-display text-2xl text-ink">{value}</p>
    </div>
  );

  if (href) {
    return (
      <a href={href} className="block transition hover:shadow-sm">
        {content}
      </a>
    );
  }
  return content;
}
