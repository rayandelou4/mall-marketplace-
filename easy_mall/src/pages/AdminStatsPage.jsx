import React, { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { Users, Package, ShoppingBag, AlertTriangle, Star, TrendingUp, Store, ShieldCheck, Flag, MessageCircle, Ban } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { StatCard } from "../components/ui/StatCard";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { fetchGlobalStats } from "../features/analytics/api";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";

const ORDER_STATUS_LABELS = {
  pending: "En attente",
  paid: "Payées",
  shipped: "Expédiées",
  delivered: "Livrées",
  cancelled: "Annulées",
  disputed: "En litige",
  refunded: "Remboursées",
};

function BreakdownCard({ title, rows, empty, t }) {
  return (
    <div className={cx("rounded-2xl border p-5", t.cardBorder, t.cardBg)}>
      <p className={cx("mb-3 text-sm font-semibold", t.textPrimary)}>{title}</p>
      {rows.length === 0 ? (
        <p className={cx("text-sm", t.textMuted)}>{empty}</p>
      ) : (
        <div className="flex flex-col gap-2 text-sm">
          {rows.map(([label, value]) => (
            <div key={label} className="flex justify-between">
              <span className={t.textMuted}>{label}</span>
              <span className="font-mono font-semibold">{value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdminStatsPage() {
  const { t } = useTheme();
  const { user, isAuthenticated, bootstrapping } = useAuth();
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    if (!isAuthenticated || !user?.is_staff) return;
    fetchGlobalStats()
      .then((data) => setState({ loading: false, error: null, data }))
      .catch((err) => setState({ loading: false, error: err.message, data: null }));
  }, [isAuthenticated, user]);

  // Attend la fin de la restauration de session avant de juger de l'accès,
  // sinon un admin dont la session se restaure encore serait éjecté à tort.
  if (!bootstrapping && (!isAuthenticated || !user?.is_staff)) {
    return <Navigate to="/" replace />;
  }

  const { loading, error, data } = state;

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <SectionHeading title="Statistiques globales" subtitle="Réservé au staff." t={t} />

        {loading ? (
          <LoadingBlock t={t} />
        ) : error ? (
          <ErrorBlock message={error} t={t} />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatCard icon={Users} label="Utilisateurs" value={data.users.total} t={t} />
              <StatCard icon={Users} label="Nouveaux (30j)" value={data.users.new_last_30_days} t={t} />
              <StatCard icon={Store} label="Vendeurs particuliers" value={data.sellers.individual} t={t} />
              <StatCard icon={Store} label="Commerçants professionnels" value={data.sellers.professional} t={t} />
              <StatCard icon={Package} label="Annonces publiées" value={data.products.published} t={t} />
              <StatCard icon={Package} label="Annonces actives" value={data.products.active_listings} t={t} />
              <StatCard icon={AlertTriangle} label="En attente de modération" value={data.products.pending_moderation} t={t} />
              <StatCard icon={ShieldCheck} label="Vérifications en attente" value={data.verification.pending} t={t} />
              <StatCard icon={ShoppingBag} label="Commandes totales" value={data.orders.total} t={t} />
              <StatCard icon={AlertTriangle} label="Litiges ouverts" value={data.moderation.open_disputes} t={t} />
              <StatCard icon={Flag} label="Signalements annonces" value={data.moderation.open_product_reports} t={t} />
              <StatCard icon={MessageCircle} label="Signalements messages" value={data.moderation.open_message_reports} t={t} />
              <StatCard icon={AlertTriangle} label="Signalements à risque" value={data.moderation.high_risk_product_reports} t={t} />
              <StatCard icon={Ban} label="Comptes suspendus" value={data.moderation.suspended_accounts} t={t} />
              <StatCard icon={Star} label="Avis publiés" value={data.reviews.total} t={t} />
              <StatCard icon={TrendingUp} label="Annonces vendues" value={data.products.sold} t={t} />
            </div>

            <div className="mt-10 grid gap-6 sm:grid-cols-2">
              <BreakdownCard
                title="Commandes par statut"
                t={t}
                empty="Aucune commande."
                rows={Object.entries(data.orders.by_status).map(([status, count]) => [
                  ORDER_STATUS_LABELS[status] || status,
                  count,
                ])}
              />
              <BreakdownCard
                title="Volume d'affaires (GMV)"
                t={t}
                empty="Aucune commande pour l'instant."
                rows={Object.entries(data.revenue.gmv_by_currency).map(([currency, total]) => [
                  currency,
                  formatPrice(total, currency),
                ])}
              />
              <BreakdownCard
                title="Commissions enregistrées"
                t={t}
                empty="Aucune commission enregistrée."
                rows={Object.entries(data.revenue.commissions_by_currency).map(([currency, total]) => [
                  currency,
                  formatPrice(total, currency),
                ])}
              />
              <BreakdownCard
                title="Catégories les plus actives"
                t={t}
                empty="Aucune catégorie pour l'instant."
                rows={data.top_categories.map((c) => [c.category__name || "Sans catégorie", c.count])}
              />
            </div>
          </>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
