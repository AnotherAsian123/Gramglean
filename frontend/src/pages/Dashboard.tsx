import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Download,
  RefreshCw,
  Trash2,
  AlertTriangle,
  Images as ImagesIcon,
  Loader2,
} from "lucide-react";
import { api, type Account, type Job, type Settings } from "../lib/api";
import ContentToggles, { type ContentSelection } from "../components/ContentToggles";
import StatusBadge from "../components/StatusBadge";
import { timeAgo } from "../lib/format";

function Avatar({ account }: { account: Account }) {
  const [failed, setFailed] = useState(false);
  const initial = account.username.charAt(0).toUpperCase();
  return (
    <div className="ig-ring grid h-14 w-14 shrink-0 place-items-center rounded-full p-[2px]">
      <div className="grid h-full w-full place-items-center overflow-hidden rounded-full bg-ink-850">
        {account.profile_pic_url && !failed ? (
          <img
            src={account.profile_pic_url}
            alt={account.username}
            className="h-full w-full object-cover"
            onError={() => setFailed(true)}
          />
        ) : (
          <span className="text-lg font-bold text-neutral-200">{initial}</span>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [username, setUsername] = useState("");
  const [selection, setSelection] = useState<ContentSelection>({
    include_posts: true,
    include_reels: true,
    include_stories: false,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [a, j] = await Promise.all([api.listAccounts(), api.listJobs()]);
    setAccounts(a);
    setJobs(j);
  }

  useEffect(() => {
    api.getSettings().then((s) => {
      setSettings(s);
      setSelection({
        include_posts: s.default_include_posts,
        include_reels: s.default_include_reels,
        include_stories: s.default_include_stories,
      });
    });
    refresh().catch((e) => setError(String(e.message ?? e)));
  }, []);

  async function startScrape(name: string, sel: ContentSelection) {
    setError(null);
    if (!sel.include_posts && !sel.include_reels && !sel.include_stories) {
      setError("Pick at least one content type.");
      return;
    }
    setBusy(true);
    try {
      const job = await api.createJob({ username: name, ...sel });
      navigate(`/jobs/${job.id}`);
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function resync(acc: Account) {
    await startScrape(acc.username, {
      include_posts: acc.include_posts,
      include_reels: acc.include_reels,
      include_stories: acc.include_stories,
    });
  }

  async function remove(acc: Account) {
    if (!confirm(`Remove @${acc.username} from the watchlist? Files on disk are kept.`)) return;
    await api.deleteAccount(acc.id);
    refresh();
  }

  const noCookies = settings && settings.cookies_available === 0;

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section>
        <h1 className="text-2xl font-extrabold tracking-tight">
          Archive an <span className="ig-gradient-text">Instagram</span> account
        </h1>
        <p className="mt-1 text-sm text-neutral-400">
          Full-resolution posts, carousels, reels and stories — saved locally, forever.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            startScrape(username, selection);
          }}
          className="card mt-5 space-y-4 p-5"
        >
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-neutral-500">
                @
              </span>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="username"
                className="input pl-8"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
              />
            </div>
            <button type="submit" className="btn-primary sm:w-40" disabled={busy}>
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              {busy ? "Starting…" : "Scrape"}
            </button>
          </div>
          <ContentToggles value={selection} onChange={setSelection} />
          {error && <p className="text-sm font-medium text-red-400">{error}</p>}
        </form>

        {noCookies && (
          <Link
            to="/settings"
            className="mt-3 flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-300 transition hover:bg-amber-500/15"
          >
            <AlertTriangle className="h-4 w-4 shrink-0" />
            No Instagram cookies uploaded yet. Scraping will be heavily rate-limited —
            add a cookies.txt in Settings.
          </Link>
        )}
      </section>

      {/* Watchlist */}
      <section>
        <h2 className="mb-3 text-sm font-bold uppercase tracking-widest text-neutral-500">
          Watchlist
        </h2>
        {accounts.length === 0 ? (
          <p className="text-sm text-neutral-500">No accounts yet. Scrape one above to begin.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {accounts.map((acc) => (
              <motion.div
                key={acc.id}
                layout
                className="card flex items-center gap-4 p-4"
              >
                <Avatar account={acc} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-bold">@{acc.username}</span>
                  </div>
                  <div className="truncate text-xs text-neutral-400">
                    {acc.full_name || "—"}
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-neutral-500">
                    <span className="flex items-center gap-1">
                      <ImagesIcon className="h-3.5 w-3.5" />
                      {acc.media_count ?? 0}
                    </span>
                    <span>synced {timeAgo(acc.last_synced_at)}</span>
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <button
                    className="btn-primary px-3 py-1.5 text-xs"
                    onClick={() => resync(acc)}
                    title="Re-sync new posts"
                  >
                    <RefreshCw className="h-3.5 w-3.5" /> Sync
                  </button>
                  <div className="flex gap-2">
                    <Link
                      to={`/gallery?account=${acc.id}`}
                      className="btn-ghost px-3 py-1.5 text-xs"
                    >
                      View
                    </Link>
                    <button
                      className="btn-ghost px-2 py-1.5 text-xs text-red-400"
                      onClick={() => remove(acc)}
                      title="Remove"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </section>

      {/* Recent jobs */}
      <section>
        <h2 className="mb-3 text-sm font-bold uppercase tracking-widest text-neutral-500">
          Recent jobs
        </h2>
        {jobs.length === 0 ? (
          <p className="text-sm text-neutral-500">No jobs run yet.</p>
        ) : (
          <div className="card divide-y divide-ink-700 overflow-hidden">
            {jobs.slice(0, 8).map((job) => (
              <Link
                key={job.id}
                to={`/jobs/${job.id}`}
                className="flex items-center justify-between gap-3 px-4 py-3 transition hover:bg-ink-800/60"
              >
                <div className="min-w-0">
                  <div className="truncate font-semibold">@{job.username}</div>
                  <div className="text-xs text-neutral-500">
                    {timeAgo(job.created_at)} · ↓{job.downloaded} ⟳{job.skipped} ✕
                    {job.failed}
                  </div>
                </div>
                <StatusBadge status={job.status} />
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
