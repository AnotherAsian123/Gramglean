import { useEffect, useRef, useState } from "react";
import {
  Upload,
  Trash2,
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  Clock4,
  Cpu,
  Gauge,
  Cookie,
  Check,
  Lock,
  Unlock,
} from "lucide-react";
import { api, type CookieFile, type Settings as TSettings } from "../lib/api";
import ContentToggles from "../components/ContentToggles";
import { timeAgo } from "../lib/format";

const cookieStatus = {
  ok: { icon: ShieldCheck, cls: "text-emerald-400", label: "OK" },
  rate_limited: { icon: Clock4, cls: "text-amber-400", label: "Rate limited" },
  invalid: { icon: ShieldAlert, cls: "text-red-400", label: "Invalid" },
  unknown: { icon: ShieldQuestion, cls: "text-neutral-400", label: "Unused" },
} as const;

function Section({
  icon: Icon,
  title,
  desc,
  children,
}: {
  icon: typeof Cpu;
  title: string;
  desc: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-5">
      <div className="mb-4 flex items-start gap-3">
        <div className="ig-gradient grid h-9 w-9 shrink-0 place-items-center rounded-lg">
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div>
          <h2 className="font-bold">{title}</h2>
          <p className="text-xs text-neutral-400">{desc}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

export default function Settings() {
  const [settings, setSettings] = useState<TSettings | null>(null);
  const [cookies, setCookies] = useState<CookieFile[]>([]);
  const [saved, setSaved] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function reload() {
    const [s, c] = await Promise.all([api.getSettings(), api.listCookies()]);
    setSettings(s);
    setCookies(c);
    applyTheme(s.theme);
  }

  useEffect(() => {
    reload();
  }, []);

  function applyTheme(theme: string) {
    const root = document.documentElement;
    root.classList.toggle("light", theme === "light");
    root.classList.toggle("dark", theme !== "light");
  }

  async function patch(update: Partial<TSettings>) {
    const next = await api.updateSettings(update);
    setSettings(next);
    if (update.theme) applyTheme(next.theme);
    setSaved(true);
    setTimeout(() => setSaved(false), 1200);
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    setUploadError(null);
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await api.uploadCookie(file);
      await reload();
    } catch (err: any) {
      setUploadError(String(err.message ?? err));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  if (!settings) return <div className="h-40 skeleton rounded-2xl" />;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">Settings</h1>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-emerald-400">
            <Check className="h-4 w-4" /> Saved
          </span>
        )}
      </div>

      {/* Cookies */}
      <Section
        icon={Cookie}
        title="Instagram cookies"
        desc="Upload cookies.txt exported while logged in. Add several (e.g. from different accounts) — the scraper cycles through them to dodge rate limits. Uploads never overwrite existing cookies."
      >
        <input
          ref={fileRef}
          type="file"
          accept=".txt,text/plain"
          className="hidden"
          onChange={onUpload}
        />
        <button className="btn-primary" onClick={() => fileRef.current?.click()}>
          <Upload className="h-4 w-4" /> Upload cookies.txt
        </button>
        {uploadError && <p className="mt-2 text-sm text-red-400">{uploadError}</p>}

        <div
          className={`mt-3 flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
            settings.cookie_encryption
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-ink-700 bg-ink-900/50 text-neutral-400"
          }`}
        >
          {settings.cookie_encryption ? (
            <>
              <Lock className="h-3.5 w-3.5 shrink-0" />
              Encryption active (AES-256-GCM). New uploads are encrypted at rest.
            </>
          ) : (
            <>
              <Unlock className="h-3.5 w-3.5 shrink-0" />
              Not encrypted. Set the COOKIE_ENCRYPTION_KEY container variable to
              encrypt cookies at rest.
            </>
          )}
        </div>

        <div className="mt-4 space-y-2">
          {cookies.length === 0 ? (
            <p className="text-sm text-neutral-500">No cookies uploaded yet.</p>
          ) : (
            cookies.map((c) => {
              const st = cookieStatus[c.status];
              const Icon = st.icon;
              return (
                <div
                  key={c.id}
                  className="flex items-center gap-3 rounded-xl border border-ink-700 bg-ink-900/50 px-4 py-3"
                >
                  <Icon className={`h-5 w-5 shrink-0 ${st.cls}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 truncate text-sm font-semibold">
                      {c.encrypted && (
                        <Lock className="h-3 w-3 shrink-0 text-emerald-400" />
                      )}
                      {c.label || c.original_name}
                    </div>
                    <div className="text-xs text-neutral-500">
                      {st.label} · used {timeAgo(c.last_used_at)}
                      {c.last_error ? ` · ${c.last_error.slice(0, 60)}` : ""}
                    </div>
                  </div>
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-neutral-400">
                    <input
                      type="checkbox"
                      checked={c.enabled}
                      onChange={async () => {
                        await api.updateCookie(c.id, { enabled: !c.enabled });
                        reload();
                      }}
                    />
                    Enabled
                  </label>
                  <button
                    className="text-red-400 hover:text-red-300"
                    onClick={async () => {
                      await api.deleteCookie(c.id);
                      reload();
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </Section>

      {/* Rate limiting */}
      <Section
        icon={Gauge}
        title="Rate limiting"
        desc="Randomized delay (seconds) inserted between Instagram API page requests. Higher = slower but safer against locks. Applies to the next job."
      >
        <div className="grid gap-5 sm:grid-cols-2">
          {(["rate_limit_min", "rate_limit_max"] as const).map((key) => (
            <div key={key}>
              <div className="mb-1 flex justify-between text-sm">
                <span className="text-neutral-400">
                  {key === "rate_limit_min" ? "Minimum delay" : "Maximum delay"}
                </span>
                <span className="font-semibold">{settings[key].toFixed(1)}s</span>
              </div>
              <input
                type="range"
                min={0}
                max={20}
                step={0.5}
                value={settings[key]}
                onChange={(e) =>
                  setSettings({ ...settings, [key]: Number(e.target.value) })
                }
                onMouseUp={(e) =>
                  patch({ [key]: Number((e.target as HTMLInputElement).value) })
                }
                className="w-full accent-ig-pink"
              />
            </div>
          ))}
        </div>
      </Section>

      {/* Concurrency */}
      <Section
        icon={Cpu}
        title="Download threads"
        desc="Parallel download workers. Downloading is IO-bound, so threads speed it up — but more threads means more simultaneous requests and higher ban risk. The container default comes from the DOWNLOAD_THREADS env var."
      >
        <div className="flex items-center gap-4">
          <input
            type="range"
            min={1}
            max={16}
            step={1}
            value={settings.download_threads}
            onChange={(e) =>
              setSettings({ ...settings, download_threads: Number(e.target.value) })
            }
            onMouseUp={(e) =>
              patch({ download_threads: Number((e.target as HTMLInputElement).value) })
            }
            className="flex-1 accent-ig-pink"
          />
          <span className="w-10 text-right text-lg font-extrabold">
            {settings.download_threads}
          </span>
        </div>
        <p className="mt-2 text-xs text-neutral-500">
          Env default: {settings.env_defaults.download_threads} · Concurrent jobs
          (env only): {settings.env_defaults.max_concurrent_jobs}
        </p>
      </Section>

      {/* Defaults + theme */}
      <Section
        icon={Check}
        title="Defaults & appearance"
        desc="Content types pre-selected for new scrapes, and the app theme."
      >
        <ContentToggles
          value={{
            include_posts: settings.default_include_posts,
            include_reels: settings.default_include_reels,
            include_stories: settings.default_include_stories,
          }}
          onChange={(sel) =>
            patch({
              default_include_posts: sel.include_posts,
              default_include_reels: sel.include_reels,
              default_include_stories: sel.include_stories,
            })
          }
        />
        <div className="mt-4 flex gap-2">
          {["dark", "light"].map((t) => (
            <button
              key={t}
              className={settings.theme === t ? "chip-on" : "chip-off"}
              onClick={() => patch({ theme: t })}
            >
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </Section>
    </div>
  );
}
