// Typed API client for the Gramglean backend.

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type LinkStatus = "pending" | "fetching" | "done" | "failed" | "skipped";
export type CookieStatus = "unknown" | "ok" | "rate_limited" | "invalid";
export type MediaType = "image" | "video";

export interface Job {
  id: number;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  link_count: number;
  total: number;
  downloaded: number;
  skipped: number;
  failed: number;
  cookie_used: string | null;
  error: string | null;
}

export interface Link {
  id: number;
  job_id: number;
  url: string;
  shortcode: string;
  status: LinkStatus;
  username: string | null;
  caption: string | null;
  taken_at: string | null;
  media_count: number;
  error: string | null;
}

export interface Media {
  id: number;
  job_id: number;
  shortcode: string;
  child_index: number;
  media_type: MediaType;
  username: string | null;
  file_path: string;
  width: number | null;
  height: number | null;
  taken_at: string | null;
  caption: string | null;
  downloaded_at: string;
}

export interface CookieFile {
  id: number;
  filename: string;
  original_name: string;
  uploaded_at: string;
  enabled: boolean;
  encrypted: boolean;
  last_used_at: string | null;
  status: CookieStatus;
  last_error: string | null;
}

export interface Settings {
  rate_limit_min: number;
  rate_limit_max: number;
  download_threads: number;
  cookies_available: number;
  cookie_encryption: boolean;
  env_defaults: {
    rate_limit_min: number;
    rate_limit_max: number;
    download_threads: number;
  };
}

export interface SettingsUpdate {
  rate_limit_min?: number;
  rate_limit_max?: number;
  download_threads?: number;
}

export interface RejectedLink {
  url: string;
  reason: string;
}

export interface QueueItem {
  id: number;
  url: string;
  shortcode: string;
  added_at: string;
}

export interface QueueAddResult {
  added: QueueItem[];
  rejected: RejectedLink[];
}

export interface JobDetail {
  job: Job;
  links: Link[];
}

export interface MediaPage {
  total: number;
  items: Media[];
}

export interface UsernameCount {
  username: string;
  count: number;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new Error("Could not reach the server — is the backend running?");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status}) — see the log file for full details.`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail.length > 0) {
        detail = body.detail;
      }
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  getQueue: () => request<QueueItem[]>("/api/queue"),

  addToQueue: (links: string[]) =>
    request<QueueAddResult>("/api/queue", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ links }),
    }),

  removeQueueItem: (id: number) =>
    request<{ ok: boolean }>(`/api/queue/${id}`, { method: "DELETE" }),

  clearQueue: () => request<{ ok: boolean }>("/api/queue", { method: "DELETE" }),

  startQueue: () => request<JobDetail>("/api/queue/start", { method: "POST" }),

  listJobs: (limit = 20) => request<Job[]>(`/api/jobs?limit=${limit}`),

  getJob: (id: number) => request<JobDetail>(`/api/jobs/${id}`),

  cancelJob: (id: number) =>
    request<{ ok: boolean }>(`/api/jobs/${id}/cancel`, { method: "POST" }),

  getJobLog: (id: number, limit = 500) =>
    request<{ lines: string[] }>(`/api/jobs/${id}/log?limit=${limit}`),

  getJobErrors: (id: number, limit = 2000) =>
    request<{ lines: string[] }>(`/api/jobs/${id}/errors?limit=${limit}`),

  listMedia: (params: {
    username?: string;
    media_type?: MediaType;
    offset?: number;
    limit?: number;
  }) => {
    const query = new URLSearchParams();
    if (params.username) query.set("username", params.username);
    if (params.media_type) query.set("media_type", params.media_type);
    query.set("offset", String(params.offset ?? 0));
    query.set("limit", String(params.limit ?? 60));
    return request<MediaPage>(`/api/media?${query.toString()}`);
  },

  listUsernames: () => request<UsernameCount[]>("/api/media/usernames"),

  mediaFileUrl: (id: number) => `/api/media/${id}/file`,

  listCookies: () => request<CookieFile[]>("/api/cookies"),

  uploadCookie: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<CookieFile>("/api/cookies", { method: "POST", body: form });
  },

  updateCookie: (id: number, patch: { enabled?: boolean; original_name?: string }) =>
    request<CookieFile>(`/api/cookies/${id}`, {
      method: "PATCH",
      headers: JSON_HEADERS,
      body: JSON.stringify(patch),
    }),

  deleteCookie: (id: number) =>
    request<{ ok: boolean }>(`/api/cookies/${id}`, { method: "DELETE" }),

  getSettings: () => request<Settings>("/api/settings"),

  updateSettings: (patch: SettingsUpdate) =>
    request<Settings>("/api/settings", {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify(patch),
    }),
};

export function errorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  return "Something went wrong — see the log file for full details.";
}

export function isJobActive(status: JobStatus): boolean {
  return status === "queued" || status === "running";
}
