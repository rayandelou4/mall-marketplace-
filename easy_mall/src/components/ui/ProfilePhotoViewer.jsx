import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Expand, X } from "lucide-react";
import { cx } from "../../styles/theme";

export function ProfilePhotoViewer({
  src,
  alt,
  title = "Photo de profil",
  className,
  children,
  showTriggerOverlay = false,
  label = "Voir la photo en grand",
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function closeOnEscape(event) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  if (!src) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cx("inline-flex items-center justify-center", showTriggerOverlay && "group relative transition-transform duration-200 hover:scale-[1.03]", className)}
        aria-label={label}
        title={label}
      >
        {children || <><Expand className="h-3.5 w-3.5" /> <span>{label}</span></>}
        {showTriggerOverlay && (
          <span className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-[inherit] bg-black/0 text-white transition-colors group-hover:bg-black/35 group-focus-visible:bg-black/40">
            <Expand className="h-5 w-5 opacity-0 drop-shadow transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
          </span>
        )}
      </button>
      {open && createPortal(
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-zinc-950/75 p-3 backdrop-blur-md sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="profile-photo-viewer-title"
        >
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="absolute inset-0 h-full w-full cursor-default"
            aria-label="Fermer l’aperçu de la photo"
          />
          <div className="relative z-10 flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-white/15 bg-zinc-900 shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center justify-between gap-4 border-b border-white/10 px-4 py-3 sm:px-5">
              <div className="min-w-0">
                <h2 id="profile-photo-viewer-title" className="truncate text-sm font-semibold text-white">{title}</h2>
                <p className="mt-0.5 text-xs text-zinc-400">Aperçu de la photo de profil</p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/15 text-zinc-300 transition hover:border-white/30 hover:bg-white/10 hover:text-white"
                aria-label="Fermer l’aperçu de la photo"
                autoFocus
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex min-h-0 flex-1 items-center justify-center bg-zinc-950 p-3 sm:p-6">
              <img
                src={src}
                alt={alt || "Photo de profil agrandie"}
                className="max-h-[calc(94vh-7rem)] max-w-full rounded-lg object-contain shadow-xl"
              />
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
