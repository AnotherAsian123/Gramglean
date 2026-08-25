import { useEffect } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Download, X } from "lucide-react";
import { api } from "../lib/api";
import type { Media } from "../lib/api";
import { baseName, formatDateTime } from "../lib/format";

interface LightboxProps {
  items: Media[];
  index: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
}

export default function Lightbox({ items, index, onClose, onNavigate }: LightboxProps) {
  const media = items[index];
  const canPrev = index > 0;
  const canNext = index < items.length - 1;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      else if (event.key === "ArrowLeft" && canPrev) onNavigate(index - 1);
      else if (event.key === "ArrowRight" && canNext) onNavigate(index + 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, canPrev, canNext, onClose, onNavigate]);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  const fileUrl = api.mediaFileUrl(media.id);
  const alt = media.caption
    ? media.caption.slice(0, 120)
    : `Post by ${media.username ?? "unknown"}`;

  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label="Media viewer"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      className="fixed inset-0 z-50 flex flex-col bg-carbon-950/95 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Top bar */}
      <div
        className="flex items-center justify-between gap-3 px-4 py-3"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="truncate text-sm text-thistle-300">
          {media.username ? `@${media.username}` : "Unknown account"}
          <span className="text-thistle-600">
            {" "}
            · {index + 1} / {items.length}
          </span>
        </span>
        <div className="flex items-center gap-2">
          <a
            href={fileUrl}
            download={baseName(media.file_path)}
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-mauve-500/60 bg-carbon-700/80 px-3 py-1.5 text-sm text-thistle-200 transition-colors hover:border-rose-400/70 hover:text-thistle-100"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            Save
          </a>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close viewer"
            className="rounded-lg p-2 text-thistle-300 transition-colors hover:bg-mauve-800/60 hover:text-thistle-100"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Media area */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden px-2 sm:px-16">
        {canPrev && (
          <button
            type="button"
            aria-label="Previous item"
            onClick={(e) => {
              e.stopPropagation();
              onNavigate(index - 1);
            }}
            className="absolute left-2 z-10 rounded-full bg-carbon-700/80 p-2 text-thistle-200 transition-colors hover:bg-mauve-700/80 sm:left-4"
          >
            <ChevronLeft className="h-6 w-6" aria-hidden="true" />
          </button>
        )}

        <motion.div
          key={media.id}
          initial={{ opacity: 0.3, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", stiffness: 320, damping: 30 }}
          drag="x"
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.25}
          onDragEnd={(_event, info) => {
            if (info.offset.x < -80 && canNext) onNavigate(index + 1);
            else if (info.offset.x > 80 && canPrev) onNavigate(index - 1);
          }}
          onClick={(e) => e.stopPropagation()}
          className="flex max-h-full max-w-full items-center justify-center"
        >
          {media.media_type === "video" ? (
            <video src={fileUrl} controls playsInline className="max-h-[72vh] max-w-full rounded-lg" />
          ) : (
            <img
              src={fileUrl}
              alt={alt}
              draggable={false}
              className="max-h-[72vh] max-w-full rounded-lg object-contain"
            />
          )}
        </motion.div>

        {canNext && (
          <button
            type="button"
            aria-label="Next item"
            onClick={(e) => {
              e.stopPropagation();
              onNavigate(index + 1);
            }}
            className="absolute right-2 z-10 rounded-full bg-carbon-700/80 p-2 text-thistle-200 transition-colors hover:bg-mauve-700/80 sm:right-4"
          >
            <ChevronRight className="h-6 w-6" aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Caption footer */}
      <div className="px-4 pb-5 pt-3" onClick={(e) => e.stopPropagation()}>
        <div className="mx-auto max-w-2xl text-center">
          {media.caption && (
            <p className="mx-auto max-h-20 overflow-y-auto text-sm leading-relaxed text-thistle-300">
              {media.caption}
            </p>
          )}
          <p className="mt-1.5 text-xs text-thistle-600">
            {media.username ? `@${media.username} · ` : ""}
            {formatDateTime(media.taken_at ?? media.downloaded_at)}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
