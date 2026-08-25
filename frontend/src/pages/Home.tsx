import { useEffect, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Cookie, Download, Loader2, X, XCircle } from "lucide-react";
import { api, errorMessage } from "../lib/api";
import type { Job, RejectedLink } from "../lib/api";
import { timeAgo } from "../lib/format";
import { Page } from "../components/Layout";
import StatusBadge from "../components/StatusBadge";
import { useToast } from "../components/Toast";

const NOTICE_KEY = "gramglean:cookie-notice-dismissed";

export default function Home() {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [rejected, setRejected] = useState<RejectedLink[]>([]);
  const [createdJobId, setCreatedJobId] = useState<number | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);
  const [cookiesAvailable, setCookiesAvailable] = useState<number | null>(null);
  const [noticeDismissed, setNoticeDismissed] = useState(() => {
    try {
      return window.localStorage.getItem(NOTICE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    let stale = false;
    void (async () => {
      const [jobsRes, settingsRes] = await Promise.allSettled([
        api.listJobs(20),
        api.getSettings(),
      ]);
      if (stale) return;
      if (jobsRes.status === "fulfilled") setJobs(jobsRes.value);
      if (settingsRes.status === "fulfilled") {
        setCookiesAvailable(settingsRes.value.cookies_available);
      }
      const failure = [jobsRes, settingsRes].find((r) => r.status === "rejected");
      if (failure && failure.status === "rejected") {
        toast(errorMessage(failure.reason));
      }
      setJobsLoaded(true);
    })();
    return () => {
      stale = true;
    };
  }, [toast]);

  const dismissNotice = () => {
    setNoticeDismissed(true);
    try {
      window.localStorage.setItem(NOTICE_KEY, "1");
    } catch {
      // Storage unavailable; the notice stays dismissed for this session.
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const links = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
    if (links.length === 0) {
      toast("Paste at least one Instagram link first.", "info");
      return;
    }
    setSubmitting(true);
    setRejected([]);
    setCreatedJobId(null);
    try {
      const result = await api.createJob(links);
      if (result.rejected.length === 0) {
        navigate(`/jobs/${result.job.id}`);
      } else {
        setRejected(result.rejected);
        setCreatedJobId(result.job.id);
        toast(
          `Job started — ${result.rejected.length} ${
            result.rejected.length === 1 ? "link" : "links"
          } couldn't be queued.`,
          "info",
        );
      }
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Page>
      {/* Hero */}
      <section className="relative mb-12">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 left-1/2 h-72 w-[36rem] max-w-full -translate-x-1/2 rounded-full bg-gradient-to-br from-mahogany-500/25 via-rose-600/20 to-transparent blur-3xl"
        />
        <div className="relative mx-auto max-w-3xl pt-4 text-center md:pt-12">
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="text-3xl font-bold tracking-tight text-thistle-100 sm:text-5xl"
          >
            Keep every post you love
          </motion.h1>
          <p className="mt-3 text-sm text-thistle-400 sm:text-base">
            Paste Instagram post links below — Gramglean downloads every photo and
            video in each post, full carousels included.
          </p>

          <form onSubmit={(e) => void handleSubmit(e)} className="mt-8 text-left">
            <label htmlFor="links-input" className="sr-only">
              Instagram links, one per line
            </label>
            <textarea
              id="links-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              placeholder={"Paste Instagram links (one per line)\nhttps://www.instagram.com/p/…"}
              className="w-full resize-y rounded-2xl border border-mauve-500/60 bg-carbon-700/80 px-4 py-3.5 font-mono text-sm text-thistle-200 placeholder:text-thistle-600 shadow-inner transition-colors focus:border-rose-400/70"
            />
            <div className="mt-4 flex justify-center">
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-rose-500 to-mahogany-500 px-8 py-3 text-base font-semibold text-thistle-100 shadow-glow transition-transform hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                ) : (
                  <Download className="h-5 w-5" aria-hidden="true" />
                )}
                {submitting ? "Starting…" : "Download"}
              </button>
            </div>
          </form>

          {rejected.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-6 rounded-xl border border-mahogany-400/50 bg-mahogany-800/40 p-4 text-left"
            >
              <p className="flex items-center gap-2 text-sm font-medium text-thistle-100">
                <XCircle className="h-4 w-4 shrink-0 text-mahogany-300" aria-hidden="true" />
                {rejected.length === 1
                  ? "One link couldn't be queued"
                  : `${rejected.length} links couldn't be queued`}
              </p>
              <ul className="mt-2 space-y-1.5">
                {rejected.map((r, i) => (
                  <li key={`${r.url}-${i}`} className="text-xs text-thistle-400">
                    <span className="break-all font-mono text-thistle-300">{r.url}</span>
                    <span className="text-mahogany-300"> — {r.reason}</span>
                  </li>
                ))}
              </ul>
              {createdJobId !== null && (
                <RouterLink
                  to={`/jobs/${createdJobId}`}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-rose-600/40 px-3 py-1.5 text-sm font-medium text-thistle-100 transition-colors hover:bg-rose-600/60"
                >
                  The rest are downloading — view job #{createdJobId}
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </RouterLink>
              )}
            </motion.div>
          )}
        </div>
      </section>

      {/* Cookie notice */}
      {cookiesAvailable === 0 && !noticeDismissed && (
        <div className="mb-8 flex items-start gap-3 rounded-xl border border-mauve-500/50 bg-mauve-800/30 px-4 py-3">
          <Cookie className="mt-0.5 h-4 w-4 shrink-0 text-thistle-400" aria-hidden="true" />
          <p className="flex-1 text-xs leading-relaxed text-thistle-400">
            Public posts download without any setup. For private posts and fewer
            rate limits, add an Instagram cookie file in{" "}
            <RouterLink
              to="/settings"
              className="font-medium text-thistle-200 underline underline-offset-2 hover:text-thistle-100"
            >
              Settings
            </RouterLink>
            .
          </p>
          <button
            type="button"
            aria-label="Dismiss notice"
            onClick={dismissNotice}
            className="rounded p-0.5 text-thistle-500 transition-colors hover:text-thistle-200"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {/* Recent jobs */}
      <section>
        <h2 className="mb-4 text-lg font-semibold text-thistle-100">Recent jobs</h2>
        {jobs.length === 0 ? (
          <p className="rounded-xl border border-dashed border-mauve-700/60 px-4 py-8 text-center text-sm text-thistle-500">
            {jobsLoaded
              ? "No jobs yet — paste some links above to get started."
              : "Loading…"}
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {jobs.map((job) => (
              <RouterLink
                key={job.id}
                to={`/jobs/${job.id}`}
                className="rounded-xl border border-mauve-800/70 bg-carbon-700/50 p-4 transition-colors hover:border-rose-500/60 hover:bg-carbon-600/50"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-thistle-100">Job #{job.id}</span>
                  <StatusBadge status={job.status} />
                </div>
                <p className="mt-2 text-sm text-thistle-400">
                  {job.link_count} {job.link_count === 1 ? "link" : "links"} ·{" "}
                  {job.downloaded}/{job.total} downloaded
                  {job.failed > 0 && (
                    <span className="text-mahogany-300"> · {job.failed} failed</span>
                  )}
                </p>
                <p className="mt-1 text-xs text-thistle-600">{timeAgo(job.created_at)}</p>
              </RouterLink>
            ))}
          </div>
        )}
      </section>
    </Page>
  );
}
