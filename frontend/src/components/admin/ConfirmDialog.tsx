"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

type ConfirmVariant = "danger" | "primary";

export function useConfirm() {
  const [state, setState] = useState<{
    open: boolean;
    title: string;
    message: ReactNode;
    variant: ConfirmVariant;
    confirmText: string;
    onConfirm?: () => void;
  }>({
    open: false,
    title: "Xác nhận",
    message: "",
    variant: "primary",
    confirmText: "Xác nhận",
  });

  function confirm({
    title = "Xác nhận",
    message,
    variant = "primary",
    confirmText = "Xác nhận",
  }: {
    title?: string;
    message: ReactNode;
    variant?: ConfirmVariant;
    confirmText?: string;
  }): Promise<boolean> {
    return new Promise((resolve) => {
      setState({
        open: true,
        title,
        message,
        variant,
        confirmText,
        onConfirm: () => {
          resolve(true);
          setState((s) => ({ ...s, open: false, onConfirm: undefined }));
        },
      });
    });
  }

  const dialog = (
    <ConfirmDialog
      open={state.open}
      title={state.title}
      message={state.message}
      variant={state.variant}
      confirmText={state.confirmText}
      onConfirm={state.onConfirm}
      onCancel={() => {
        setState((s) => ({ ...s, open: false, onConfirm: undefined }));
      }}
    />
  );

  return { confirm, dialog };
}

function ConfirmDialog({
  open,
  title,
  message,
  variant,
  confirmText,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: ReactNode;
  variant: ConfirmVariant;
  confirmText: string;
  onConfirm?: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) ref.current?.focus();
  }, [open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-ink/40 p-4">
      <div className="w-full max-w-md rounded-sm border border-line bg-paper p-6 shadow-lg">
        <h3 className="font-display text-xl text-forest">{title}</h3>
        <div className="mt-2 text-sm text-ink">{message}</div>
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-line px-4 py-1.5 text-sm text-ink-muted hover:border-forest hover:text-forest"
          >
            Huỷ
          </button>
          <button
            ref={ref}
            type="button"
            onClick={onConfirm}
            className={`rounded-full px-4 py-1.5 text-sm font-medium text-white ${
              variant === "danger"
                ? "bg-danger hover:bg-danger/90"
                : "bg-forest hover:bg-forest-deep"
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
