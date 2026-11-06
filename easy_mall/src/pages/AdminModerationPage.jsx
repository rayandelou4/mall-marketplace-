import React, { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { AlertTriangle, Ban, BarChart3, Download, Flag, RotateCcw, ShieldCheck, XCircle } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { decideReport, fetchDisputes, fetchMessageReports, fetchReports, moderateAccount, reviewDispute, reviewMessageReport } from "../features/moderation/api";
import {
  downloadVerificationDocument,
  fetchAdminVerificationRequests,
  reviewAdminVerificationRequest,
} from "../features/seller/verificationApi";
import { cx } from "../styles/theme";

const REPORT_REASONS = {
  counterfeit_product: "Produit potentiellement contrefait",
  misleading_description: "Description trompeuse",
  misleading_photos: "Photos trompeuses",
  prohibited_product: "Produit interdit",
  scam_suspected: "Suspicion d'arnaque",
  misleading_pricing: "Prix ou caractéristiques trompeurs",
  duplicate_or_spam: "Annonce dupliquée ou spam",
  other: "Autre motif",
};

const DISPUTE_STATUS_LABELS = {
  open: "Ouvert",
  waiting_seller: "En attente du vendeur",
  waiting_buyer: "En attente de l’acheteur",
  under_review: "En cours d’examen",
  resolved: "Résolu",
  rejected: "Rejeté",
  closed: "Clôturé",
};

const MESSAGE_REPORT_REASONS = {
  threat: "Menace",
  inappropriate: "Message inapproprié",
  harassment: "Harcèlement",
  fraud: "Fraude ou tentative d’arnaque",
  other: "Autre motif",
};

const MESSAGE_REPORT_STATUS_LABELS = {
  new: "Nouveau",
  under_review: "En cours d’examen",
  valid: "Fondé",
  rejected: "Rejeté",
  closed: "Clôturé",
};

const VERIFICATION_STATUS_LABELS = {
  pending: "En attente",
  under_review: "En cours d’examen",
  needs_more_info: "Informations à compléter",
  approved: "Approuvée",
  rejected: "Refusée",
  expired: "Expirée",
  cancelled: "Annulée",
  draft: "Brouillon",
};

const REVIEWABLE_REQUEST_STATUSES = new Set(["pending", "under_review", "needs_more_info"]);

export default function AdminModerationPage() {
  const { t } = useTheme();
  const { user, isAuthenticated, bootstrapping } = useAuth();
  const [reports, setReports] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [messageReports, setMessageReports] = useState([]);
  const [verificationRequests, setVerificationRequests] = useState([]);
  const [requestFilter, setRequestFilter] = useState("active");
  const [requestDecisions, setRequestDecisions] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [downloadBusy, setDownloadBusy] = useState(null);

  useEffect(() => {
    if (!isAuthenticated || !user?.is_staff) return;

    async function load() {
      try {
        setLoading(true);
        const [reportList, disputeList, messageReportList, requestList] = await Promise.all([
          fetchReports(),
          fetchDisputes(),
          fetchMessageReports(),
          fetchAdminVerificationRequests(),
        ]);
        setReports(reportList);
        setDisputes(disputeList);
        setMessageReports(messageReportList);
        setVerificationRequests(requestList);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [isAuthenticated, user]);

  const stats = useMemo(() => ({
    reports: reports.length,
    openDisputes: disputes.filter((d) => ["open", "waiting_seller", "waiting_buyer", "under_review"].includes(d.status)).length,
    messageReports: messageReports.filter((report) => ["new", "under_review"].includes(report.status)).length,
    pendingRequests: verificationRequests.filter((request) => REVIEWABLE_REQUEST_STATUSES.has(request.status)).length,
  }), [reports, disputes, messageReports, verificationRequests]);

  const visibleVerificationRequests = requestFilter === "active"
    ? verificationRequests.filter((request) => REVIEWABLE_REQUEST_STATUSES.has(request.status))
    : verificationRequests;

  async function handleDecision(reportId, decision, reason) {
    setActionBusy(true);
    try {
      const updated = await decideReport(reportId, { decision, reason });
      setReports((items) => items.map((item) => (item.id === reportId ? updated : item)));
    } catch (err) {
      window.alert(err.message);
    } finally {
      setActionBusy(false);
    }
  }

  async function handleDisputeReview(event, disputeId) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setActionBusy(true);
    try {
      const updated = await reviewDispute(disputeId, {
        status: formData.get("status"),
        resolution: formData.get("resolution"),
      });
      setDisputes((items) => items.map((item) => (item.id === disputeId ? updated : item)));
    } catch (err) {
      window.alert(err.message);
    } finally {
      setActionBusy(false);
    }
  }

  async function handleMessageReportReview(event, reportId) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setActionBusy(true);
    try {
      const updated = await reviewMessageReport(reportId, {
        status: formData.get("status"),
        review_notes: formData.get("review_notes"),
      });
      setMessageReports((items) => items.map((item) => item.id === reportId ? updated : item));
    } catch (err) {
      window.alert(err.message);
    } finally {
      setActionBusy(false);
    }
  }

  async function handleAccountModeration(accountId, username, isSuspended) {
    const action = isSuspended ? "rétablir" : "suspendre";
    const reason = window.prompt(`Motif pour ${action} le compte @${username} :`);
    if (reason === null) return;
    if (!reason.trim()) {
      window.alert("Un motif est obligatoire.");
      return;
    }
    setActionBusy(true);
    try {
      const result = await moderateAccount(accountId, { suspended: !isSuspended, reason: reason.trim() });
      const nextState = result.account.is_suspended;
      setReports((items) => items.map((report) => String(report.seller) === String(accountId)
        ? { ...report, seller_is_suspended: nextState }
        : report));
      setDisputes((items) => items.map((dispute) => ({
        ...dispute,
        ...(String(dispute.seller) === String(accountId) ? { seller_is_suspended: nextState } : {}),
        ...(String(dispute.raised_by) === String(accountId) ? { raised_by_is_suspended: nextState } : {}),
      })));
      setMessageReports((items) => items.map((report) => String(report.reported_user_id) === String(accountId)
        ? { ...report, reported_user_is_suspended: nextState }
        : report));
    } catch (err) {
      window.alert(err.message);
    } finally {
      setActionBusy(false);
    }
  }

  function accountActionButton(accountId, username, suspended) {
    if (!accountId) return null;
    return (
      <button type="button" disabled={actionBusy} onClick={() => handleAccountModeration(accountId, username, suspended)} className={cx("inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-semibold disabled:opacity-60", suspended ? "border-emerald-200 text-emerald-700" : "border-rose-200 text-rose-700")}>
        {suspended ? <RotateCcw className="h-3.5 w-3.5" /> : <Ban className="h-3.5 w-3.5" />}
        {suspended ? "Rétablir le compte" : "Suspendre le compte"}
      </button>
    );
  }

  async function handleVerificationReview(event, request) {
    event.preventDefault();
    const decision = requestDecisions[request.id] || "request_more_info";
    const message = new FormData(event.currentTarget).get("message").trim();
    setActionBusy(true);
    try {
      const payload = { decision, notes: message };
      if (decision === "reject") payload.rejection_reason = message;
      if (decision === "request_more_info") payload.seller_message = message;
      const updated = await reviewAdminVerificationRequest(request.id, payload);
      setVerificationRequests((items) => items.map((item) => (item.id === request.id ? updated : item)));
    } catch (err) {
      window.alert(err.message);
    } finally {
      setActionBusy(false);
    }
  }

  async function handleDocumentDownload(documentItem) {
    setDownloadBusy(documentItem.id);
    try {
      const file = await downloadVerificationDocument(documentItem.id);
      const url = URL.createObjectURL(file);
      const link = document.createElement("a");
      link.href = url;
      link.download = `justificatif-${documentItem.id}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      window.alert(err.message);
    } finally {
      setDownloadBusy(null);
    }
  }

  if (!bootstrapping && (!isAuthenticated || !user?.is_staff)) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <SectionHeading title="Administration" subtitle="Signalements, litiges et demandes de vérification" t={t} />
        <Link to="/statistiques" className={cx("-mt-2 mb-6 inline-flex items-center gap-2 text-sm font-semibold", t.accentText)}>
          <BarChart3 className="h-4 w-4" /> Statistiques globales
        </Link>

        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className={cx("rounded-2xl border p-5", t.cardBorder, t.cardBg)}>
            <p className={cx("mb-2 text-sm font-semibold", t.textMuted)}>Signalements</p>
            <p className="text-3xl font-bold">{stats.reports}</p>
          </div>
          <div className={cx("rounded-2xl border p-5", t.cardBorder, t.cardBg)}>
            <p className={cx("mb-2 text-sm font-semibold", t.textMuted)}>Litiges ouverts</p>
            <p className="text-3xl font-bold">{stats.openDisputes}</p>
          </div>
          <div className={cx("rounded-2xl border p-5", t.cardBorder, t.cardBg)}>
            <p className={cx("mb-2 text-sm font-semibold", t.textMuted)}>Signalements de messages à traiter</p>
            <p className="text-3xl font-bold">{stats.messageReports}</p>
          </div>
          <div className={cx("rounded-2xl border p-5", t.cardBorder, t.cardBg)}>
            <p className={cx("mb-2 text-sm font-semibold", t.textMuted)}>Demandes à examiner</p>
            <p className="text-3xl font-bold">{stats.pendingRequests}</p>
          </div>
        </div>

        {loading ? (
          <LoadingBlock t={t} />
        ) : error ? (
          <ErrorBlock message={error} t={t} />
        ) : (
          <div className="grid gap-8 lg:grid-cols-2">
            <section>
              <h2 className="mb-4 text-lg font-semibold">Signalements</h2>
              {reports.length === 0 ? (
                <p className={cx("rounded-xl border p-4 text-sm", t.cardBorder, t.cardBg, t.textMuted)}>
                  Aucun signalement à traiter.
                </p>
              ) : (
                <div className="flex flex-col gap-4">
                  {reports.map((report) => (
                    <div key={report.id} className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold">{report.product_id || report.product}</p>
                          <p className={cx("text-xs", t.textMuted)}>
                            {report.reporter_username} · {REPORT_REASONS[report.reason] || report.reason}
                          </p>
                        </div>
                        <span className={cx("rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide", report.status === "valid" ? "bg-emerald-100 text-emerald-700" : report.status === "rejected" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700")}>{report.status_display}</span>
                      </div>
                      <p className={cx("mt-3 text-sm", t.textMuted)}>{report.description || "Aucune description ajoutée."}</p>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                        <span className={t.textMuted}>Compte vendeur · @{report.seller_username}</span>
                        {accountActionButton(report.seller, report.seller_username, report.seller_is_suspended)}
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <button type="button" disabled={actionBusy} onClick={() => handleDecision(report.id, "under_review", "Examen manuel demandé.")} className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-100">
                          Examiner
                        </button>
                        <button type="button" disabled={actionBusy} onClick={() => handleDecision(report.id, "reject", "Signalement rejeté.")} className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100">
                          Rejeter
                        </button>
                        <button type="button" disabled={actionBusy} onClick={() => handleDecision(report.id, "valid", "Signalement fondé.")} className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100">
                          Valider
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="mb-4 text-lg font-semibold">Litiges</h2>
              {disputes.length === 0 ? (
                <p className={cx("rounded-xl border p-4 text-sm", t.cardBorder, t.cardBg, t.textMuted)}>
                  Aucun litige ouvert.
                </p>
              ) : (
                <div className="flex flex-col gap-4">
                  {disputes.map((dispute) => (
                    <div key={dispute.id} className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold">Commande {String(dispute.order).slice(0, 8)}</p>
                          <p className={cx("text-xs", t.textMuted)}>{dispute.reason}</p>
                        </div>
                        <span className={cx("rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide", dispute.status === "resolved" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700")}>{DISPUTE_STATUS_LABELS[dispute.status] || dispute.status}</span>
                      </div>
                      <p className={cx("mt-3 text-sm", t.textMuted)}>{dispute.description || "Aucune description détaillée."}</p>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                        <span className={t.textMuted}>Acheteur · @{dispute.raised_by_username}</span>
                        {accountActionButton(dispute.raised_by, dispute.raised_by_username, dispute.raised_by_is_suspended)}
                        <span className={cx("ml-2", t.textMuted)}>Vendeur · @{dispute.seller_username}</span>
                        {accountActionButton(dispute.seller, dispute.seller_username, dispute.seller_is_suspended)}
                      </div>
                      {Array.isArray(dispute.evidence_view) && dispute.evidence_view.length > 0 && (
                        <div className="mt-3 rounded-lg border border-dashed border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                          <p className="mb-1 font-semibold">Preuves</p>
                          {dispute.evidence_view.map((item, index) => (
                            <div key={`${dispute.id}-evidence-${index}`} className="mb-1 last:mb-0">
                              {item.message || item.source || "Preuve jointe"}
                            </div>
                          ))}
                        </div>
                      )}
                      <form onSubmit={(event) => handleDisputeReview(event, dispute.id)} className={cx("mt-4 grid gap-3 border-t pt-4", t.border)}>
                        <label className={cx("grid gap-1 text-xs font-medium", t.textPrimary)}>
                          Décision
                          <select name="status" defaultValue={dispute.status} className={cx("rounded-lg border px-3 py-2 text-sm", t.inputBg, t.border, t.textPrimary)}>
                            {Object.entries(DISPUTE_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                          </select>
                        </label>
                        <label className={cx("grid gap-1 text-xs font-medium", t.textPrimary)}>
                          Résolution ou note interne
                          <textarea name="resolution" defaultValue={dispute.resolution || dispute.review_notes} rows={2} maxLength={4000} className={cx("rounded-lg border px-3 py-2 text-sm", t.inputBg, t.border, t.textPrimary)} />
                        </label>
                        <button type="submit" disabled={actionBusy} className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 sm:justify-self-start">
                          {actionBusy ? "Enregistrement…" : "Enregistrer la décision"}
                        </button>
                      </form>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {!loading && !error && (
          <section className="mt-8">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold"><Flag className="h-5 w-5" /> Signalements de messages</h2>
            {messageReports.length === 0 ? (
              <p className={cx("rounded-xl border p-4 text-sm", t.cardBorder, t.cardBg, t.textMuted)}>Aucun message signalé.</p>
            ) : (
              <div className="flex flex-col gap-4">
                {messageReports.map((report) => (
                  <article key={report.id} className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold">@{report.reported_username} · {MESSAGE_REPORT_REASONS[report.reason] || report.reason}</h3>
                        <p className={cx("mt-1 text-xs", t.textMuted)}>Signalé par @{report.reporter_username} · {new Date(report.created_at).toLocaleString("fr-FR")}</p>
                      </div>
                      <span className={cx("rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide", report.status === "valid" ? "bg-emerald-100 text-emerald-700" : report.status === "rejected" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700")}>{MESSAGE_REPORT_STATUS_LABELS[report.status] || report.status}</span>
                    </div>
                    <blockquote className={cx("mt-3 whitespace-pre-wrap border-l-2 pl-3 text-sm", t.border, t.textPrimary)}>{report.message_data?.content || "Message multimédia sans texte."}</blockquote>
                    {report.message_data?.image_url && <a href={report.message_data.image_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs font-semibold text-indigo-600">Ouvrir l’image jointe</a>}
                    {report.message_data?.voice_url && <audio controls preload="none" src={report.message_data.voice_url} className="mt-2 block max-w-full" />}
                    {report.description && <p className={cx("mt-2 whitespace-pre-wrap text-sm", t.textMuted)}>Précisions : {report.description}</p>}
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                      <span className={t.textMuted}>Compte signalé · @{report.reported_username}</span>
                      {accountActionButton(report.reported_user_id, report.reported_username, report.reported_user_is_suspended)}
                    </div>
                    <form onSubmit={(event) => handleMessageReportReview(event, report.id)} className={cx("mt-4 grid gap-3 border-t pt-4 sm:grid-cols-2", t.border)}>
                      <label className={cx("grid gap-1 text-xs font-medium", t.textPrimary)}>
                        Décision
                        <select name="status" defaultValue={report.status} className={cx("rounded-lg border px-3 py-2 text-sm", t.inputBg, t.border, t.textPrimary)}>
                          {Object.entries(MESSAGE_REPORT_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                      </label>
                      <label className={cx("grid gap-1 text-xs font-medium", t.textPrimary)}>
                        Note interne
                        <textarea name="review_notes" defaultValue={report.review_notes || ""} rows={2} maxLength={4000} className={cx("rounded-lg border px-3 py-2 text-sm", t.inputBg, t.border, t.textPrimary)} />
                      </label>
                      <button type="submit" disabled={actionBusy} className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 sm:justify-self-start">{actionBusy ? "Enregistrement…" : "Enregistrer la décision"}</button>
                    </form>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {!loading && !error && (
          <section className="mt-8">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Demandes de vérification</h2>
                <p className={cx("mt-1 text-sm", t.textMuted)}>Examen des justificatifs soumis par les vendeurs.</p>
              </div>
              <select value={requestFilter} onChange={(event) => setRequestFilter(event.target.value)} aria-label="Filtrer les demandes" className={cx("rounded-lg border px-3 py-2 text-sm", t.inputBg, t.border, t.textPrimary)}>
                <option value="active">À examiner</option>
                <option value="all">Toutes les demandes</option>
              </select>
            </div>
            {visibleVerificationRequests.length === 0 ? (
              <p className={cx("rounded-xl border p-4 text-sm", t.cardBorder, t.cardBg, t.textMuted)}>
                Aucune demande à afficher.
              </p>
            ) : (
              <div className="flex flex-col gap-4">
                {visibleVerificationRequests.map((request) => {
                  const decision = requestDecisions[request.id] || "request_more_info";
                  const isReviewable = REVIEWABLE_REQUEST_STATUSES.has(request.status);
                  return (
                    <article key={request.id} className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold">{request.user_display_name} · {request.target_level_display}</h3>
                          <p className={cx("mt-1 text-xs", t.textMuted)}>{request.verification_type_display} · {request.submitted_at ? new Date(request.submitted_at).toLocaleString("fr-FR") : "Date non disponible"}</p>
                        </div>
                        <span className={cx("rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide", request.status === "approved" ? "bg-emerald-100 text-emerald-700" : request.status === "rejected" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700")}>{VERIFICATION_STATUS_LABELS[request.status] || request.status}</span>
                      </div>
                      {request.description && <p className={cx("mt-3 whitespace-pre-wrap text-sm", t.textMuted)}>{request.description}</p>}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(request.documents || []).map((documentItem) => (
                          <div key={documentItem.id} className={cx("flex items-center gap-2 rounded-lg border px-3 py-2 text-xs", t.border)}>
                            <span>{documentItem.document_type} · {documentItem.file_size_mb} Mo · {documentItem.is_valid_format ? "Format valide" : "Format invalide"}</span>
                            {documentItem.download_url && (
                              <button type="button" onClick={() => handleDocumentDownload(documentItem)} disabled={downloadBusy === documentItem.id} aria-label="Télécharger le justificatif" title="Télécharger le justificatif" className={cx("rounded p-1", t.textMuted, downloadBusy === documentItem.id && "opacity-50")}>
                                <Download className="h-4 w-4" />
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                      {isReviewable ? (
                        <form onSubmit={(event) => handleVerificationReview(event, request)} className={cx("mt-4 grid gap-3 border-t pt-4 sm:grid-cols-2", t.border)}>
                          <label className={cx("grid gap-1 text-xs font-medium", t.textPrimary)}>
                            Décision
                            <select value={decision} onChange={(event) => setRequestDecisions((current) => ({ ...current, [request.id]: event.target.value }))} className={cx("rounded-lg border px-3 py-2 text-sm", t.inputBg, t.border, t.textPrimary)}>
                              <option value="request_more_info">Demander des informations</option>
                              <option value="approve">Approuver</option>
                              <option value="reject">Refuser</option>
                            </select>
                          </label>
                          <label className={cx("grid gap-1 text-xs font-medium sm:row-span-2", t.textPrimary)}>
                            {decision === "reject" ? "Motif de refus" : decision === "request_more_info" ? "Informations à demander" : "Note (facultatif)"}
                            <textarea name="message" required={decision !== "approve"} defaultValue={request.seller_message || request.rejection_reason || ""} rows={3} maxLength={4000} className={cx("rounded-lg border px-3 py-2 text-sm", t.inputBg, t.border, t.textPrimary)} />
                          </label>
                          <button type="submit" disabled={actionBusy} className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 sm:justify-self-start">
                            {actionBusy ? "Enregistrement…" : "Enregistrer la décision"}
                          </button>
                        </form>
                      ) : (
                        <p className={cx("mt-3 text-xs", t.textMuted)}>Cette demande a été traitée.</p>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
