export interface Account {
  id: number;
  username: string;
  full_name: string | null;
  profile_pic_url: string | null;
  added_at: string;
  last_synced_at: string | null;
  include_posts: boolean;
  include_reels: boolean;
  include_stories: boolean;
  media_count?: number;
}

export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "rate_limited";

export interface Job {
  id: number;
  account_id: number;
  username: string;
  status: JobStatus;
  include_posts: boolean;
  include_reels: boolean;
  include_stories: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  downloaded: number;
  skipped: number;
  failed: number;
  cookie_used: string | null;
  error: string | null;
}

export interface Media {
  id: number;
  account_id: number;
  shortcode: string;
  child_index: number;
  media_type: "image" | "video";
  source: "post" | "carousel" | "reel" | "story";
  file_path: string;
  taken_at: string | null;
  caption: string | null;
}

export interface CookieFile {
  id: number;
  filename: string;
  original_name: string;
  label: string | null;
  uploaded_at: string;
  enabled: boolean;
  encrypted: boolean;
  last_used_at: string | null;
  status: "unknown" | "ok" | "rate_limited" | "invalid";
  last_error: string | null;
}

export interface Settings {
  rate_limit_min: number;
  rate_limit_max: number;
  download_threads: number;
  theme: string;
  default_include_posts: boolean;
  default_include_reels: boolean;
  default_include_stories: boolean;
  cookies_available: number;
  cookie_encryption: boolean;
  env_defaults: {
    download_threads: number;
    max_concurrent_jobs: number;
    rate_limit_min: number;
    rate_limit_max: number;
  };
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: opts.body && !(opts.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : undefined,
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // accounts
  listAccounts: () => req<Account[]>("/api/accounts"),
  createAccount: (body: Partial<Account> & { username: string }) =>
    req<Account>("/api/accounts", { method: "POST", body: JSON.stringify(body) }),
  updateAccount: (id: number, body: Partial<Account>) =>
    req<Account>(`/api/accounts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteAccount: (id: number) =>
    req<void>(`/api/accounts/${id}`, { method: "DELETE" }),

  // jobs
  listJobs: (accountId?: number) =>
    req<Job[]>(`/api/jobs${accountId ? `?account_id=${accountId}` : ""}`),
  getJob: (id: number) => req<Job>(`/api/jobs/${id}`),
  createJob: (body: {
    username: string;
    include_posts: boolean;
    include_reels: boolean;
    include_stories: boolean;
  }) => req<Job>("/api/jobs", { method: "POST", body: JSON.stringify(body) }),
  cancelJob: (id: number) =>
    req<{ cancelled: boolean }>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  getJobLog: (id: number) => req<{ lines: string[] }>(`/api/jobs/${id}/log`),
  getJobErrors: (id: number) => req<{ lines: string[] }>(`/api/jobs/${id}/errors`),

  // media
  listMedia: (params: {
    account_id?: number;
    source?: string;
    media_type?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    });
    return req<{ total: number; items: Media[] }>(`/api/media?${qs.toString()}`);
  },
  mediaFileUrl: (id: number) => `/api/media/${id}/file`,

  // settings
  getSettings: () => req<Settings>("/api/settings"),
  updateSettings: (body: Partial<Settings>) =>
    req<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(body) }),

  // cookies
  listCookies: () => req<CookieFile[]>("/api/cookies"),
  uploadCookie: (file: File, label?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    if (label) fd.append("label", label);
    return req<CookieFile>("/api/cookies", { method: "POST", body: fd });
  },
  updateCookie: (id: number, body: Partial<CookieFile>) =>
    req<CookieFile>(`/api/cookies/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteCookie: (id: number) =>
    req<void>(`/api/cookies/${id}`, { method: "DELETE" }),
};
