import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Account, type Media } from "../lib/api";
import MediaGrid from "../components/MediaGrid";
import Lightbox from "../components/Lightbox";

const PAGE = 60;

const FILTERS: { key: string; label: string; source?: string; media_type?: string }[] = [
  { key: "all", label: "All" },
  { key: "post", label: "Posts", source: "post" },
  { key: "carousel", label: "Carousels", source: "carousel" },
  { key: "reel", label: "Reels", source: "reel" },
  { key: "story", label: "Stories", source: "story" },
  { key: "video", label: "Videos", media_type: "video" },
];

export default function Gallery() {
  const [params, setParams] = useSearchParams();
  const accountId = params.get("account") ? Number(params.get("account")) : undefined;
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [filter, setFilter] = useState("all");
  const [items, setItems] = useState<Media[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [lightbox, setLightbox] = useState<number | null>(null);

  useEffect(() => {
    api.listAccounts().then(setAccounts);
  }, []);

  const load = useCallback(
    async (reset: boolean) => {
      setLoading(true);
      const f = FILTERS.find((x) => x.key === filter)!;
      const offset = reset ? 0 : items.length;
      try {
        const res = await api.listMedia({
          account_id: accountId,
          source: f.source,
          media_type: f.media_type,
          limit: PAGE,
          offset,
        });
        setTotal(res.total);
        setItems((prev) => (reset ? res.items : [...prev, ...res.items]));
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [accountId, filter]
  );

  useEffect(() => {
    load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, filter]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-extrabold">Gallery</h1>
        <select
          className="input w-auto"
          value={accountId ?? ""}
          onChange={(e) => {
            const v = e.target.value;
            if (v) setParams({ account: v });
            else setParams({});
          }}
        >
          <option value="">All accounts</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              @{a.username} ({a.media_count ?? 0})
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={filter === f.key ? "chip-on" : "chip-off"}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {items.length === 0 && !loading ? (
        <div className="card grid place-items-center p-16 text-center text-neutral-500">
          Nothing here yet. Run a scrape from the dashboard.
        </div>
      ) : (
        <>
          <MediaGrid items={items} onOpen={setLightbox} />
          {loading && (
            <div className="grid grid-cols-3 gap-1 sm:gap-2 md:grid-cols-4 lg:grid-cols-5">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="aspect-square skeleton rounded-lg" />
              ))}
            </div>
          )}
          {items.length < total && !loading && (
            <div className="flex justify-center pt-2">
              <button className="btn-ghost" onClick={() => load(false)}>
                Load more ({items.length}/{total})
              </button>
            </div>
          )}
        </>
      )}

      <Lightbox
        items={items}
        index={lightbox}
        onClose={() => setLightbox(null)}
        onNavigate={setLightbox}
      />
    </div>
  );
}
