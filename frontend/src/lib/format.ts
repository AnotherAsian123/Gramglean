import type { JobStatus } from "./api";

export function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").getTime();
  const secs = Math.floor((Date.now() - then) / 1000);
  if (Number.isNaN(secs)) return "—";
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(then).toLocaleDateString();
}

export const statusStyles: Record<JobStatus, string> = {
  queued: "bg-neutral-500/15 text-neutral-300 border-neutral-500/30",
  running: "bg-ig-blue/15 text-ig-blue border-ig-blue/40",
  completed: "bg-emerald-500/15 text-emerald-400 border-emerald-500/40",
  failed: "bg-red-500/15 text-red-400 border-red-500/40",
  cancelled: "bg-neutral-500/15 text-neutral-400 border-neutral-500/30",
  rate_limited: "bg-amber-500/15 text-amber-400 border-amber-500/40",
};

export const statusLabel: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
  rate_limited: "Rate limited",
};
