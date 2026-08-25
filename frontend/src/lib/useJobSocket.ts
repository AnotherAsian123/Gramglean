import { useEffect, useState } from "react";
import { api, isJobActive } from "./api";
import type { Job, Link, LinkStatus } from "./api";

export type ConnectionState = "connecting" | "live" | "polling" | "closed";

interface LinkUpdate {
  id: number;
  url: string;
  shortcode: string;
  status: LinkStatus;
  username: string | null;
  media_count: number;
  error: string | null;
}

type WsEvent =
  | { type: "snapshot"; job: Job; links: Link[] }
  | { type: "link"; link: LinkUpdate }
  | {
      type: "progress";
      status: Job["status"];
      total: number;
      downloaded: number;
      skipped: number;
      failed: number;
    }
  | {
      type: "done";
      status: Job["status"];
      total: number;
      downloaded: number;
      skipped: number;
      failed: number;
      error: string | null;
    };

const MAX_RETRIES = 5;
const RETRY_DELAY_MS = 2000;
const POLL_INTERVAL_MS = 3000;

/**
 * Live job state over WebSocket, with automatic reconnect (up to 5 tries,
 * 2s apart) and a polling fallback (every 3s) when the socket is unavailable.
 */
export function useJobSocket(jobId: number | null) {
  const [job, setJob] = useState<Job | null>(null);
  const [links, setLinks] = useState<Link[]>([]);
  const [connection, setConnection] = useState<ConnectionState>("connecting");

  useEffect(() => {
    if (jobId === null) return;

    let disposed = false;
    let finished = false;
    let retries = 0;
    let ws: WebSocket | null = null;
    let retryTimer: number | undefined;
    let pollTimer: number | undefined;

    setJob(null);
    setLinks([]);
    setConnection("connecting");

    const finish = () => {
      finished = true;
      setConnection("closed");
    };

    const handleEvent = (msg: WsEvent) => {
      switch (msg.type) {
        case "snapshot":
          setJob(msg.job);
          setLinks(msg.links);
          if (!isJobActive(msg.job.status)) finish();
          break;
        case "link":
          setLinks((prev) =>
            prev.map((l) => (l.id === msg.link.id ? { ...l, ...msg.link } : l)),
          );
          break;
        case "progress":
          setJob((prev) =>
            prev
              ? {
                  ...prev,
                  status: msg.status,
                  total: msg.total,
                  downloaded: msg.downloaded,
                  skipped: msg.skipped,
                  failed: msg.failed,
                }
              : prev,
          );
          break;
        case "done":
          setJob((prev) =>
            prev
              ? {
                  ...prev,
                  status: msg.status,
                  total: msg.total,
                  downloaded: msg.downloaded,
                  skipped: msg.skipped,
                  failed: msg.failed,
                  error: msg.error,
                }
              : prev,
          );
          finish();
          break;
      }
    };

    const startPolling = () => {
      if (disposed || finished) return;
      setConnection("polling");
      const poll = async () => {
        try {
          const detail = await api.getJob(jobId);
          if (disposed) return;
          setJob(detail.job);
          setLinks(detail.links);
          if (!isJobActive(detail.job.status)) {
            finish();
            return;
          }
        } catch {
          // Server unreachable right now; the connection state shown in the
          // UI reflects this and we quietly keep trying.
        }
        if (!disposed && !finished) {
          pollTimer = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
        }
      };
      void poll();
    };

    const connect = () => {
      if (disposed || finished) return;
      let socket: WebSocket;
      try {
        const proto = window.location.protocol === "https:" ? "wss" : "ws";
        socket = new WebSocket(`${proto}://${window.location.host}/ws/jobs/${jobId}`);
      } catch {
        startPolling();
        return;
      }
      ws = socket;
      socket.onopen = () => {
        if (!disposed && !finished) {
          retries = 0;
          setConnection("live");
        }
      };
      socket.onmessage = (event: MessageEvent) => {
        if (disposed) return;
        try {
          handleEvent(JSON.parse(String(event.data)) as WsEvent);
        } catch {
          // Malformed frame; ignore it.
        }
      };
      socket.onclose = () => {
        if (disposed || finished) return;
        if (retries < MAX_RETRIES) {
          retries += 1;
          setConnection("connecting");
          retryTimer = window.setTimeout(connect, RETRY_DELAY_MS);
        } else {
          startPolling();
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      if (pollTimer !== undefined) window.clearTimeout(pollTimer);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [jobId]);

  return { job, links, connection };
}
