import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Cookie, Loader2, Lock, Trash2, Upload } from "lucide-react";
import { api, errorMessage } from "../lib/api";
import type { CookieFile, Settings as SettingsData } from "../lib/api";
import { timeAgo } from "../lib/format";
import { Page } from "../components/Layout";
import StatusBadge from "../components/StatusBadge";
import { useToast } from "../components/Toast";

interface SliderValues {
  rate_limit_min: number;
  rate_limit_max: number;
  download_threads: number;
}

export default function Settings() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [form, setForm] = useState<SliderValues | null>(null);
  const [cookies, setCookies] = useState<CookieFile[]>([]);
  const [cookiesLoaded, setCookiesLoaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const { toast } = useToast();

  // Refs so the commit callback always reads the latest values, even when the
  // triggering pointer/key event fires in the same gesture as the last change.
  const formRef = useRef<SliderValues | null>(null);
  formRef.current = form;
  const settingsRef = useRef<SettingsData | null>(null);
  settingsRef.current = settings;

  useEffect(() => {
    let stale = false;
    api
      .getSettings()
      .then((s) => {
        if (stale) return;
        setSettings(s);
        setForm({
          rate_limit_min: s.rate_limit_min,
          rate_limit_max: s.rate_limit_max,
          download_threads: s.download_threads,
        });
      })
      .catch((err: unknown) => {
        if (!stale) toast(errorMessage(err));
      });
    api
      .listCookies()
      .then((c) => {
        if (!stale) setCookies(c);
      })
      .catch((err: unknown) => {
        if (!stale) toast(errorMessage(err));
      })
      .finally(() => {
        if (!stale) setCookiesLoaded(true);
      });
    return () => {
      stale = true;
    };
  }, [toast]);

  const commitSliders = useCallback(async () => {
    const current = formRef.current;
    const saved = settingsRef.current;
    if (!current) return;
    const payload: SliderValues = { ...current };
    if (payload.rate_limit_max < payload.rate_limit_min) {
      payload.rate_limit_max = payload.rate_limit_min;
    }
    if (
      saved &&
      saved.rate_limit_min === payload.rate_limit_min &&
      saved.rate_limit_max === payload.rate_limit_max &&
      saved.download_threads === payload.download_threads
    ) {
      if (payload.rate_limit_max !== current.rate_limit_max) setForm(payload);
      return;
    }
    try {
      const updated = await api.updateSettings(payload);
      setSettings(updated);
      setForm({
        rate_limit_min: updated.rate_limit_min,
        rate_limit_max: updated.rate_limit_max,
        download_threads: updated.download_threads,
      });
      toast("Settings saved.", "success");
    } catch (err) {
      toast(errorMessage(err));
    }
  }, [toast]);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      const created = await api.uploadCookie(file);
      setCookies((prev) => [...prev, created]);
      toast(`Uploaded ${created.original_name}.`, "success");
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const toggleCookie = async (cookie: CookieFile) => {
    try {
      const updated = await api.updateCookie(cookie.id, { enabled: !cookie.enabled });
      setCookies((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (err) {
      toast(errorMessage(err));
    }
  };

  const deleteCookie = async (cookie: CookieFile) => {
    const confirmed = window.confirm(
      `Delete cookie file "${cookie.original_name}"? This cannot be undone.`,
    );
    if (!confirmed) return;
    try {
      await api.deleteCookie(cookie.id);
      setCookies((prev) => prev.filter((c) => c.id !== cookie.id));
      toast(`Deleted ${cookie.original_name}.`, "success");
    } catch (err) {
      toast(errorMessage(err));
    }
  };

  return (
    <Page>
      <h1 className="mb-8 text-2xl font-semibold text-thistle-100">Settings</h1>

      {/* Cookies */}
      <section className="mb-10">
        <div className="mb-1.5 flex flex-wrap items-center gap-3">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-thistle-100">
            <Cookie className="h-5 w-5 text-thistle-400" aria-hidden="true" />
            Instagram cookies
          </h2>
          {settings?.cookie_encryption && (
            <span className="inline-flex items-center gap-1 rounded-full border border-thistle-500/40 bg-thistle-300/10 px-2.5 py-0.5 text-xs text-thistle-200">
              <Lock className="h-3 w-3" aria-hidden="true" />
              Encrypted at rest
            </span>
          )}
        </div>
        <p className="mb-4 text-sm text-thistle-500">
          Upload a cookies.txt export to download private posts and reduce rate
          limiting.
          {settings && !settings.cookie_encryption
            ? " Cookie files are stored unencrypted on disk."
            : ""}
        </p>

        <label className="mb-4 inline-flex cursor-pointer items-center gap-2 rounded-xl border border-mauve-500/60 bg-carbon-700/70 px-4 py-2.5 text-sm font-medium text-thistle-200 transition-colors hover:border-rose-500/60 hover:text-thistle-100 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-rose-300">
          <input
            type="file"
            accept=".txt,text/plain"
            className="sr-only"
            onChange={(e) => void handleUpload(e)}
            disabled={uploading}
          />
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Upload className="h-4 w-4" aria-hidden="true" />
          )}
          {uploading ? "Uploading…" : "Upload cookies.txt"}
        </label>

        <ul className="divide-y divide-mauve-800/60 rounded-xl border border-mauve-800/60 bg-carbon-700/40">
          {cookies.map((cookie) => (
            <li
              key={cookie.id}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3.5"
            >
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-medium text-thistle-100">
                  <span className="truncate">{cookie.original_name}</span>
                  {cookie.encrypted && (
                    <Lock
                      className="h-3.5 w-3.5 shrink-0 text-thistle-500"
                      aria-label="Encrypted at rest"
                    />
                  )}
                </p>
                <p className="mt-0.5 text-xs text-thistle-500">
                  Uploaded {timeAgo(cookie.uploaded_at)}
                  {cookie.last_used_at ? ` · last used ${timeAgo(cookie.last_used_at)}` : ""}
                </p>
                {cookie.last_error && (
                  <p className="mt-1 text-xs text-mahogany-300">{cookie.last_error}</p>
                )}
              </div>
              <StatusBadge status={cookie.status} />
              <button
                type="button"
                role="switch"
                aria-checked={cookie.enabled}
                aria-label={`${cookie.enabled ? "Disable" : "Enable"} ${cookie.original_name}`}
                onClick={() => void toggleCookie(cookie)}
                className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
                  cookie.enabled ? "bg-rose-500" : "bg-mauve-800"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-thistle-200 transition-all ${
                    cookie.enabled ? "left-[22px]" : "left-0.5"
                  }`}
                />
              </button>
              <button
                type="button"
                aria-label={`Delete ${cookie.original_name}`}
                onClick={() => void deleteCookie(cookie)}
                className="rounded-lg p-2 text-thistle-500 transition-colors hover:bg-mahogany-700/40 hover:text-mahogany-300"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            </li>
          ))}
          {cookies.length === 0 && (
            <li className="px-4 py-6 text-sm text-thistle-500">
              {cookiesLoaded
                ? "No cookie files yet — public posts still work without one."
                : "Loading…"}
            </li>
          )}
        </ul>
      </section>

      {/* Download behaviour */}
      <section>
        <h2 className="mb-4 text-lg font-semibold text-thistle-100">Download behaviour</h2>
        {form && settings ? (
          <div className="space-y-6 rounded-xl border border-mauve-800/60 bg-carbon-700/40 p-5">
            <SliderField
              label="Minimum delay between downloads"
              value={form.rate_limit_min}
              min={0}
              max={60}
              step={0.5}
              unit="s"
              hint={`Default: ${settings.env_defaults.rate_limit_min}s`}
              onChange={(v) => setForm((f) => (f ? { ...f, rate_limit_min: v } : f))}
              onCommit={() => void commitSliders()}
            />
            <SliderField
              label="Maximum delay between downloads"
              value={form.rate_limit_max}
              min={0}
              max={120}
              step={0.5}
              unit="s"
              hint={`Default: ${settings.env_defaults.rate_limit_max}s — kept at or above the minimum delay`}
              onChange={(v) => setForm((f) => (f ? { ...f, rate_limit_max: v } : f))}
              onCommit={() => void commitSliders()}
            />
            <SliderField
              label="Download threads"
              value={form.download_threads}
              min={1}
              max={16}
              step={1}
              hint={`Default: ${settings.env_defaults.download_threads}`}
              onChange={(v) => setForm((f) => (f ? { ...f, download_threads: v } : f))}
              onCommit={() => void commitSliders()}
            />
          </div>
        ) : (
          <div className="flex justify-center rounded-xl border border-mauve-800/60 bg-carbon-700/40 py-10">
            <Loader2 className="h-6 w-6 animate-spin text-thistle-500" aria-label="Loading settings" />
          </div>
        )}
      </section>
    </Page>
  );
}

interface SliderFieldProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  hint: string;
  onChange: (value: number) => void;
  onCommit: () => void;
}

function SliderField({
  label,
  value,
  min,
  max,
  step,
  unit,
  hint,
  onChange,
  onCommit,
}: SliderFieldProps) {
  const id = useId();
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-thistle-200">
          {label}
        </label>
        <span className="font-mono text-sm text-thistle-100">
          {value}
          {unit ?? ""}
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        onPointerUp={onCommit}
        onKeyUp={onCommit}
        onTouchEnd={onCommit}
        className="w-full accent-rose-400"
      />
      <p className="mt-1 text-xs text-thistle-500">{hint}</p>
    </div>
  );
}
