import { useEffect, useRef, useState } from "react";
import type { JobStatus } from "./api";

export interface JobProgress {
  status: JobStatus;
  total: number;
  downloaded: number;
  skipped: number;
  failed: number;
  error?: string | null;
}

export interface LogLine {
  level: string;
  message: string;
  ts: number;
}

const TERMINAL: JobStatus[] = ["completed", "failed", "cancelled", "rate_limited"];

/** Subscribes to /ws/jobs/{id} and tracks live progress + a rolling log. */
export function useJobSocket(jobId: number | null) {
  const [progress, setProgress] = useState<JobProgress | null>(null);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (jobId == null) return;
    setProgress(null);
    setLogs([]);

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/jobs/${jobId}`);
    socketRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.type === "log") {
        setLogs((prev) =>
          [...prev, { level: data.level, message: data.message, ts: Date.now() }].slice(-300)
        );
        return;
      }
      // snapshot | progress | done all carry counters.
      setProgress({
        status: data.status,
        total: data.total ?? 0,
        downloaded: data.downloaded ?? 0,
        skipped: data.skipped ?? 0,
        failed: data.failed ?? 0,
        error: data.error,
      });
      if (data.type === "done" || TERMINAL.includes(data.status)) {
        // Let the server close; keep last state.
      }
    };

    return () => {
      ws.close();
      socketRef.current = null;
    };
  }, [jobId]);

  return { progress, logs, connected };
}
