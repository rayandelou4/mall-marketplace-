import React, { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { AlertTriangle, ShieldCheck, XCircle } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { fetchReports, fetchDisputes, decideReport } from "../features/moderation/api";
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

export default function AdminModerationPage() {
  const { t } = useTheme();
  const { user, isAuthenticated, bootstrapping } = useAuth();
  const [reports, setReports] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !user?.is_staff) return;

    async function load() {
      try {
        setLoading(true);
        const [reportList, disputeList] = await Promise.all([fetchReports(), fetchDisputes()]);
        setReports(reportList);
        setDisputes(disputeList);
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
  }), [reports, disputes]);

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

  if (!bootstrapping && (!isAuthenticated || !user?.is_staff)) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <SectionHeading title="Modération" subtitle="Signalements et litiges" t={t} />

        <div className="mb-8 grid gap-4 sm:grid-cols-2">
          <div className={cx("rounded-2xl border p-5", t.cardBorder, t.cardBg)}>
            <p className={cx("mb-2 text-sm font-semibold", t.textMuted)}>Signalements</p>
            <p className="text-3xl font-bold">{stats.reports}</p>
          </div>
          <div className={cx("rounded-2xl border p-5", t.cardBorder, t.cardBg)}>
            <p className={cx("mb-2 text-sm font-semibold", t.textMuted)}>Litiges ouverts</p>
            <p className="text-3xl font-bold">{stats.openDisputes}</p>
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
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
