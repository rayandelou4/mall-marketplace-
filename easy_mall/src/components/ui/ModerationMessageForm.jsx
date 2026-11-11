import React, { useState } from "react";
import { Trash2 } from "lucide-react";
import { uploadToCloudinary } from "../../lib/cloudinary";
import { cx } from "../../styles/theme";

export function ModerationMessageForm({
  t,
  reasons,
  defaultReason,
  submitLabel,
  onSubmit,
  onCancel,
  loading = false,
  allowImages = false,
  showReason = true,
  placeholder = "Décrivez le problème rencontré…",
}) {
  const [reason, setReason] = useState(defaultReason || reasons[0]?.[0] || "other");
  const [description, setDescription] = useState("");
  const [sending, setSending] = useState(false);
  const [evidenceUrls, setEvidenceUrls] = useState([]);
  const [uploadingImages, setUploadingImages] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setSending(true);
    try {
      await onSubmit({ reason, description, evidence_urls: evidenceUrls });
    } finally {
      setSending(false);
    }
  }

  async function handleEvidenceSelection(fileList) {
    const files = Array.from(fileList || []);
    if (files.length + evidenceUrls.length > 5) {
      setUploadError("Vous pouvez joindre jusqu’à cinq photos.");
      return;
    }
    setUploadingImages(true);
    setUploadError(null);
    for (const file of files) {
      if (!file.type.startsWith("image/")) {
        setUploadError("Seules les images sont acceptées.");
        continue;
      }
      try {
        const url = await uploadToCloudinary(file);
        setEvidenceUrls((current) => [...current, url]);
      } catch (error) {
        setUploadError(error.message || "L’envoi d’une preuve a échoué.");
      }
    }
    setUploadingImages(false);
  }

  const disabled = loading || sending || uploadingImages;

  return (
    <form onSubmit={handleSubmit} className={cx("mt-3 flex flex-col gap-3 rounded-xl border p-4", t.border, t.cardBg)}>
      {showReason && (
        <label className="block">
          <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Catégorie du problème</span>
          <select value={reason} onChange={(event) => setReason(event.target.value)} required className={cx("w-full rounded-xl border px-3 py-2.5 text-sm", t.inputBg, t.border, t.textPrimary)}>
            {reasons.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      )}
      <label className="block">
        <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Message</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder={placeholder}
          rows={4}
          required
          className={cx("w-full rounded-xl border px-3 py-2.5 text-sm outline-none focus:border-indigo-500", t.inputBg, t.border, t.textPrimary)}
        />
      </label>
      {allowImages && (
        <div>
          <label className="block">
            <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Preuves photographiques (5 maximum)</span>
            <input
              type="file"
              accept="image/*"
              multiple
              disabled={disabled || evidenceUrls.length >= 5}
              onChange={(event) => {
                handleEvidenceSelection(event.target.files);
                event.target.value = "";
              }}
              className={cx("w-full rounded-lg border px-3 py-2 text-sm", t.border, t.textPrimary)}
            />
          </label>
          {uploadError && <p className="mt-1 text-xs text-rose-600" role="alert">{uploadError}</p>}
          {evidenceUrls.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {evidenceUrls.map((url, index) => (
                <div key={url} className="relative h-16 w-16 overflow-hidden rounded-lg">
                  <img src={url} alt={`Preuve ${index + 1}`} className="h-full w-full object-cover" />
                  <button type="button" onClick={() => setEvidenceUrls((current) => current.filter((item) => item !== url))} aria-label={`Retirer la preuve ${index + 1}`} className="absolute right-0 top-0 rounded-bl bg-white p-1 text-rose-600">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="flex gap-2">
        <button type="submit" disabled={disabled} className="rounded-full bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
          {uploadingImages ? "Envoi des preuves…" : disabled ? "Envoi…" : submitLabel}
        </button>
        <button type="button" onClick={onCancel} disabled={disabled} className={cx("rounded-full border px-4 py-2 text-sm font-semibold disabled:opacity-60", t.border, t.textMuted)}>
          Annuler
        </button>
      </div>
    </form>
  );
}