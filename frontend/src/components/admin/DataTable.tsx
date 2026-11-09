"use client";

import { ReactNode } from "react";

export type Column<T> = {
  key: string;
  header: ReactNode;
  width?: string;
  align?: "left" | "right" | "center";
  cell: (row: T) => ReactNode;
};

export function DataTable<T>({
  columns,
  rows,
  keyExtractor,
  loading,
  empty,
  rowClassName,
  onRowClick,
  rowAriaLabel,
}: {
  columns: Column<T>[];
  rows: T[];
  keyExtractor: (row: T) => string;
  loading?: boolean;
  empty?: ReactNode;
  rowClassName?: (row: T, index: number) => string;
  onRowClick?: (row: T) => void;
  rowAriaLabel?: (row: T) => string;
}) {
  return (
    <div className="overflow-hidden rounded-sm border border-line bg-surface">
      <div className="max-w-full overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-forest/5">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-3 font-medium text-ink-muted ${col.width ? col.width : ""} ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {loading && rows.length === 0 ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="animate-pulse">
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3">
                      <div className="h-4 rounded bg-line" />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-ink-muted">
                  {empty ?? "Không có dữ liệu"}
                </td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <tr key={keyExtractor(row)}
                  tabIndex={onRowClick ? 0 : undefined}
                  role={onRowClick ? "button" : undefined}
                  aria-label={onRowClick ? rowAriaLabel?.(row) ?? "Mở chi tiết" : undefined}
                  onClick={onRowClick ? event => {
                    if ((event.target as HTMLElement).closest("button, a, input, select, textarea")) return;
                    onRowClick(row);
                  } : undefined}
                  onKeyDown={onRowClick ? event => {
                    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onRowClick(row); }
                  } : undefined}
                  className={`${onRowClick ? "cursor-pointer hover:bg-forest/10 focus-visible:bg-forest/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-forest" : "hover:bg-forest/5"} ${rowClassName?.(row, index) ?? ""}`}>
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-4 py-3 ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"}`}
                    >
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
