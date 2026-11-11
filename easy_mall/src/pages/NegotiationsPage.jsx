import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, Clock3, X } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { TextField } from "../components/ui/FormControls";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { useCart } from "../features/cart/CartContext";
import { acceptNegotiation, counterNegotiation, fetchNegotiations, rejectNegotiation } from "../features/negotiations/api";
import { fetchProduct } from "../features/catalog/api";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";

const STATUS_LABELS = {
  open: "En attente de réponse",
  accepted: "Acceptée · commande à finaliser",
  rejected: "Refusée",
  expired: "Expirée",
  completed: "Commandée",
};

const EVENT_LABELS = {
  proposal: "Proposition",
  counter_proposal: "Contre-proposition",
  accepted: "Prix accepté",
  rejected: "Proposition refusée",
  expired: "Négociation expirée",
  checkout: "Commande créée",
};

function formatDate(value) {
  return new Intl.DateTimeFormat("fr-CD", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function NegotiationsPage() {
  const { t } = useTheme();
  const { user, isAuthenticated } = useAuth();
  const { addItem } = useCart();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, error: null, items: [] });
  const [busyId, setBusyId] = useState(null);
  const [counterAmounts, setCounterAmounts] = useState({});

  function load() {
    setState((current) => ({ ...current, loading: true, error: null }));
    fetchNegotiations()
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

  async function handleAction(negotiation, action, amount = null) {
    setBusyId(negotiation.id);
    setState((current) => ({ ...current, error: null }));
    try {
      if (action === "accept") await acceptNegotiation(negotiation.id);
      else if (action === "reject") await rejectNegotiation(negotiation.id);
      else await counterNegotiation(negotiation.id, amount);
      load();
    } catch (error) {
      setState((current) => ({ ...current, error: error.message }));
    } finally {
      setBusyId(null);
    }
  }

  async function handleCheckout(negotiation) {
    setBusyId(negotiation.id);
    try {
      const product = await fetchProduct(negotiation.product);
      const variant = product.variants?.find((item) => item.id === negotiation.variant) || null;
      addItem(product, 1, null, variant, {
        id: negotiation.id,
        accepted_price: negotiation.accepted_price,
        reserved_until: negotiation.reserved_until,
      });
      navigate("/panier");
    } catch (error) {
      setState((current) => ({ ...current, error: error.message }));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
        <SectionHeading
          title="Mes négociations"
          subtitle="Une acceptation réserve temporairement l’article; la vente n’existe qu’après commande et paiement selon le mode proposé."
          t={t}
        />
        {state.error && <div className="mt-5"><ErrorBlock message={state.error} t={t} /></div>}
        {state.loading ? <LoadingBlock t={t} /> : state.items.length === 0 ? (
          <p className={cx("mt-6 text-sm", t.textMuted)}>
            Aucune négociation pour le moment. Proposez un prix depuis une annonce de produit.
          </p>
        ) : (
          <div className="mt-6 flex flex-col gap-4">
            {state.items.map((negotiation) => {
              const proposalEvents = negotiation.events.filter((event) => ["proposal", "counter_proposal"].includes(event.kind));
              const latestProposal = proposalEvents.at(-1);
              const canRespond = negotiation.status === "open"
                && latestProposal?.actor_username !== user?.username;
              const isBuyer = negotiation.buyer_username === user?.username;
              const counterAmount = counterAmounts[negotiation.id] || "";

              return (
                <article key={negotiation.id} className={cx("rounded-xl border p-4 sm:p-5", t.cardBorder, t.cardBg)}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link to={`/produit/${negotiation.product}`} className={cx("font-semibold hover:underline", t.textPrimary)}>
                        {negotiation.product_title}{negotiation.variant_label ? ` · ${negotiation.variant_label}` : ""}
                      </Link>
                      <p className={cx("mt-1 text-xs", t.textMuted)}>
                        {isBuyer ? `Vendeur : ${negotiation.seller_username}` : `Acheteur : ${negotiation.buyer_username}`}
                      </p>
                    </div>
                    <span className={cx("rounded-full px-3 py-1 text-xs font-semibold", negotiation.status === "accepted" ? "bg-emerald-100 text-emerald-800" : negotiation.status === "open" ? "bg-amber-100 text-amber-800" : "bg-zinc-100 text-zinc-600")}>
                      {STATUS_LABELS[negotiation.status] || negotiation.status}
                    </span>
                  </div>

                  <div className={cx("mt-4 border-l-2 pl-4", t.border)}>
                    <ol className="flex flex-col gap-3">
                      {negotiation.events.map((event) => (
                        <li key={event.id} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm">
                          <span className={t.textPrimary}>
                            <span className="font-medium">{event.actor_username || "Système"}</span>
                            {` · ${EVENT_LABELS[event.kind] || event.kind}`}
                            {event.amount != null && ` : ${formatPrice(event.amount, negotiation.currency)}`}
                          </span>
                          <time className={cx("text-xs", t.textMuted)} dateTime={event.created_at}>{formatDate(event.created_at)}</time>
                        </li>
                      ))}
                    </ol>
                  </div>

                  {negotiation.status === "open" && (
                    <p className={cx("mt-3 flex items-center gap-1 text-xs", t.textMuted)}>
                      <Clock3 className="h-3.5 w-3.5" /> Réponse attendue avant le {formatDate(negotiation.expires_at)} · {negotiation.proposal_count}/{negotiation.max_proposals} propositions
                    </p>
                  )}
                  {negotiation.status === "accepted" && (
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-emerald-700">
                        Réservé jusqu’au {formatDate(negotiation.reserved_until)}. Finalisez votre commande dans ce délai.
                      </p>
                      {isBuyer && (
                        <button type="button" onClick={() => handleCheckout(negotiation)} disabled={busyId === negotiation.id} className="min-h-11 rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                          {busyId === negotiation.id ? "Chargement…" : `Commander · ${formatPrice(negotiation.accepted_price, negotiation.currency)}`}
                        </button>
                      )}
                    </div>
                  )}

                  {canRespond && (
                    <div className="mt-4 flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-end">
                      <button type="button" onClick={() => handleAction(negotiation, "accept")} disabled={busyId === negotiation.id} className="flex min-h-11 items-center justify-center gap-2 rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                        <Check className="h-4 w-4" /> Accepter {formatPrice(latestProposal?.amount, negotiation.currency)}
                      </button>
                      <button type="button" onClick={() => handleAction(negotiation, "reject")} disabled={busyId === negotiation.id} className={cx("flex min-h-11 items-center justify-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold disabled:opacity-50", t.border, t.textPrimary)}>
                        <X className="h-4 w-4" /> Refuser
                      </button>
                      {negotiation.proposal_count < negotiation.max_proposals && (
                        <form
                          className="flex min-w-0 flex-1 items-end gap-2"
                          onSubmit={(event) => {
                            event.preventDefault();
                            if (counterAmount) handleAction(negotiation, "counter", counterAmount);
                          }}
                        >
                          <TextField
                            label={`Contre-proposition (${negotiation.currency})`}
                            type="number"
                            min="0.01"
                            step="0.01"
                            value={counterAmount}
                            onChange={(value) => setCounterAmounts((current) => ({ ...current, [negotiation.id]: value }))}
                            required
                            t={t}
                          />
                          <button type="submit" disabled={busyId === negotiation.id || !counterAmount} className="min-h-11 shrink-0 rounded-full border px-4 py-2 text-sm font-semibold disabled:opacity-50">
                            Contre-offrir
                          </button>
                        </form>
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