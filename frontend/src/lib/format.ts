// Date/text formatting helpers.

/**
 * Parse an ISO timestamp from the server. Naive timestamps (no timezone
 * suffix) are treated as UTC by appending "Z".
 */
export function parseServerDate(value: string): Date {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

export function timeAgo(value: string | null): string {
  if (!value) return "—";
  const then = parseServerDate(value);
  if (Number.isNaN(then.getTime())) return "—";
  const seconds = Math.round((Date.now() - then.getTime()) / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return then.toLocaleDateString();
}

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = parseServerDate(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** Last path segment of a file path (handles both / and \ separators). */
export function baseName(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || "media";
}
