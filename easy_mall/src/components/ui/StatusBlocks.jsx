import React from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { cx } from "../../styles/theme";

export function SectionHeading({ eyebrow, title, subtitle, t }) {
  return (
    <div className="mb-6 flex flex-col gap-1">
      {eyebrow && <span className={cx("text-xs font-semibold uppercase tracking-wider", t.accentText)}>{eyebrow}</span>}
      <h2 className={cx("text-2xl sm:text-3xl font-semibold", t.textPrimary)}>{title}</h2>
      {subtitle && <p className={cx("text-sm", t.textMuted)}>{subtitle}</p>}
    </div>
  );
}

export function LoadingBlock({ t, label = "Chargement…" }) {
  return (
    <div className={cx("flex items-center justify-center gap-2 rounded-2xl border py-16 text-sm", t.cardBorder, t.textMuted)}>
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function ErrorBlock({ message, t, showApi = true }) {
  return (
    <div className="flex items-start gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p className="font-medium">Une erreur est survenue.</p>
        <p className="mt-0.5 text-rose-600">
          {message}{showApi && `une erreur`}
        </p>
      </div>
    </div>
  );
}
