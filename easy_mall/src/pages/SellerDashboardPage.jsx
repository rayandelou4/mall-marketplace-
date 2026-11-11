import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Plus, Pencil, Trash2, Eye, Heart, Package, TrendingUp, MapPin, ShoppingBag, Star } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { StatCard } from "../components/ui/StatCard";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { fetchMyProducts, deleteProduct, fetchMySales, deleteSale, fetchStockHistory, markSaleShipped, fetchWallet, fetchPaymentConfig } from "../features/seller/api";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";
import { fetchSellerStats } from "../features/analytics/api";
import { VerificationPanel } from "../components/seller/VerificationPanel";
import { SellerLocalizationPanel } from "../components/seller/SellerLocalizationPanel";
import { SellerPromotionsPanel } from "../components/seller/SellerPromotionsPanel";

const STATUS_LABELS = { draft: "Brouillon", published: "Publié", sold: "Vendu", archived: "Archivé" };
const MODERATION_LABELS = { pending: "En attente de validation", approved: "Visible", rejected: "Refusée" };
const STATUS_STYLES = {
  draft: "bg-zinc-100 text-zinc-600",
  published: "bg-emerald-100 text-emerald-700",
  sold: "bg-indigo-100 text-indigo-700",
  archived: "bg-rose-100 text-rose-700",
};

export default function SellerDashboardPage() {
  const { t } = useTheme();
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [products, setProducts] = useState({ loading: true, error: null, items: [] });
  const [sales, setSales] = useState({ loading: true, error: null, items: [] });
  const [period, setPeriod] = useState("weekly");
  const [chartMetric, setChartMetric] = useState("units");
  const [chartCurrency, setChartCurrency] = useState("");
  const [analytics, setAnalytics] = useState({ loading: true, error: null, data: null });
  const [stockHistory, setStockHistory] = useState({});
  const [openStockHistory, setOpenStockHistory] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [activeSection, setActiveSection] = useState("products");
  const [busySaleId, setBusySaleId] = useState(null);
  const [wallet, setWallet] = useState(null);

  useEffect(() => {
    const section = searchParams.get("section");
    setActiveSection(["sales", "verification", "localization", "promotions"].includes(section) ? section : "products");
  }, [searchParams]);

  function loadProducts() {
    setProducts((s) => ({ ...s, loading: true }));
    fetchMyProducts()
      .then((items) => setProducts({ loading: false, error: null, items }))
      .catch((err) => setProducts({ loading: false, error: err.message, items: [] }));
  }

  function loadSales() {
    setSales((state) => ({ ...state, loading: true }));
    fetchMySales()
      .then((items) => setSales({ loading: false, error: null, items }))
      .catch((err) => setSales({ loading: false, error: err.message, items: [] }));
  }

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth");
      return;
    }
    loadProducts();
    loadSales();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    let active = true;
    setAnalytics((current) => ({ ...current, loading: true, error: null }));
    fetchSellerStats(period)
      .then((data) => {
        if (active) setAnalytics({ loading: false, error: null, data });
      })
      .catch((error) => {
        if (active) setAnalytics({ loading: false, error: error.message, data: null });
      });
    return () => { active = false; };
  }, [isAuthenticated, period]);

  useEffect(() => {
    if (!isAuthenticated) return undefined;
    let active = true;
    fetchPaymentConfig()
      .then(({ mode }) => mode === "online" ? fetchWallet() : null)
      .then((result) => {
        if (active && result) setWallet(result);
      })
      .catch(() => {});
    return () => { active = false; };
  }, [isAuthenticated]);

  async function handleDelete(product) {
    if (!window.confirm(`Supprimer « ${product.title} » ?`)) return;
    try {
      await deleteProduct(product.id);
      loadProducts();
    } catch (err) {
      window.alert(err.message);
    }
  }

  async function toggleStockHistory(productId) {
    if (openStockHistory === productId) {
      setOpenStockHistory(null);
      return;
    }
    setOpenStockHistory(productId);
    if (stockHistory[productId]) return;
    setStockHistory((current) => ({
      ...current,
      [productId]: { loading: true, error: null, items: [] },
    }));
    try {
      const items = await fetchStockHistory(productId);
      setStockHistory((current) => ({ ...current, [productId]: { loading: false, error: null, items } }));
    } catch (error) {
      setStockHistory((current) => ({ ...current, [productId]: { loading: false, error: error.message, items: [] } }));
    }
  }

  async function handleDeleteSale(item) {
    if (!window.confirm("Retirer cette vente livrée ou annulée de votre liste ? L’historique comptable restera conservé.")) return;
    setBusySaleId(item.id);
    try {
      await deleteSale(item.id);
      loadSales();
    } catch (error) {
      window.alert(error.message);
    } finally {
      setBusySaleId(null);
    }
  }

  async function handleMarkShipped(item) {
    setBusySaleId(item.id);
    try {
      await markSaleShipped(item.id);
      loadSales();
    } catch (error) {
      window.alert(error.message);
    } finally {
      setBusySaleId(null);
    }
  }

  const stats = {
    total: products.items.length,
    published: products.items.filter((p) => p.status === "published").length,
    views: products.items.reduce((sum, p) => sum + (p.views_count || 0), 0),
  };
  const sortedProducts = [...products.items].sort(
    (first, second) => new Date(second.created_at).getTime() - new Date(first.created_at).getTime()
  );
  const sortedSales = [...sales.items].sort(
    (first, second) => new Date(second.order_created_at).getTime() - new Date(first.order_created_at).getTime()
  );
  const visibleProducts = statusFilter === "all"
    ? sortedProducts
    : sortedProducts.filter((product) => product.status === statusFilter);
  const revenueSeries = analytics.data?.sales.revenue_series || [];
  const revenueCurrencies = [...new Set(revenueSeries.map((bucket) => bucket.currency))];
  const selectedChartCurrency = revenueCurrencies.includes(chartCurrency) ? chartCurrency : revenueCurrencies[0];
  const chartSeries = chartMetric === "revenue"
    ? revenueSeries.filter((bucket) => bucket.currency === selectedChartCurrency)
    : analytics.data?.sales.series || [];
  const chartValues = chartSeries.map((bucket) => chartMetric === "revenue" ? Number(bucket.revenue) : bucket[chartMetric]);
  const maxChartValue = Math.max(1, ...chartValues);
  const revenueSummary = analytics.data?.sales.revenue_by_currency
    .map(({ currency, amount }) => formatPrice(amount, currency))
    .join(" · ") || "—";
  const periodRevenueSummary = analytics.data?.period_sales?.revenue_by_currency
    .map(({ currency, amount }) => formatPrice(amount, currency))
    .join(" · ") || "—";

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <SectionHeading title="Tableau de bord vendeur" t={t} />
          {activeSection === "products" && (
            <Link
              to="/vendeur/annonces/nouvelle"
              className="flex items-center gap-2 rounded-full bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              <Plus className="h-4 w-4" /> Nouvelle annonce
            </Link>
          )}
        </div>

        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <StatCard icon={Package} label="Annonces" value={analytics.data?.products.total ?? "—"} t={t} />
          <StatCard icon={TrendingUp} label="Publiées" value={analytics.data?.products.published ?? "—"} t={t} />
          <StatCard icon={ShoppingBag} label="Produits vendus · période" value={analytics.data?.period_sales?.products_sold ?? "—"} t={t} />
          <StatCard icon={Package} label="Unités vendues · période" value={analytics.data?.period_sales?.units ?? "—"} t={t} />
          <StatCard icon={ShoppingBag} label="Commandes reçues · période" value={analytics.data?.period_sales?.orders_received ?? "—"} t={t} />
          <StatCard icon={ShoppingBag} label="Commandes en cours" value={analytics.data?.sales.orders_pending ?? "—"} t={t} />
          <StatCard icon={Eye} label="Vues cumulées" value={analytics.data?.products.views ?? "—"} t={t} />
          <StatCard icon={Heart} label="Ajouts aux favoris" value={analytics.data?.products.favorites ?? "—"} t={t} />
          <StatCard icon={ShoppingBag} label="Ajouts au panier" value={analytics.data?.products.cart_adds ?? "—"} t={t} />
          <StatCard icon={Star} label="Note moyenne" value={analytics.data ? `${Number(analytics.data.reviews.average).toFixed(1)} / 5` : "—"} t={t} />
          <StatCard icon={TrendingUp} label="Conversion des visites" value={analytics.data?.conversion_rate == null ? "—" : `${analytics.data.conversion_rate}%`} t={t} />
          <StatCard icon={TrendingUp} label="Transactions réussies" value={analytics.data?.transactions.successful ?? "—"} t={t} />
          {analytics.data?.transactions.pending > 0 && (
            <StatCard icon={ShoppingBag} label="Paiements en attente" value={analytics.data.transactions.pending} t={t} />
          )}
          {wallet && <StatCard icon={TrendingUp} label="Solde disponible" value={formatPrice(wallet.balance, wallet.currency)} t={t} />}
        </div>

        {analytics.error && <div className="mb-6"><ErrorBlock message={analytics.error} t={t} /></div>}
        <section className={cx("mb-8 border-y py-5", t.border)} aria-labelledby="seller-analytics-title">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id="seller-analytics-title" className={cx("text-lg font-semibold", t.textPrimary)}>Activité commerciale</h2>
              <p className={cx("mt-1 text-sm", t.textMuted)}>Ventes confirmées, regroupées par période.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <label className={cx("flex items-center gap-2 text-sm", t.textMuted)}>
                Mesure
                <select value={chartMetric} onChange={(event) => setChartMetric(event.target.value)} className={cx("rounded-lg border px-3 py-2", t.border, t.cardBg, t.textPrimary)}>
                  <option value="units">Articles vendus</option>
                  <option value="orders">Commandes</option>
                  <option value="revenue">Chiffre d’affaires</option>
                </select>
              </label>
              {chartMetric === "revenue" && revenueCurrencies.length > 1 && (
                <label className={cx("flex items-center gap-2 text-sm", t.textMuted)}>
                  Devise
                  <select value={selectedChartCurrency} onChange={(event) => setChartCurrency(event.target.value)} className={cx("rounded-lg border px-3 py-2", t.border, t.cardBg, t.textPrimary)}>
                    {revenueCurrencies.map((currency) => <option key={currency} value={currency}>{currency}</option>)}
                  </select>
                </label>
              )}
              <label className={cx("flex items-center gap-2 text-sm", t.textMuted)}>
                Période
                <select value={period} onChange={(event) => setPeriod(event.target.value)} className={cx("rounded-lg border px-3 py-2", t.border, t.cardBg, t.textPrimary)}>
                  <option value="daily">Quotidienne · 30 jours</option>
                  <option value="weekly">Hebdomadaire · 12 semaines</option>
                  <option value="monthly">Mensuelle · 12 mois</option>
                  <option value="yearly">Annuelle · 5 ans</option>
                </select>
              </label>
            </div>
          </div>
          {analytics.loading ? (
            <LoadingBlock t={t} />
          ) : chartSeries.length === 0 ? (
            <p className={cx("py-10 text-center text-sm", t.textMuted)}>Aucune vente livrée sur cette période.</p>
          ) : (
            <div className="flex h-44 items-end gap-2 overflow-x-auto border-b px-1" role="img" aria-label={`${chartMetric} par période`}>
              {chartSeries.map((bucket) => (
                <div key={bucket.date} className="flex h-full min-w-10 flex-1 flex-col items-center justify-end gap-2 pb-2">
                  <span className={cx("text-[10px] font-medium", t.textMuted)}>{chartMetric === "revenue" ? formatPrice(bucket.revenue, bucket.currency) : bucket[chartMetric]}</span>
                  <div
                    className="w-full max-w-10 rounded-t-sm bg-emerald-500/80"
                    style={{ height: `${Math.max(6, (Number(chartMetric === "revenue" ? bucket.revenue : bucket[chartMetric]) / maxChartValue) * 78)}%` }}
                    title={chartMetric === "revenue" ? formatPrice(bucket.revenue, bucket.currency) : `${bucket[chartMetric]} ${chartMetric === "units" ? "article(s)" : "commande(s)"}`}
                  />
                  <span className={cx("whitespace-nowrap text-[10px]", t.textMuted)}>
                    {new Intl.DateTimeFormat("fr", { day: "numeric", month: "short" }).format(new Date(bucket.date))}
                  </span>
                </div>
              ))}
            </div>
          )}
          <p className={cx("mt-4 text-sm", t.textMuted)}>
            Chiffre d’affaires confirmé sur la période : <span className={cx("font-semibold", t.textPrimary)}>{periodRevenueSummary}</span>
            <span className="mx-2">·</span>
            Cumulé : <span className={cx("font-semibold", t.textPrimary)}>{revenueSummary}</span>
          </p>
          {analytics.data?.transactions.pending_by_currency?.length > 0 && (
            <p className={cx("mt-2 text-sm", t.textMuted)}>
              Paiements retenus : <span className={cx("font-semibold", t.textPrimary)}>
                {analytics.data.transactions.pending_by_currency.map(({ currency, amount }) => formatPrice(amount, currency)).join(" · ")}
              </span>
            </p>
          )}
          {(analytics.data?.products.low_stock > 0 || analytics.data?.products.low_stock_variants > 0) && (
            <p className="mt-2 text-sm font-medium text-amber-700">
              {analytics.data.products.low_stock} annonce(s) et {analytics.data.products.low_stock_variants} variante(s) ont un stock faible.
            </p>
          )}
          {analytics.data && (
            <p className={cx("mt-2 text-xs", t.textMuted)}>
              {analytics.data.sales.orders} commandes livrées · {analytics.data.reviews.count} avis vérifiés
              {analytics.data.conversion_rate === null && " · Taux de conversion indisponible sans historique des visites uniques"}
            </p>
          )}
        </section>

        {analytics.data && (
          <div className="mb-10 grid gap-8 sm:grid-cols-2">
            {[
              { title: "Les plus consultées", items: analytics.data.sales.top_viewed, metric: (item) => `${item.views_count} vues`, key: "views_count" },
              { title: "Les plus vendues", items: analytics.data.sales.top_products, metric: (item) => `${item.units} vendu(s)`, key: "units" },
            ].map((list) => (
              <section key={list.title} aria-label={list.title}>
                <h2 className={cx("mb-3 text-sm font-semibold", t.textPrimary)}>{list.title}</h2>
                {list.items.length === 0 ? (
                  <p className={cx("text-sm", t.textMuted)}>Pas encore de données.</p>
                ) : (
                  <ol className={cx("divide-y border-y", t.border)}>
                    {list.items.map((item) => (
                      <li key={`${list.key}-${item.product_id || item.id}-${item.product_title || item.title}`} className="flex justify-between gap-3 py-2.5 text-sm">
                        <span className={cx("truncate", t.textPrimary)}>{item.product_title || item.title}</span>
                        <span className={cx("shrink-0 text-xs", t.textMuted)}>{list.metric(item)}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </section>
            ))}
          </div>
        )}

        <div className={cx("mb-6 grid w-full max-w-2xl grid-cols-2 gap-1 rounded-xl border p-1 sm:flex", t.border, t.cardBg)} role="tablist" aria-label="Contenu du tableau vendeur">
          <button
            type="button"
            role="tab"
            aria-selected={activeSection === "products"}
            onClick={() => setActiveSection("products")}
            className={cx("flex-1 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors", activeSection === "products" ? "bg-indigo-600 text-white" : t.textMuted)}
          >
            Mes annonces ({stats.total})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeSection === "sales"}
            onClick={() => setActiveSection("sales")}
            className={cx("flex-1 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors", activeSection === "sales" ? "bg-indigo-600 text-white" : t.textMuted)}
          >
            Mes ventes ({sales.items.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeSection === "verification"}
            onClick={() => setActiveSection("verification")}
            className={cx("flex-1 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors", activeSection === "verification" ? "bg-indigo-600 text-white" : t.textMuted)}
          >
            Vérification
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeSection === "localization"}
            onClick={() => setActiveSection("localization")}
            className={cx("flex-1 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors", activeSection === "localization" ? "bg-indigo-600 text-white" : t.textMuted)}
          >
            Localisation & livraison
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeSection === "promotions"}
            onClick={() => setActiveSection("promotions")}
            className={cx("flex-1 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors", activeSection === "promotions" ? "bg-indigo-600 text-white" : t.textMuted)}
          >
            Promotions
          </button>
        </div>

        {activeSection === "promotions" ? (
          <SellerPromotionsPanel t={t} />
        ) : activeSection === "localization" ? (
          <SellerLocalizationPanel t={t} />
        ) : activeSection === "verification" ? (
          <VerificationPanel t={t} isProfessional={user?.seller_type === "professional"} />
        ) : activeSection === "products" ? (
        <div className="mb-12">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <SectionHeading title="Mes annonces" t={t} />
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className={cx("rounded-xl border px-3 py-2 text-sm", t.border, t.cardBg, t.textPrimary)}
              aria-label="Filtrer mes annonces"
            >
              <option value="all">Toutes les annonces</option>
              <option value="published">Publiées</option>
              <option value="draft">Brouillons</option>
              <option value="archived">Archivées</option>
            </select>
          </div>
          {products.loading ? (
            <LoadingBlock t={t} />
          ) : products.error ? (
            <ErrorBlock message={products.error} t={t} />
          ) : visibleProducts.length === 0 ? (
            <p className={cx("text-sm", t.textMuted)}>
              Aucune annonce pour l'instant.{" "}
              <Link to="/vendeur/annonces/nouvelle" className="font-semibold text-indigo-600 hover:underline">
                Publier la première
              </Link>
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {visibleProducts.map((p) => (
                <div key={p.id} className={cx("rounded-xl border", t.cardBorder, t.cardBg)}>
                <div className="flex flex-wrap items-center gap-4 p-4">
                  <span className={cx("rounded-full px-3 py-1 text-xs font-semibold", STATUS_STYLES[p.status])}>
                    {STATUS_LABELS[p.status] || p.status}
                  </span>
                  {p.status === "published" && p.moderation_status !== "approved" && (
                    <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">
                      {MODERATION_LABELS[p.moderation_status] || "À valider"}
                    </span>
                  )}
                  <span className={cx("min-w-35 flex-1 truncate text-sm font-medium", t.textPrimary)}>{p.title}</span>
                  <span className="font-mono text-sm">{formatPrice(p.price, p.currency)}</span>
                  <span className={cx("flex items-center gap-1 text-xs", t.textMuted)}>
                    <Eye className="h-3 w-3" /> {p.views_count}
                  </span>
                  <span className={cx("flex items-center gap-1 text-xs", t.textMuted)}>
                    <Heart className="h-3 w-3" /> {p.favorites_count}
                  </span>
                  {p.item_type === "product" && (
                    <span className={cx("text-xs", p.stock_quantity > 0 && p.stock_quantity <= 3 ? "font-semibold text-amber-700" : t.textMuted)}>
                      Stock : {p.stock_quantity}
                    </span>
                  )}
                  {p.item_type === "product" && (
                    <button type="button" onClick={() => toggleStockHistory(p.id)} className="text-xs font-semibold text-indigo-600 hover:underline">
                      {openStockHistory === p.id ? "Masquer l’historique" : "Historique du stock"}
                    </button>
                  )}
                  <Link to={`/vendeur/annonces/${p.id}/modifier`} className={cx("rounded-full border p-2", t.border)} aria-label="Modifier">
                    <Pencil className="h-3.5 w-3.5" />
                  </Link>
                  <button
                    onClick={() => handleDelete(p)}
                    className="rounded-full border border-rose-200 p-2 text-rose-500 hover:bg-rose-50"
                    aria-label="Supprimer"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
                {openStockHistory === p.id && (
                  <div className={cx("border-t px-4 py-3", t.border)}>
                    {stockHistory[p.id]?.loading ? (
                      <p className={cx("text-xs", t.textMuted)}>Chargement de l’historique…</p>
                    ) : stockHistory[p.id]?.error ? (
                      <p className="text-xs text-rose-600">{stockHistory[p.id].error}</p>
                    ) : stockHistory[p.id]?.items.length ? (
                      <ul className="flex flex-col gap-2">
                        {stockHistory[p.id].items.map((movement) => (
                          <li key={movement.id} className={cx("flex flex-wrap justify-between gap-2 text-xs", t.textMuted)}>
                            <span>{movement.movement_type.replaceAll("_", " ")}{movement.variant_label ? ` · ${movement.variant_label}` : ""} · {movement.actor_username || "Système"}</span>
                            <span>{movement.quantity_delta > 0 ? "+" : ""}{movement.quantity_delta} · {new Date(movement.created_at).toLocaleDateString("fr")}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className={cx("text-xs", t.textMuted)}>Aucun mouvement enregistré.</p>
                    )}
                  </div>
                )}
                </div>
              ))}
            </div>
          )}
        </div>
        ) : (
        <div>
          <SectionHeading title="Mes ventes" t={t} />
          {sales.loading ? (
            <LoadingBlock t={t} />
          ) : sales.error ? (
            <ErrorBlock message={sales.error} t={t} />
          ) : sales.items.length === 0 ? (
            <p className={cx("text-sm", t.textMuted)}>Aucune vente pour l'instant.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {sortedSales.map((item) => (
                <div key={item.id} className={cx("flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4 text-sm", t.cardBorder, t.cardBg)}>
                  <div className="min-w-35 flex-1">
                    <p className={cx("font-medium", t.textPrimary)}>{item.product_title}{item.variant_label ? ` · ${item.variant_label}` : ""} × {item.quantity}</p>
                    {item.shipping_address && (
                      <p className={cx("mt-1 flex items-start gap-1 text-xs", t.textMuted)}>
                        <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span className="wrap-break-word">{item.shipping_address}</span>
                      </p>
                    )}
                  </div>
                  <span className={cx("text-xs", t.textMuted)}>
                    {item.order_status === "pending" && item.payment_method === "cash"
                      ? item.sale_method === "delivery" ? "En attente d’expédition" : "En attente de remise"
                      : item.order_status}
                  </span>
                  <span className="font-mono">{formatPrice(item.subtotal, item.currency)}</span>
                  {item.order_status === "pending" && item.payment_method === "cash" && item.sale_method === "delivery" && !item.is_shipped && (
                    <button
                      type="button"
                      onClick={() => handleMarkShipped(item)}
                      disabled={busySaleId === item.id}
                      className="rounded-full bg-indigo-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-60"
                    >
                      Marquer expédiée
                    </button>
                  )}
                  {["delivered", "cancelled"].includes(item.order_status) && (
                    <button
                      type="button"
                      onClick={() => handleDeleteSale(item)}
                      disabled={busySaleId === item.id}
                      aria-label={`Retirer la vente ${item.product_title} de la liste`}
                      className={cx("rounded-full border p-2 disabled:opacity-60", t.border, t.textMuted, "hover:border-rose-300 hover:text-rose-600")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
