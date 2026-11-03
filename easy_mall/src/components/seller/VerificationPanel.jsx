import { createElement, useEffect, useState } from "react";
import { BadgeCheck, Building2, Clock3, FileCheck2, ShieldCheck, Upload } from "lucide-react";
import { ErrorBlock, LoadingBlock } from "../ui/StatusBlocks";
import { cx } from "../../styles/theme";
import {
  createVerificationRequest,
  fetchVerificationLevels,
  fetchVerificationStatus,
  submitVerificationRequest,
  uploadVerificationDocument,
} from "../../features/seller/verificationApi";

const STATUS_LABELS = {
  draft: "Brouillon",
  pending: "En attente",
  under_review: "En cours d’examen",
  needs_more_info: "Informations à compléter",
  approved: "Approuvée",
  rejected: "Refusée",
  expired: "Expirée",
  cancelled: "Annulée",
};

const STATUS_STYLE = {
  draft: "bg-zinc-100 text-zinc-700",
  pending: "bg-amber-100 text-amber-800",
  under_review: "bg-sky-100 text-sky-800",
  needs_more_info: "bg-orange-100 text-orange-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-rose-100 text-rose-800",
  expired: "bg-zinc-100 text-zinc-600",
};

const LEVEL_DETAILS = [
  { level: "level_0", title: "Profil créé", icon: ShieldCheck, description: "Un compte actif existe. Ce niveau ne confirme ni l’identité ni la fiabilité." },
  { level: "level_1", title: "E-mail vérifié", icon: BadgeCheck, description: "L’adresse e-mail a été confirmée par le mécanisme de compte existant; ce n’est pas une preuve d’identité." },
  { level: "level_2", title: "Identité examinée", icon: FileCheck2, description: "Examen interne d’un justificatif par un réviseur autorisé. L’aspect du document ne garantit pas son authenticité." },
  { level: "level_3", title: "Commerçant vérifié", icon: Building2, description: "Examen des preuves d’activité fournies par un compte déclaré professionnel; cela ne prouve pas l’identité personnelle du propriétaire." },
  { level: "level_4", title: "Historique commercial", icon: BadgeCheck, description: "Calculé à partir des ventes livrées, des avis liés à ces ventes et des annulations résolues. Ce badge ne certifie pas l’identité." },
];

function certificationIsActive(certification) {
  return certification.is_active && (!certification.expires_at || new Date(certification.expires_at) > new Date());
}

export function VerificationPanel({ t, isProfessional }) {
  const [status, setStatus] = useState(null);
  const [criteria, setCriteria] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [targetLevel, setTargetLevel] = useState("level_2");
  const [documentType, setDocumentType] = useState("identity");
  const [files, setFiles] = useState([]);
  const [description, setDescription] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [currentStatus, levelData] = await Promise.all([
        fetchVerificationStatus(),
        fetchVerificationLevels(),
      ]);
      setStatus(currentStatus);
      setCriteria(levelData.levels || []);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    setDocumentType(targetLevel === "level_2" ? "identity" : "business_registration");
  }, [targetLevel]);

  const activeCertifications = (status?.certifications || []).filter(certificationIsActive);
  const pendingRequests = status?.pending_requests || [];
  const requestHistory = status?.requests || pendingRequests;
  const selectedRequest = pendingRequests.find((item) => item.target_level === targetLevel);
  const canEditRequest = selectedRequest && ["draft", "needs_more_info"].includes(selectedRequest.status);
  const requestIsOpen = selectedRequest && !["draft", "needs_more_info"].includes(selectedRequest.status);
  const historyCriteria = criteria.find((item) => item.level === "level_4");

  async function handleSubmit(event) {
    event.preventDefault();
    setNotice("");
    setError("");
    if (!files.length) {
      setError("Ajoutez au moins un justificatif pour envoyer cette demande.");
      return;
    }
    setBusy(true);
    try {
      const request = canEditRequest
        ? selectedRequest
        : await createVerificationRequest({
            verification_type: targetLevel === "level_2" ? "identity" : "business_registration",
            target_level: targetLevel,
            description,
          });

      for (const file of files) {
        const payload = new FormData();
        payload.append("document_type", documentType);
        payload.append("description", description);
        payload.append("file", file);
        await uploadVerificationDocument(request.id, payload);
      }
      await submitVerificationRequest(request.id);
      setFiles([]);
      setDescription("");
      setNotice("Votre demande a été envoyée pour examen manuel.");
      await load();
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock t={t} label="Chargement des vérifications…" />;
  if (!status) return <ErrorBlock message={error || "Statut indisponible."} t={t} />;

  const achieved = new Set([
    "level_0",
    ...(status.is_email_verified ? ["level_1"] : []),
    ...activeCertifications.map((certification) => certification.level),
    ...((status.eligible_levels || []).filter((item) => item.level === "level_4" && item.is_achieved).map((item) => item.level)),
  ]);

  return (
    <section className="space-y-6" aria-labelledby="verification-heading">
      <div>
        <h2 id="verification-heading" className={cx("text-xl font-semibold", t.textPrimary)}>Vérification de mon compte</h2>
        <p className={cx("mt-1 max-w-3xl text-sm", t.textMuted)}>
          Les niveaux sont indépendants. Une vérification d’identité ou d’activité est facultative; ne transmettez que les justificatifs correspondant au niveau dont vous avez besoin.
        </p>
      </div>

      <div className="divide-y rounded-xl border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900">
        {LEVEL_DETAILS.map(({ level, title, icon: Icon, description: detail }) => {
          const currentRequest = pendingRequests.find((item) => item.target_level === level);
          const isAchieved = achieved.has(level);
          return (
            <div key={level} className="flex gap-3 p-4 sm:items-center">
              {createElement(Icon, { className: cx("mt-0.5 h-5 w-5 shrink-0", isAchieved ? "text-emerald-600" : t.textMuted), "aria-hidden": true })}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className={cx("text-sm font-semibold", t.textPrimary)}>{title}</h3>
                  {isAchieved && <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">Actif</span>}
                  {currentRequest && <span className={cx("rounded px-2 py-0.5 text-xs font-medium", STATUS_STYLE[currentRequest.status] || STATUS_STYLE.draft)}>{STATUS_LABELS[currentRequest.status] || currentRequest.status}</span>}
                </div>
                <p className={cx("mt-1 text-sm", t.textMuted)}>{detail}</p>
                {level === "level_4" && historyCriteria && (
                  <p className={cx("mt-2 text-xs", t.textMuted)}>
                    Critères actuels : {historyCriteria.requires_transaction_count} commandes livrées, {historyCriteria.requires_account_age_days} jours d’ancienneté, note minimale {historyCriteria.requires_minimum_rating}, annulations au plus {historyCriteria.max_cancellation_rate} %.
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {requestHistory.length > 0 && (
        <div className="space-y-2">
          <h3 className={cx("text-sm font-semibold", t.textPrimary)}>Demandes</h3>
          {requestHistory.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center gap-2 border-b border-zinc-200 py-3 text-sm dark:border-zinc-700">
              <Clock3 className="h-4 w-4 text-zinc-500" />
              <span className={cx("font-medium", t.textPrimary)}>{item.target_level_display}</span>
              <span className={cx("rounded px-2 py-0.5 text-xs", STATUS_STYLE[item.status] || STATUS_STYLE.draft)}>{STATUS_LABELS[item.status] || item.status}</span>
              {item.rejection_reason && <p className="w-full text-rose-700">Motif : {item.rejection_reason}</p>}
              {item.seller_message && <p className="w-full text-amber-800">À compléter : {item.seller_message}</p>}
            </div>
          ))}
        </div>
      )}

      <div className="border-t border-zinc-200 pt-5 dark:border-zinc-700">
        <h3 className={cx("text-base font-semibold", t.textPrimary)}>Demander un examen manuel</h3>
        <p className={cx("mt-1 text-sm", t.textMuted)}>
          Les pièces sont privées, accessibles aux réviseurs autorisés uniquement et supprimées 90 jours après la décision finale. La plateforme ne les transmet à aucun fournisseur externe.
        </p>
        <form className="mt-4 grid max-w-2xl gap-3 sm:grid-cols-2" onSubmit={handleSubmit}>
          <label className={cx("grid gap-1 text-sm", t.textPrimary)}>
            Niveau demandé
            <select value={targetLevel} onChange={(event) => setTargetLevel(event.target.value)} className="rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-600 dark:bg-zinc-800">
              <option value="level_2">Identité examinée</option>
              {isProfessional && <option value="level_3">Commerçant professionnel vérifié</option>}
            </select>
          </label>
          <label className={cx("grid gap-1 text-sm", t.textPrimary)}>
            Type de justificatif
            <select value={documentType} onChange={(event) => setDocumentType(event.target.value)} className="rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-600 dark:bg-zinc-800">
              {targetLevel === "level_2" ? (
                <>
                  <option value="identity">Pièce d’identité</option>
                  <option value="passport">Passeport</option>
                  <option value="national_id">Carte nationale d’identité</option>
                  <option value="drivers_license">Permis de conduire</option>
                </>
              ) : (
                <>
                  <option value="business_registration">Enregistrement professionnel</option>
                  <option value="business_location">Photo récente du commerce</option>
                  <option value="business_activity">Preuve d’activité commerciale</option>
                  <option value="tax_id">Document fiscal, si applicable</option>
                </>
              )}
            </select>
          </label>
          <label className={cx("grid gap-1 text-sm sm:col-span-2", t.textPrimary)}>
            Justificatif(s)
            <input type="file" accept=".jpg,.jpeg,.png,.pdf,.heic,.heif" multiple onChange={(event) => setFiles(Array.from(event.target.files || []))} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600" />
            <span className={cx("text-xs", t.textMuted)}>10 Mo maximum par fichier. Formats : JPEG, PNG, HEIC ou PDF.</span>
          </label>
          <label className={cx("grid gap-1 text-sm sm:col-span-2", t.textPrimary)}>
            Précisions utiles (facultatif)
            <textarea rows="3" maxLength="2000" value={description} onChange={(event) => setDescription(event.target.value)} className="rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-600 dark:bg-zinc-800" />
          </label>
          {error && <p className="text-sm text-rose-700 sm:col-span-2" role="alert">{error}</p>}
          {notice && <p className="text-sm text-emerald-700 sm:col-span-2" role="status">{notice}</p>}
          {requestIsOpen && <p className={cx("text-sm sm:col-span-2", t.textMuted)}>Une demande est déjà en cours pour ce niveau.</p>}
          <button type="submit" disabled={busy || requestIsOpen} className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50 sm:col-span-2 sm:justify-self-start">
            <Upload className="h-4 w-4" /> {busy ? "Envoi…" : canEditRequest ? "Compléter et renvoyer" : "Envoyer pour examen"}
          </button>
        </form>
      </div>
      {error && !status && <ErrorBlock message={error} t={t} />}
    </section>
  );
}