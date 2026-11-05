import React, { useState } from "react";
import { cx } from "../../styles/theme";

export function ModerationMessageForm({
  t,
  reasons,
  defaultReason,
  submitLabel,
  onSubmit,
  onCancel,
  loading = false,
}) {
  const [reason, setReason] = useState(defaultReason || reasons[0]?.[0] || "other");
  const [description, setDescription] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setSending(true);
    try {
      await onSubmit({ reason, description });
    } finally {
      setSending(false);
    }
  }

  const disabled = loading || sending;

  return (
    <form onSubmit={handleSubmit} className={cx("mt-3 flex flex-col gap-3 rounded-xl border p-4", t.border, t.cardBg)}>
      <label className="block">
        <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Motif</span>
        <select value={reason} onChange={(event) => setReason(event.target.value)} required className={cx("w-full rounded-xl border px-3 py-2.5 text-sm", t.inputBg, t.border, t.textPrimary)}>
          {reasons.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <label className="block">
        <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Message</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Décrivez le problème rencontré…"
          rows={4}
          required
          className={cx("w-full rounded-xl border px-3 py-2.5 text-sm outline-none focus:border-indigo-500", t.inputBg, t.border, t.textPrimary)}
        />
      </label>
      <div className="flex gap-2">
        <button type="submit" disabled={disabled} className="rounded-full bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
          {disabled ? "Envoi…" : submitLabel}
        </button>
        <button type="button" onClick={onCancel} disabled={disabled} className={cx("rounded-full border px-4 py-2 text-sm font-semibold disabled:opacity-60", t.border, t.textMuted)}>
          Annuler
        </button>
      </div>
    </form>
  );
}