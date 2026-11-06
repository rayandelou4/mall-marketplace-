import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Plus, Pencil, Trash2, Eye, Heart, Package, TrendingUp, MapPin } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { StatCard } from "../components/ui/StatCard";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { fetchMyProducts, deleteProduct, fetchMySales, fetchConfirmedSalesCount, deleteSale } from "../features/seller/api";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";
import { VerificationPanel } from "../components/seller/VerificationPanel";
import { SellerLocalizationPanel } from "../components/seller/SellerLocalizationPanel";

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
  const [confirmedSalesCount, setConfirmedSalesCount] = useState(0);
  const [statusFilter, setStatusFilter] = useState("all");
  const [activeSection, setActiveSection] = useState("products");
  const [busySaleId, setBusySaleId] = useState(null);

  useEffect(() => {
    const section = searchParams.get("section");
    setActiveSection(["sales", "verification", "localization"].includes(section) ? section : "products");
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
    fetchConfirmedSalesCount().then((result) => setConfirmedSalesCount(result.count)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

        <div className="mb-10 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard icon={Package} label="Annonces" value={stats.total} t={t} />
          <StatCard icon={TrendingUp} label="Publiées" value={stats.published} t={t} />
          <StatCard icon={Eye} label="Vues cumulées" value={stats.views} t={t} />
          <StatCard icon={TrendingUp} label="Ventes confirmées" value={confirmedSalesCount} t={t} />
        </div>

        <div className={cx("mb-6 flex w-full max-w-2xl rounded-xl border p-1", t.border, t.cardBg)} role="tablist" aria-label="Contenu du tableau vendeur">
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
        </div>

        {activeSection === "localization" ? (
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
                <div key={p.id} className={cx("flex flex-wrap items-center gap-4 rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
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
                    <p className={cx("font-medium", t.textPrimary)}>{item.product_title} × {item.quantity}</p>
                    {item.shipping_address && (
                      <p className={cx("mt-1 flex items-start gap-1 text-xs", t.textMuted)}>
                        <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span className="wrap-break-word">{item.shipping_address}</span>
                      </p>
                    )}
                  </div>
                  <span className={cx("text-xs", t.textMuted)}>{item.order_status === "pending" && item.payment_method === "cash" ? "En attente de remise" : item.order_status}</span>
                  <span className="font-mono">{formatPrice(item.subtotal, item.currency)}</span>
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
