import type { CookieStatus, JobStatus, LinkStatus } from "../lib/api";

export type AnyStatus = JobStatus | LinkStatus | CookieStatus;

interface BadgeConfig {
  label: string;
  className: string;
  pulse?: boolean;
}

const CONFIG: Record<AnyStatus, BadgeConfig> = {
  // Job statuses
  queued: { label: "Queued", className: "border-mauve-500/60 bg-mauve-800/60 text-thistle-400" },
  running: {
    label: "Running",
    className: "border-rose-400/60 bg-rose-700/40 text-rose-200",
    pulse: true,
  },
  completed: {
    label: "Completed",
    className: "border-thistle-500/50 bg-thistle-300/10 text-thistle-200",
  },
  cancelled: { label: "Cancelled", className: "border-mauve-500/50 bg-carbon-600/70 text-thistle-500" },
  // Link statuses (failed/skipped shared with jobs)
  pending: { label: "Pending", className: "border-mauve-500/60 bg-mauve-800/60 text-thistle-400" },
  fetching: {
    label: "Fetching",
    className: "border-rose-400/60 bg-rose-700/40 text-rose-200",
    pulse: true,
  },
  done: { label: "Done", className: "border-thistle-500/50 bg-thistle-300/10 text-thistle-200" },
  skipped: { label: "Skipped", className: "border-mauve-500/50 bg-mauve-700/40 text-thistle-400" },
  failed: { label: "Failed", className: "border-mahogany-400/60 bg-mahogany-700/50 text-mahogany-300" },
  // Cookie statuses
  ok: { label: "OK", className: "border-thistle-500/50 bg-thistle-300/10 text-thistle-200" },
  rate_limited: {
    label: "Rate limited",
    className: "border-rose-400/60 bg-rose-800/50 text-rose-300",
  },
  invalid: { label: "Invalid", className: "border-mahogany-400/60 bg-mahogany-700/50 text-mahogany-300" },
  unknown: { label: "Unknown", className: "border-mauve-500/50 bg-carbon-600/70 text-thistle-500" },
};

export default function StatusBadge({ status }: { status: AnyStatus }) {
  const config = CONFIG[status] ?? CONFIG.unknown;
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${config.className}`}
    >
      {config.pulse && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden="true" />
      )}
      {config.label}
    </span>
  );
}
