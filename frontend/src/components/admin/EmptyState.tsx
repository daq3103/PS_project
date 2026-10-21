"use client";

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-sm border border-dashed border-line bg-surface/50 px-6 py-12 text-center text-sm text-ink-muted">
      {message}
    </div>
  );
}
