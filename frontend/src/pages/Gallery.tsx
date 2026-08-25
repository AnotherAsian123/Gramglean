import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { Loader2 } from "lucide-react";
import { api, errorMessage } from "../lib/api";
import type { Media, UsernameCount } from "../lib/api";
import { Page } from "../components/Layout";
import MediaGrid from "../components/MediaGrid";
import Lightbox from "../components/Lightbox";
import { useToast } from "../components/Toast";

type MediaTypeFilter = "" | "image" | "video";

const PAGE_SIZE = 60;

const TYPE_FILTERS: ReadonlyArray<{ value: MediaTypeFilter; label: string }> = [
  { value: "", label: "All" },
  { value: "image", label: "Images" },
  { value: "video", label: "Videos" },
];

export default function Gallery() {
  const [items, setItems] = useState<Media[]>([]);
  const [total, setTotal] = useState(0);
  const [usernames, setUsernames] = useState<UsernameCount[]>([]);
  const [username, setUsername] = useState("");
  const [mediaType, setMediaType] = useState<MediaTypeFilter>("");
  const [loading, setLoading] = useState(true);
  const [lightbox, setLightbox] = useState<number | null>(null);
  const { toast } = useToast();

  // The offset for "Load more" is derived from a ref kept in sync with the
  // items state, so the callback never sees a stale item count.
  const itemsRef = useRef<Media[]>([]);
  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  const requestRef = useRef(0);
  const loadingRef = useRef(false);

  const fetchPage = useCallback(
    async (reset: boolean) => {
      if (!reset && loadingRef.current) return;
      const requestId = ++requestRef.current;
      loadingRef.current = true;
      setLoading(true);
      try {
        const offset = reset ? 0 : itemsRef.current.length;
        const page = await api.listMedia({
          username: username || undefined,
          media_type: mediaType === "" ? undefined : mediaType,
          offset,
          limit: PAGE_SIZE,
        });
        if (requestId !== requestRef.current) return; // superseded by a newer request
        setTotal(page.total);
        setItems((prev) => (reset ? page.items : [...prev, ...page.items]));
      } catch (err) {
        if (requestId === requestRef.current) toast(errorMessage(err));
      } finally {
        if (requestId === requestRef.current) {
          loadingRef.current = false;
          setLoading(false);
        }
      }
    },
    [username, mediaType, toast],
  );

  // Refetch from the start whenever a filter changes (fetchPage identity
  // changes with the filters).
  useEffect(() => {
    setLightbox(null);
    void fetchPage(true);
  }, [fetchPage]);

  useEffect(() => {
    let stale = false;
    api
      .listUsernames()
      .then((u) => {
        if (!stale) setUsernames(u);
      })
      .catch((err: unknown) => {
        if (!stale) toast(errorMessage(err));
      });
    return () => {
      stale = true;
    };
  }, [toast]);

  return (
    <Page>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold text-thistle-100">Gallery</h1>
        <span className="text-sm text-thistle-500">
          {total} {total === 1 ? "item" : "items"}
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <label htmlFor="username-filter" className="sr-only">
            Filter by account
          </label>
          <select
            id="username-filter"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="rounded-lg border border-mauve-500/60 bg-carbon-700 px-3 py-1.5 text-sm text-thistle-200"
          >
            <option value="">All accounts</option>
            {usernames.map((u) => (
              <option key={u.username} value={u.username}>
                @{u.username} ({u.count})
              </option>
            ))}
          </select>
          <div
            role="group"
            aria-label="Media type"
            className="flex overflow-hidden rounded-lg border border-mauve-500/60"
          >
            {TYPE_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => setMediaType(filter.value)}
                aria-pressed={mediaType === filter.value}
                className={`px-3 py-1.5 text-sm transition-colors ${
                  mediaType === filter.value
                    ? "bg-rose-600/50 text-thistle-100"
                    : "bg-carbon-700 text-thistle-400 hover:text-thistle-200"
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {items.length === 0 && !loading ? (
        <p className="rounded-xl border border-dashed border-mauve-700/60 px-4 py-16 text-center text-sm text-thistle-500">
          Nothing here yet — download some posts and they'll show up in your gallery.
        </p>
      ) : (
        <MediaGrid items={items} onSelect={(i) => setLightbox(i)} />
      )}

      <div className="mt-6 flex justify-center">
        {loading ? (
          <Loader2 className="h-6 w-6 animate-spin text-thistle-500" aria-label="Loading media" />
        ) : items.length < total ? (
          <button
            type="button"
            onClick={() => void fetchPage(false)}
            className="rounded-xl border border-mauve-500/60 bg-carbon-700/70 px-6 py-2.5 text-sm font-medium text-thistle-200 transition-colors hover:border-rose-500/60 hover:text-thistle-100"
          >
            Load more ({total - items.length} remaining)
          </button>
        ) : null}
      </div>

      <AnimatePresence>
        {lightbox !== null && lightbox < items.length && (
          <Lightbox
            items={items}
            index={lightbox}
            onClose={() => setLightbox(null)}
            onNavigate={setLightbox}
          />
        )}
      </AnimatePresence>
    </Page>
  );
}
