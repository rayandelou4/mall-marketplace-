import React, { useEffect, useState } from "react";
import { AlertTriangle, MessageSquareText, Scale } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { ModerationMessageForm } from "../components/ui/ModerationMessageForm";
import { ErrorBlock, LoadingBlock, SectionHeading } from "../components/ui/StatusBlocks";
import { appealDispute, fetchDisputes, replyToDispute } from "../features/moderation/api";
import { useAuth } from "../features/auth/AuthContext";
import { useTheme } from "../features/theme/ThemeContext";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";

const STATUS_LABELS = {
  open: "Ouvert",
  waiting_seller: "En attente du vendeur",
  waiting_buyer: "En attente de l’acheteur",
  under_review: "En cours d’examen",
  resolved: "Résolu",
  rejected: "Rejeté",
  closed: "Clôturé",
};

function formatDate(value) {
  return new Date(value).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
}

export default function DisputesPage() {
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, error: null, items: [] });
  const [formState, setFormState] = useState({ disputeId: null, kind: null });
  const [busy, setBusy] = useState(false);

  function load() {
    setState((current) => ({ ...current, loading: true, error: null }));
    fetchDisputes()
      .then((items) => setState({ loading: false, error: null, items }))
      .catch((error) => setState({ loading: false, error: error.message, items: [] }));
  }

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  async function handleResponse(dispute, kind, payload) {
    setBusy(true);
    try {
      const request = kind === "appeal" ? appealDispute : replyToDispute;
      await request(dispute.id, { body: payload.description, evidence_urls: payload.evidence_urls });
      setFormState({ disputeId: null, kind: null });
      load();
    } catch (error) {
      window.alert(error.message);
    } finally {
      setBusy(false);
    }
  }

  const { loading, error, items } = state;
  return (
    <div className={cx("min-h-screen", t.pageBg, t.textPrimary)}>
      <SiteHeader />
      <main className="mx-auto min-h-[65vh] max-w-4xl px-4 py-10 sm:px-6">
        <SectionHeading title="Centre de résolution" subtitle="Suivez les dossiers de vos commandes et échangez avec l’autre partie ou l’administration." t={t} />
        {loading ? <LoadingBlock t={t} /> : error ? <ErrorBlock message={error} t={t} /> : items.length === 0 ? (
          <div className={cx("mt-8 border-y py-10 text-center", t.border)}>
            <Scale className={cx("mx-auto h-8 w-8", t.textMuted)} />
            <p className={cx("mt-3 text-sm", t.textMuted)}>Aucun litige associé à vos commandes.</p>
            <Link to="/mes-commandes" className="mt-3 inline-block text-sm font-semibold text-indigo-600">Voir mes commandes</Link>
          </div>
        ) : (
          <div className="mt-6 flex flex-col gap-5">
            {items.map((dispute) => {
              const isBuyer = dispute.raised_by_username === useAuth().user?.username;
              const isFinal = ["resolved", "rejected", "closed"].includes(dispute.status);
              const currentForm = formState.disputeId === dispute.id ? formState.kind : null;
              return (
                <article key={dispute.id} className={cx("border-y py-5", t.border)}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <Link to={`/mes-commandes`} className={cx("font-semibold hover:underline", t.textPrimary)}>
                        Dossier · commande #{String(dispute.order).slice(0, 8)}
                      </Link>
                      <p className={cx("mt-1 text-sm", t.textMuted)}>{dispute.reason_display || dispute.reason} · {isBuyer ? `Vendeur @${dispute.seller_username}` : `Acheteur @${dispute.raised_by_username}`}</p>
                    </div>
                    <span className={cx("rounded-full px-3 py-1 text-xs font-semibold", isFinal ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800")}>
                      {STATUS_LABELS[dispute.status] || dispute.status}
                    </span>
                  </div>
                  <p className={cx("mt-3 whitespace-pre-wrap text-sm", t.textPrimary)}>{dispute.description}</p>
                  {dispute.refund_status && dispute.refund_status !== "not_applicable" && (
                    <p className={cx("mt-2 text-sm", t.textMuted)}>
                      Suivi du remboursement : {dispute.refund_status}
                      {dispute.refund_amount != null && ` · ${formatPrice(dispute.refund_amount, dispute.order_currency || "USD")}`}
                      {dispute.refund_reference && ` · Réf. ${dispute.refund_reference}`}
                    </p>
                  )}
                  {dispute.resolution && (
                    <div className="mt-3 border-l-2 border-emerald-500 pl-3">
                      <p className="text-xs font-semibold text-emerald-700">Décision motivée</p>
                      <p className={cx("mt-1 whitespace-pre-wrap text-sm", t.textPrimary)}>{dispute.resolution}</p>
                    </div>
                  )}
                  <div className={cx("mt-4 border-t pt-4", t.border)}>
                    <h2 className={cx("mb-3 flex items-center gap-2 text-sm font-semibold", t.textPrimary)}>
                      <MessageSquareText className="h-4 w-4" /> Historique des échanges
                    </h2>
                    <div className="flex flex-col gap-3">
                      {(dispute.messages || []).map((message) => (
                        <div key={message.id} className={cx("rounded-lg p-3", message.kind === "decision" ? "bg-emerald-50" : "bg-black/5")}>
                          <div className="flex flex-wrap justify-between gap-2 text-xs">
                            <span className={cx("font-semibold", t.textPrimary)}>{message.kind_display} · {message.author_username || "Administration"}</span>
                            <time className={t.textMuted}>{formatDate(message.created_at)}</time>
                          </div>
                          <p className={cx("mt-1 whitespace-pre-wrap text-sm", t.textPrimary)}>{message.body}</p>
                          {message.evidence?.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {message.evidence.filter((proof) => proof.image_url).map((proof) => (
                                <a key={proof.image_url} href={proof.image_url} target="_blank" rel="noreferrer">
                                  <img src={proof.image_url} alt="Preuve jointe au litige" className="h-20 w-20 rounded-lg object-cover" />
                                </a>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                  {currentForm ? (
                    <ModerationMessageForm
                      t={t}
                      reasons={[]}
                      showReason={false}
                      allowImages
                      loading={busy}
                      placeholder={currentForm === "appeal" ? "Expliquez les motifs de votre contestation…" : "Ajoutez une réponse au dossier…"}
                      submitLabel={currentForm === "appeal" ? "Envoyer la contestation" : "Envoyer la réponse"}
                      onSubmit={(payload) => handleResponse(dispute, currentForm, payload)}
                      onCancel={() => setFormState({ disputeId: null, kind: null })}
                    />
                  ) : (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {!isFinal && (
                        <button type="button" onClick={() => setFormState({ disputeId: dispute.id, kind: "reply" })} className="min-h-11 rounded-lg border px-4 py-2 text-sm font-semibold text-indigo-600">
                          Répondre au dossier
                        </button>
                      )}
                      {dispute.appeal_allowed && (
                        <button type="button" onClick={() => setFormState({ disputeId: dispute.id, kind: "appeal" })} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-amber-300 px-4 py-2 text-sm font-semibold text-amber-800">
                          <AlertTriangle className="h-4 w-4" /> Contester la décision avant le {formatDate(dispute.appeal_deadline)}
                        </button>
                      )}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </main>
      <SiteFooter t={t} />
    </div>
  );
}