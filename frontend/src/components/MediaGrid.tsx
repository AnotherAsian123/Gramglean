import { Play } from "lucide-react";
import { api } from "../lib/api";
import type { Media } from "../lib/api";

interface MediaGridProps {
  items: Media[];
  onSelect: (index: number) => void;
}

export default function MediaGrid({ items, onSelect }: MediaGridProps) {
  return (
    <div className="columns-2 gap-3 sm:columns-3 lg:columns-4 xl:columns-5">
      {items.map((media, index) => {
        const label = media.caption
          ? media.caption.slice(0, 80)
          : `Post by ${media.username ?? "unknown"}`;
        return (
          <button
            key={media.id}
            type="button"
            onClick={() => onSelect(index)}
            className="group relative mb-3 block w-full break-inside-avoid overflow-hidden rounded-xl border border-mauve-800/70 bg-carbon-700 transition-colors hover:border-rose-500/60"
          >
            {media.media_type === "video" ? (
              <span className="relative block">
                <video
                  src={api.mediaFileUrl(media.id)}
                  muted
                  playsInline
                  preload="metadata"
                  tabIndex={-1}
                  aria-hidden="true"
                  className="aspect-square w-full object-cover"
                />
                <span className="absolute inset-0 flex items-center justify-center bg-carbon-950/25 transition-colors group-hover:bg-carbon-950/10">
                  <Play className="h-8 w-8 text-thistle-100 drop-shadow-lg" aria-hidden="true" />
                </span>
                <span className="sr-only">{`Video: ${label}`}</span>
              </span>
            ) : (
              <img
                src={api.mediaFileUrl(media.id)}
                alt={label}
                loading="lazy"
                className="w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
