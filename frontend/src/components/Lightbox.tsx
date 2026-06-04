import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, ChevronLeft, ChevronRight, Download, Calendar } from "lucide-react";
import type { Media } from "../lib/api";
import { api } from "../lib/api";

export default function Lightbox({
  items,
  index,
  onClose,
  onNavigate,
}: {
  items: Media[];
  index: number | null;
  onClose: () => void;
  onNavigate: (next: number) => void;
}) {
  const open = index !== null;
  const media = open ? items[index!] : null;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" && index! < items.length - 1) onNavigate(index! + 1);
      if (e.key === "ArrowLeft" && index! > 0) onNavigate(index! - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, index, items.length, onClose, onNavigate]);

  return (
    <AnimatePresence>
      {open && media && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm"
          onClick={onClose}
        >
          <button
            className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-6 w-6" />
          </button>

          {index! > 0 && (
            <button
              className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white hover:bg-white/20 md:left-6"
              onClick={(e) => {
                e.stopPropagation();
                onNavigate(index! - 1);
              }}
              aria-label="Previous"
            >
              <ChevronLeft className="h-7 w-7" />
            </button>
          )}
          {index! < items.length - 1 && (
            <button
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white hover:bg-white/20 md:right-6"
              onClick={(e) => {
                e.stopPropagation();
                onNavigate(index! + 1);
              }}
              aria-label="Next"
            >
              <ChevronRight className="h-7 w-7" />
            </button>
          )}

          <motion.div
            key={media.id}
            initial={{ scale: 0.94, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.94, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="flex max-h-[90vh] w-full max-w-4xl flex-col items-center px-4"
            onClick={(e) => e.stopPropagation()}
          >
            {media.media_type === "video" ? (
              <video
                src={api.mediaFileUrl(media.id)}
                controls
                autoPlay
                className="max-h-[78vh] w-auto rounded-xl"
              />
            ) : (
              <img
                src={api.mediaFileUrl(media.id)}
                alt={media.shortcode}
                className="max-h-[78vh] w-auto rounded-xl object-contain"
              />
            )}

            <div className="mt-3 flex w-full items-center justify-between gap-3 text-sm text-neutral-300">
              <div className="flex items-center gap-2 truncate">
                <span className="rounded-md bg-white/10 px-2 py-0.5 text-xs uppercase tracking-wide">
                  {media.source}
                </span>
                {media.taken_at && (
                  <span className="flex items-center gap-1 text-neutral-400">
                    <Calendar className="h-3.5 w-3.5" />
                    {new Date(media.taken_at).toLocaleDateString()}
                  </span>
                )}
              </div>
              <a
                href={api.mediaFileUrl(media.id)}
                download
                className="flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-xs font-semibold hover:bg-white/20"
              >
                <Download className="h-4 w-4" /> Save
              </a>
            </div>
            {media.caption && (
              <p className="mt-2 max-h-24 w-full overflow-y-auto whitespace-pre-wrap text-sm text-neutral-400">
                {media.caption}
              </p>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
