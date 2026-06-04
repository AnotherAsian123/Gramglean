import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, Ban, FileWarning, ScrollText, Images } from "lucide-react";
import { api, type Job } from "../lib/api";
import { useJobSocket } from "../lib/useJobSocket";
import StatusBadge from "../components/StatusBadge";
import { timeAgo } from "../lib/format";

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="card p-4 text-center">
      <div className={`text-2xl font-extrabold ${color}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-widest text-neutral-500">{label}</div>
    </div>
  );
}

export default function JobView() {
  const { id } = useParams();
  const jobId = id ? Number(id) : null;
  const [job, setJob] = useState<Job | null>(null);
  const { progress, logs } = useJobSocket(jobId);
  const [tab, setTab] = useState<"activity" | "errors">("activity");
  const [errorLines, setErrorLines] = useState<string[]>([]);

  useEffect(() => {
    if (jobId == null) return;
    api.getJob(jobId).then(setJob).catch(() => {});
  }, [jobId]);

  // Merge live progress over the fetched job snapshot.
  const view = useMemo(() => {
    if (!job) return null;
    return progress ? { ...job, ...progress } : job;
  }, [job, progress]);

  useEffect(() => {
    if (jobId == null) return;
    if (tab === "errors") {
      api.getJobErrors(jobId).then((r) => setErrorLines(r.lines)).catch(() => {});
    }
  }, [tab, jobId, view?.failed, view?.status]);

  if (!view) {
    return <div className="h-40 skeleton rounded-2xl" />;
  }

  const active = view.status === "running" || view.status === "queued";
  const pct =
    view.total > 0 ? Math.round(((view.downloaded + view.failed) / view.total) * 100) : 0;

  async function cancel() {
    if (jobId == null) return;
    await api.cancelJob(jobId).catch(() => {});
  }

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-neutral-400 hover:text-neutral-200">
        <ArrowLeft className="h-4 w-4" /> Dashboard
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">@{view.username}</h1>
          <p className="text-xs text-neutral-500">
            started {timeAgo(view.started_at ?? view.created_at)}
            {view.cookie_used && ` · cookie: ${view.cookie_used}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={view.status} />
          {active && (
            <button className="btn-ghost text-red-400" onClick={cancel}>
              <Ban className="h-4 w-4" /> Cancel
            </button>
          )}
          {!active && (
            <Link to={`/gallery?account=${view.account_id}`} className="btn-primary">
              <Images className="h-4 w-4" /> View gallery
            </Link>
          )}
        </div>
      </div>

      {/* Progress */}
      <div className="card p-5">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-semibold">
            {view.total === 0 && active
              ? "Enumerating account…"
              : `${view.downloaded + view.failed} / ${view.total}`}
          </span>
          <span className="text-neutral-400">{view.total > 0 ? `${pct}%` : ""}</span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-ink-800">
          {view.total === 0 && active ? (
            <div className="ig-gradient h-full w-1/3 animate-pulse rounded-full" />
          ) : (
            <motion.div
              className="ig-gradient h-full rounded-full"
              animate={{ width: `${pct}%` }}
              transition={{ ease: "easeOut", duration: 0.4 }}
            />
          )}
        </div>
        <div className="mt-4 grid grid-cols-4 gap-3">
          <Stat label="Downloaded" value={view.downloaded} color="text-emerald-400" />
          <Stat label="Skipped" value={view.skipped} color="text-neutral-300" />
          <Stat label="Failed" value={view.failed} color="text-red-400" />
          <Stat label="Total" value={view.total} color="text-ig-pink" />
        </div>
        {view.error && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <FileWarning className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{view.error}</span>
          </div>
        )}
      </div>

      {/* Logs */}
      <div className="card overflow-hidden">
        <div className="flex border-b border-ink-700 text-sm">
          <button
            className={`flex items-center gap-2 px-4 py-3 font-semibold ${
              tab === "activity" ? "text-ig-pink" : "text-neutral-400"
            }`}
            onClick={() => setTab("activity")}
          >
            <ScrollText className="h-4 w-4" /> Activity
          </button>
          <button
            className={`flex items-center gap-2 px-4 py-3 font-semibold ${
              tab === "errors" ? "text-ig-pink" : "text-neutral-400"
            }`}
            onClick={() => setTab("errors")}
          >
            <FileWarning className="h-4 w-4" /> Failures ({view.failed})
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto bg-ink-950/60 p-4 font-mono text-xs leading-relaxed">
          {tab === "activity" ? (
            logs.length === 0 ? (
              <p className="text-neutral-600">Waiting for activity…</p>
            ) : (
              logs.map((l, i) => (
                <div key={i} className="text-neutral-300">
                  <span className="text-neutral-600">·</span> {l.message}
                </div>
              ))
            )
          ) : errorLines.length === 0 ? (
            <p className="text-neutral-600">No failures recorded for this job.</p>
          ) : (
            errorLines.map((line, i) => (
              <div key={i} className="whitespace-pre-wrap break-all text-red-300/90">
                {line}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
