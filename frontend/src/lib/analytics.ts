export type TrafficReport = {
  enabled: boolean; days: number; section: string; timezone: string; retention_days: number;
  generated_at: string; online: number | null;
  summary: { views: number; visitors: number; sessions: number };
  daily: { day: string; views: number; visitors: number; sessions: number }[];
  dimensions: Record<"page" | "source" | "device" | "section", { label: string; count: number }[]>;
  vitals: { kind: string; samples: number; p75: number; average: number }[];
};
export type SystemReport = {
  generated_at: string;
  resources: {
    cpu_percent: number; cpu_scope: string; cpu_cores: number;
    memory_used_bytes: number; memory_total_bytes: number; memory_percent: number;
    container_memory_bytes: number | null; container_limit_bytes: number | null;
    process_memory_bytes: number; disk_used_bytes: number; disk_total_bytes: number;
    disk_percent: number; process_uptime_seconds: number;
  };
  services: Record<string, { status: "up" | "down"; latency_ms: number | null; memory_bytes?: number; maxmemory_bytes?: number; queued_jobs?: number; worker_heartbeat_present?: boolean }>;
  api: { available: boolean; window_minutes?: number; requests?: number; client_errors?: number; server_errors?: number; average_ms?: number | null; p95_upper_ms?: number | "inf" | null; timeline?: { timestamp: number; requests: number; errors: number }[]; routes?: { route: string; requests: number; average_ms: number; errors: number }[] };
};
