import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PackageCheck, XCircle, Star, AlertTriangle, ChevronDown, Trash2 } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { fetchOrders, fetchOrderDetails, confirmReceipt, cancelOrder, deleteOrder } from "../features/orders/api";
import { createReview } from "../features/reviews/api";
import { createDispute } from "../features/moderation/api";
import { ModerationMessageForm } from "../components/ui/ModerationMessageForm";
import { DISPUTE_REASONS } from "../features/moderation/formOptions";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";

const STATUS_LABELS = {
  pending: "En attente de remise",
  paid: "Payée",
  shipped: "Expédiée",
  delivered: "Livrée",
  cancelled: "Annulée",
  disputed: "En litige",
  refunded: "Remboursée",
};

function ReviewForm({ t, onSubmit, onCancel }) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit({ rating, comment });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className={cx("mt-2 flex flex-col gap-2 rounded-xl border p-3", t.border)}>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" onClick={() => setRating(n)} aria-label={`${n} étoiles`}>
            <Star className={cx("h-5 w-5", n <= rating ? "fill-amber-400 text-amber-400" : "text-zinc-300")} />
          </button>
        ))}
      </div>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Votre commentaire (optionnel)"
        rows={2}
        className={cx("rounded-lg border px-3 py-2 text-sm outline-none focus:border-indigo-500", t.inputBg, t.border, t.textPrimary)}
      />
      <div className="flex gap-2">
        <button type="submit" disabled={saving} className="rounded-full bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-60">
          Envoyer l'avis
        </button>
        <button type="button" onClick={onCancel} className={cx("rounded-full border px-4 py-1.5 text-xs font-semibold", t.border, t.textMuted)}>
          Annuler
        </button>
      </div>
    </form>
  );
}

export default function OrdersPage() {
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, error: null, items: [] });
  const [busyId, setBusyId] = useState(null);
  const [openOrderId, setOpenOrderId] = useState(null);
  const [orderDetails, setOrderDetails] = useState({});
  const [openReview, setOpenReview] = useState(null); // `${orderId}:${seller}` en cours de saisie
  const [reviewedKeys, setReviewedKeys] = useState(new Set());
  const [openDispute, setOpenDispute] = useState(null); // orderId en cours de saisie

  function load() {
    setState((s) => ({ ...s, loading: true }));
    fetchOrders()
      .then((items) => setState({ loading: false, error: null, items }))
      .catch((err) => setState({ loading: false, error: err.message, items: [] }));
  }

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  async function handleConfirm(order) {
    setBusyId(order.id);
    try {
      await confirmReceipt(order.id);
      load();
    } catch (err) {
      window.alert(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleCancel(order) {
    if (!window.confirm("Annuler cette commande ?")) return;
    setBusyId(order.id);
    try {
      await cancelOrder(order.id);
      load();
    } catch (err) {
      window.alert(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleDeleteOrder(order) {
    if (!window.confirm("Retirer cette commande livrée ou annulée de votre liste ? L’historique comptable restera conservé.")) return;
    setBusyId(order.id);
    try {
      await deleteOrder(order.id);
      setOpenOrderId((current) => current === order.id ? null : current);
      load();
    } catch (err) {
      window.alert(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function toggleOrderDetails(orderId) {
    const cachedDetails = orderDetails[orderId];
    if (openOrderId === orderId && !cachedDetails?.error) {
      setOpenOrderId(null);
      return;
    }
    setOpenOrderId(orderId);
    if (cachedDetails?.items || cachedDetails?.loading) return;

    setOrderDetails((current) => ({
      ...current,
      [orderId]: { loading: true, error: null, items: null },
    }));
    try {
      const detail = await fetchOrderDetails(orderId);
      setOrderDetails((current) => ({
        ...current,
        [orderId]: { loading: false, error: null, items: detail.items || [] },
      }));
    } catch (error) {
      setOrderDetails((current) => ({
        ...current,
        [orderId]: { loading: false, error: error.message, items: null },
      }));
    }
  }

  async function handleSubmitReview(order, seller, { rating, comment }) {
    const key = `${order.id}:${seller}`;
    try {
      await createReview({ order_id: order.id, reviewed_username: seller, rating, comment });
      setReviewedKeys((s) => new Set(s).add(key));
      setOpenReview(null);
    } catch (err) {
      window.alert(err.message);
    }
  }

  async function handleSubmitDispute(order, { reason, description, evidence_urls }) {
    try {
      await createDispute({ order_id: order.id, reason, description, evidence_urls });
      setOpenDispute(null);
      load();
    } catch (err) {
      window.alert(err.message);
    }
  }

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <SectionHeading title="Mes commandes" t={t} />
        <Link to="/litiges" className="mb-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-indigo-600 hover:underline">
          <AlertTriangle className="h-4 w-4" /> Centre de résolution et suivi des litiges
        </Link>

        {state.loading ? (
          <LoadingBlock t={t} />
        ) : state.error ? (
          <ErrorBlock message={state.error} t={t} />
        ) : state.items.length === 0 ? (
          <p className={cx("text-sm", t.textMuted)}>
            Aucune commande pour l'instant.{" "}
            <Link to="/catalogue" className="font-semibold text-indigo-600 hover:underline">Parcourir le catalogue</Link>
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {state.items.map((order) => (
              <div key={order.id} className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className={cx("text-sm font-semibold", t.textPrimary)}>Commande #{order.id.slice(0, 8)}</span>
                  <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-600">
                    {STATUS_LABELS[order.status] || order.status}
                  </span>
                </div>
                <p className={cx("mt-1 text-xs", t.textMuted)}>
                  {order.items_count} article{order.items_count > 1 ? "s" : ""} · {formatPrice(order.total_amount, order.currency)}
                </p>

                <button
                  type="button"
                  onClick={() => toggleOrderDetails(order.id)}
                  aria-expanded={openOrderId === order.id}
                  aria-controls={`order-details-${order.id}`}
                  className={cx("mt-2 inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:underline")}
                >
                  {orderDetails[order.id]?.error ? "Réessayer" : openOrderId === order.id ? "Masquer les articles" : "Voir les articles"}
                  <ChevronDown className={cx("h-3.5 w-3.5 transition-transform", openOrderId === order.id && "rotate-180")} />
                </button>

                {openOrderId === order.id && (
                  <div id={`order-details-${order.id}`} className={cx("mt-3 border-t pt-3", t.border)}>
                    {orderDetails[order.id]?.loading ? (
                      <p className={cx("text-sm", t.textMuted)}>Chargement des articles…</p>
                    ) : orderDetails[order.id]?.error ? (
                      <p className="text-sm text-rose-600">{orderDetails[order.id].error}</p>
                    ) : (
                      <div className="flex flex-col divide-y divide-zinc-200 dark:divide-zinc-800">
                        {(orderDetails[order.id]?.items || []).map((item) => (
                          <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                            <div className="min-w-0 flex-1">
                              <p className={cx("truncate text-sm font-semibold", t.textPrimary)}>{item.product_title}</p>
                              <Link to={`/vendeurs/${item.seller_username}`} className="mt-0.5 inline-block text-xs font-medium text-indigo-600 hover:underline">
                                Vendu par {item.seller_username}
                              </Link>
                            </div>
                            <div className="shrink-0 text-right">
                              <p className={cx("text-sm font-semibold", t.textPrimary)}>{formatPrice(item.subtotal, item.currency)}</p>
                              <p className={cx("text-xs", t.textMuted)}>
                                {item.quantity} × {formatPrice(item.unit_price, item.currency)}
                                {Number(item.shipping_cost) > 0 && ` · livraison ${formatPrice(item.shipping_cost, item.currency)}`}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  {order.payment_method === "cash" && (
                    (order.status === "shipped" || (order.status === "pending" && !order.has_delivery)) && (
                    <button
                      onClick={() => handleConfirm(order)}
                      disabled={busyId === order.id}
                      className="flex items-center gap-1.5 rounded-full bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                    >
                      <PackageCheck className="h-3.5 w-3.5" /> Confirmer la réception
                    </button>
                    )
                  )}
                  {order.status === "pending" && (
                    <button
                      onClick={() => handleCancel(order)}
                      disabled={busyId === order.id}
                      className="flex items-center gap-1.5 rounded-full border border-rose-200 px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 disabled:opacity-60"
                    >
                      <XCircle className="h-3.5 w-3.5" /> Annuler
                    </button>
                  )}
                  {["delivered", "cancelled"].includes(order.status) && (
                    <button
                      type="button"
                      onClick={() => handleDeleteOrder(order)}
                      disabled={busyId === order.id}
                      className="flex items-center gap-1.5 rounded-full border border-zinc-200 px-4 py-2 text-xs font-semibold text-zinc-600 hover:border-rose-300 hover:text-rose-600 disabled:opacity-60"
                    >
                      <Trash2 className="h-3.5 w-3.5" /> Retirer de la liste
                    </button>
                  )}
                  {["pending", "paid", "delivered"].includes(order.status) && openDispute !== order.id && (
                    <button
                      onClick={() => setOpenDispute(order.id)}
                      className="flex items-center gap-1.5 rounded-full border border-rose-200 px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50"
                    >
                      <AlertTriangle className="h-3.5 w-3.5" /> Signaler un litige
                    </button>
                  )}
                </div>

                {openDispute === order.id && (
                  <ModerationMessageForm
                    t={t}
                    reasons={DISPUTE_REASONS}
                    submitLabel="Envoyer le litige"
                    allowImages
                    onSubmit={(message) => handleSubmitDispute(order, message)}
                    onCancel={() => setOpenDispute(null)}
                  />
                )}

                {order.status === "delivered" && (order.sellers || []).map((seller) => {
                  const key = `${order.id}:${seller}`;
                  if (reviewedKeys.has(key)) {
                    return (
                      <p key={key} className={cx("mt-2 text-xs", t.textMuted)}>Avis envoyé pour {seller}.</p>
                    );
                  }
                  return (
                    <div key={key} className="mt-2">
                      {openReview === key ? (
                        <ReviewForm
                          t={t}
                          onSubmit={(payload) => handleSubmitReview(order, seller, payload)}
                          onCancel={() => setOpenReview(null)}
                        />
                      ) : (
                        <button
                          onClick={() => setOpenReview(key)}
                          className="flex items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-semibold text-indigo-600 hover:bg-indigo-50"
                        >
                          <Star className="h-3.5 w-3.5" /> Laisser un avis pour {seller}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
