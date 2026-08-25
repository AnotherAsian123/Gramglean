import { useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowLeft, Loader2, RefreshCw, XCircle } from "lucide-react";
import { api, errorMessage, isJobActive } from "../lib/api";
import { useJobSocket } from "../lib/useJobSocket";
import { timeAgo } from "../lib/format";
import { Page } from "../components/Layout";
import StatusBadge from "../components/StatusBadge";
import { useToast } from "../components/Toast";

type Tab = "links" | "log" | "failures";

export default function JobView() {
  const { id } = useParams();
  const jobId = id !== undefined && /^\d+$/.test(id) ? Number(id) : null;
  const { job, links, connection } = useJobSocket(jobId);
  const [tab, setTab] = useState<Tab>("links");
  const [logLines, setLogLines] = useState<string[]>([]);
  const [failureLines, setFailureLines] = useState<string[]>([]);
  const [refresh, setRefresh] = useState(0);
  const [cancelling, setCancelling] = useState(false);
  const { toast } = useToast();
  const status = job?.status;

  // Failures are fetched eagerly so the tab label can show a count; refetched
  // on each status change and on manual refresh.
  useEffect(() => {
    if (jobId === null || status === undefined) return;
    let stale = false;
    api
      .getJobErrors(jobId)
      .then((r) => {
        if (!stale) setFailureLines(r.lines);
      })
      .catch((err: unknown) => {
        if (!stale) toast(errorMessage(err));
      });
    return () => {
      stale = true;
    };
  }, [jobId, status, refresh, toast]);

  // The activity log is only fetched while its tab is open.
  useEffect(() => {
    if (jobId === null || tab !== "log" || status === undefined) return;
    let stale = false;
    api
      .getJobLog(jobId)
      .then((r) => {
        if (!stale) setLogLines(r.lines);
      })
      .catch((err: unknown) => {
        if (!stale) toast(errorMessage(err));
      });
    return () => {
      stale = true;
    };
  }, [jobId, tab, status, refresh, toast]);

  const handleCancel = async () => {
    if (jobId === null) return;
    setCancelling(true);
    try {
      await api.cancelJob(jobId);
      toast("Cancellation requested.", "info");
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setCancelling(false);
    }
  };

  if (jobId === null) {
    return (
      <Page>
        <p className="rounded-xl border border-mauve-700/60 px-4 py-8 text-center text-sm text-thistle-400">
          That job doesn't exist.{" "}
          <RouterLink to="/" className="text-thistle-200 underline underline-offset-2">
            Back to Home
          </RouterLink>
        </p>
      </Page>
    );
  }

  const processed = job ? job.downloaded + job.skipped + job.failed : 0;
  const percent = job && job.total > 0 ? Math.round((processed / job.total) * 100) : 0;
  const segmentWidth = (count: number) =>
    job && job.total > 0 ? `${(count / job.total) * 100}%` : "0%";

  const stats = job
    ? [
        { label: "Total", value: job.total, className: "text-thistle-100" },
        { label: "Downloaded", value: job.downloaded, className: "text-thistle-100" },
        { label: "Skipped", value: job.skipped, className: "text-thistle-300" },
        {
          label: "Failed",
          value: job.failed,
          className: job.failed > 0 ? "text-mahogany-300" : "text-thistle-100",
        },
      ]
    : [];

  return (
    <Page>
      {/* Header */}
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <RouterLink
          to="/"
          aria-label="Back to Home"
          className="rounded-lg p-1.5 text-thistle-400 transition-colors hover:bg-mauve-800/50 hover:text-thistle-100"
        >
          <ArrowLeft className="h-5 w-5" aria-hidden="true" />
        </RouterLink>
        <h1 className="text-2xl font-semibold text-thistle-100">Job #{jobId}</h1>
        {job && <StatusBadge status={job.status} />}
        {job && isJobActive(job.status) && (
          <span className="flex items-center gap-1.5 text-xs text-thistle-500">
            <span
              aria-hidden="true"
              className={`h-1.5 w-1.5 rounded-full ${
                connection === "live" ? "bg-thistle-300" : "bg-rose-400"
              } ${connection === "connecting" ? "animate-pulse" : ""}`}
            />
            {connection === "live"
              ? "Live"
              : connection === "polling"
                ? "Auto-refresh"
                : "Connecting…"}
          </span>
        )}
        <span className="flex-1" />
        {job && isJobActive(job.status) && (
          <button
            type="button"
            onClick={() => void handleCancel()}
            disabled={cancelling}
            className="inline-flex items-center gap-1.5 rounded-lg border border-mahogany-400/60 bg-mahogany-700/40 px-3.5 py-1.5 text-sm font-medium text-mahogany-300 transition-colors hover:bg-mahogany-600/50 hover:text-thistle-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <XCircle className="h-4 w-4" aria-hidden="true" />
            {cancelling ? "Cancelling…" : "Cancel job"}
          </button>
        )}
      </div>

      {job && (
        <p className="mb-6 pl-11 text-xs text-thistle-500">
          Created {timeAgo(job.created_at)}
          {job.cookie_used ? ` · cookie: ${job.cookie_used}` : ""}
        </p>
      )}

      {!job && (
        <div className="flex justify-center py-16">
          <Loader2 className="h-7 w-7 animate-spin text-thistle-500" aria-label="Loading job" />
        </div>
      )}

      {job?.error && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-mahogany-400/60 bg-mahogany-800/50 px-4 py-3.5">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-mahogany-300" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-thistle-100">This job hit a problem</p>
            <p className="mt-0.5 text-sm text-thistle-300">{job.error}</p>
          </div>
        </div>
      )}

      {/* Progress */}
      {job && (
        <div className="mb-6 rounded-xl border border-mauve-800/60 bg-carbon-700/40 p-5">
          <div className="mb-3 flex items-center justify-between text-sm">
            <span className="text-thistle-300">
              {processed} of {job.total} processed
            </span>
            <span className="text-thistle-500">{percent}%</span>
          </div>
          {job.status === "running" && job.total === 0 ? (
            <div className="h-2.5 w-full animate-pulse rounded-full bg-mauve-500" />
          ) : (
            <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-carbon-600">
              <div
                className="bg-rose-400 transition-all duration-500"
                style={{ width: segmentWidth(job.downloaded) }}
              />
              <div
                className="bg-mauve-400 transition-all duration-500"
                style={{ width: segmentWidth(job.skipped) }}
              />
              <div
                className="bg-mahogany-400 transition-all duration-500"
                style={{ width: segmentWidth(job.failed) }}
              />
            </div>
          )}
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-lg border border-mauve-800/50 bg-carbon-800/70 px-3 py-2.5"
              >
                <p className="text-xs text-thistle-500">{stat.label}</p>
                <p className={`mt-0.5 text-xl font-semibold ${stat.className}`}>{stat.value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      {job && (
        <>
          <div className="mb-4 flex items-center gap-1 border-b border-mauve-800/60">
            {(["links", "log", "failures"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${
                  tab === t ? "text-thistle-100" : "text-thistle-500 hover:text-thistle-300"
                }`}
              >
                {t === "links"
                  ? `Links (${links.length})`
                  : t === "log"
                    ? "Activity log"
                    : `Failures (${failureLines.length})`}
                {tab === t && (
                  <motion.span
                    layoutId="job-tab-underline"
                    className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-rose-400"
                  />
                )}
              </button>
            ))}
            {tab !== "links" && (
              <button
                type="button"
                aria-label="Refresh log data"
                onClick={() => setRefresh((n) => n + 1)}
                className="ml-auto rounded-lg p-2 text-thistle-500 transition-colors hover:bg-mauve-800/50 hover:text-thistle-200"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </div>

          {tab === "links" && (
            <ul className="divide-y divide-mauve-800/60 rounded-xl border border-mauve-800/60 bg-carbon-700/40">
              {links.map((link) => (
                <li
                  key={link.id}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3"
                >
                  <span className="font-mono text-sm text-thistle-200">{link.shortcode}</span>
                  {link.username && (
                    <span className="text-sm text-thistle-400">@{link.username}</span>
                  )}
                  <span className="ml-auto flex items-center gap-3">
                    {link.media_count > 0 && (
                      <span className="text-xs text-thistle-500">
                        {link.media_count} {link.media_count === 1 ? "item" : "items"}
                      </span>
                    )}
                    <StatusBadge status={link.status} />
                  </span>
                  {link.error && (
                    <p className="w-full text-xs text-mahogany-300">{link.error}</p>
                  )}
                </li>
              ))}
              {links.length === 0 && (
                <li className="px-4 py-6 text-sm text-thistle-500">No links yet.</li>
              )}
            </ul>
          )}

          {tab === "log" && (
            <div className="rounded-xl border border-mauve-800/60 bg-carbon-900/70 p-4">
              <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-thistle-400">
                {logLines.length > 0 ? logLines.join("\n") : "No activity yet."}
              </pre>
            </div>
          )}

          {tab === "failures" && (
            <div className="rounded-xl border border-mahogany-500/40 bg-carbon-900/70 p-4">
              <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-mahogany-300">
                {failureLines.length > 0
                  ? failureLines.join("\n")
                  : "No failures — nice and clean."}
              </pre>
            </div>
          )}
        </>
      )}
    </Page>
  );
}
