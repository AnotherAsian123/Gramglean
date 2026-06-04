import { motion } from "framer-motion";
import { Play, Layers, Film, Clock } from "lucide-react";
import type { Media } from "../lib/api";
import { api } from "../lib/api";

const sourceIcon = {
  post: null,
  carousel: Layers,
  reel: Film,
  story: Clock,
} as const;

export default function MediaGrid({
  items,
  onOpen,
}: {
  items: Media[];
  onOpen: (index: number) => void;
}) {
  return (
    <div className="grid grid-cols-3 gap-1 sm:gap-2 md:grid-cols-4 lg:grid-cols-5">
      {items.map((m, i) => {
        const Badge = sourceIcon[m.source];
        const isVideo = m.media_type === "video";
        return (
          <motion.button
            key={m.id}
            layout
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2, delay: Math.min(i, 12) * 0.015 }}
            onClick={() => onOpen(i)}
            className="group relative aspect-square overflow-hidden rounded-lg bg-ink-800"
          >
            {isVideo ? (
              <>
                <video
                  src={api.mediaFileUrl(m.id) + "#t=0.1"}
                  preload="metadata"
                  muted
                  className="h-full w-full object-cover"
                />
                <div className="absolute inset-0 grid place-items-center bg-black/20">
                  <Play className="h-9 w-9 text-white drop-shadow" fill="white" />
                </div>
              </>
            ) : (
              <img
                src={api.mediaFileUrl(m.id)}
                loading="lazy"
                alt={m.shortcode}
                className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
              />
            )}
            {Badge && (
              <div className="absolute right-1.5 top-1.5 rounded-md bg-black/55 p-1 backdrop-blur">
                <Badge className="h-3.5 w-3.5 text-white" />
              </div>
            )}
            <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-white/5 group-hover:ring-ig-pink/50" />
          </motion.button>
        );
      })}
    </div>
  );
}
