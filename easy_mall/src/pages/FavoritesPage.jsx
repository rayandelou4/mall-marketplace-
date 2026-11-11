import React, { useEffect, useState } from "react";
import { Heart, Save, Trash2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { ProductCard } from "../components/catalog/ProductCard";
import { ErrorBlock, LoadingBlock, SectionHeading } from "../components/ui/StatusBlocks";
import { useAuth } from "../features/auth/AuthContext";
import {
  fetchFavorites,
  fetchSellerFavorites,
  removeFavorite,
  removeSellerFavorite,
  updateFavorite,
} from "../features/catalog/api";
import { useTheme } from "../features/theme/ThemeContext";
import { cx } from "../styles/theme";

export default function FavoritesPage() {
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("listings");
  const [targetDrafts, setTargetDrafts] = useState({});
  const [savingTargetId, setSavingTargetId] = useState(null);
  const [state, setState] = useState({
    loading: true,
    error: null,
    listings: [],
    sellers: [],
  });

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth");
      return;
    }
    let cancelled = false;
    Promise.all([fetchFavorites(), fetchSellerFavorites()])
      .then(([listings, sellers]) => {
        if (!cancelled) {
          setState({ loading: false, error: null, listings, sellers });
          setTargetDrafts(Object.fromEntries(listings.map((item) => [item.id, item.target_price || ""])));
        }
      })
      .catch((error) => {
        if (!cancelled) setState((current) => ({ ...current, loading: false, error: error.message }));
      });
    return () => { cancelled = true; };
  }, [isAuthenticated, navigate]);

  async function handleRemoveListing(favorite) {
    try {
      await removeFavorite(favorite.id);
      setState((current) => ({
        ...current,
        listings: current.listings.filter((item) => item.id !== favorite.id),
      }));
    } catch (error) {
      window.alert(error.message);
    }
  }

  async function handleRemoveSeller(favorite) {
    try {
      await removeSellerFavorite(favorite.id);
      setState((current) => ({
        ...current,
        sellers: current.sellers.filter((item) => item.id !== favorite.id),
      }));
    } catch (error) {
      window.alert(error.message);
    }
  }

  async function handleSaveTarget(favorite) {
    setSavingTargetId(favorite.id);
    try {
      const value = targetDrafts[favorite.id] ?? "";
      const updated = await updateFavorite(favorite.id, {
        target_price: value === "" ? null : value,
      });
      setState((current) => ({
        ...current,
        listings: current.listings.map((item) => item.id === favorite.id ? updated : item),
      }));
      setTargetDrafts((current) => ({ ...current, [favorite.id]: updated.target_price || "" }));
    } catch (error) {
      window.alert(error.message);
    } finally {
      setSavingTargetId(null);
    }
  }

  return (
    <div className={cx("min-h-screen", t.pageBg, t.textPrimary)}>
      <SiteHeader />
      <main className="mx-auto min-h-[65vh] max-w-7xl px-4 py-10 sm:px-6">
        <SectionHeading title="Mes favoris" subtitle="Retrouvez les annonces et vendeurs que vous suivez." t={t} />

        <div className={cx("mb-8 flex w-full max-w-lg rounded-xl border p-1", t.border, t.cardBg)} role="tablist" aria-label="Types de favoris">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "listings"}
            onClick={() => setActiveTab("listings")}
            className={cx("flex-1 rounded-lg px-4 py-2.5 text-sm font-semibold", activeTab === "listings" ? "bg-indigo-600 text-white" : t.textMuted)}
          >
            Annonces ({state.listings.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "sellers"}
            onClick={() => setActiveTab("sellers")}
            className={cx("flex-1 rounded-lg px-4 py-2.5 text-sm font-semibold", activeTab === "sellers" ? "bg-indigo-600 text-white" : t.textMuted)}
          >
            Vendeurs ({state.sellers.length})
          </button>
        </div>

        {state.loading ? (
          <LoadingBlock t={t} />
        ) : state.error ? (
          <ErrorBlock message={state.error} t={t} />
        ) : activeTab === "listings" ? (
          state.listings.length === 0 ? (
            <div className={cx("flex flex-col items-center gap-3 py-16 text-center", t.textMuted)}>
              <Heart className="h-8 w-8" />
              <p className="text-sm">Vous n’avez pas encore d’annonce favorite.</p>
              <Link to="/catalogue" className="text-sm font-semibold text-indigo-600 hover:underline">Explorer les annonces</Link>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {state.listings.map((favorite, index) => (
                <div key={favorite.id}>
                  <ProductCard product={favorite.product_detail} index={index} t={t} showSeller />
                  <div className={cx("mt-3 border-t pt-3", t.border)}>
                    <label className={cx("block text-xs font-medium", t.textPrimary)} htmlFor={`target-price-${favorite.id}`}>
                      M’alerter sous {favorite.product_detail.currency}
                    </label>
                    <div className="mt-1 flex gap-2">
                      <input
                        id={`target-price-${favorite.id}`}
                        type="number"
                        min="0"
                        step="0.01"
                        value={targetDrafts[favorite.id] ?? ""}
                        onChange={(event) => setTargetDrafts((current) => ({ ...current, [favorite.id]: event.target.value }))}
                        placeholder="Prix cible"
                        className={cx("min-w-0 flex-1 rounded-lg border px-3 py-2 text-sm", t.border, t.cardBg, t.textPrimary)}
                      />
                      <button
                        type="button"
                        onClick={() => handleSaveTarget(favorite)}
                        disabled={savingTargetId === favorite.id}
                        aria-label={`Enregistrer le prix cible pour ${favorite.product_detail.title}`}
                        className={cx("min-h-11 min-w-11 rounded-lg border", t.border, t.textPrimary, "disabled:opacity-50")}
                      >
                        <Save className="mx-auto h-4 w-4" />
                      </button>
                    </div>
                    {favorite.target_price != null && (
                      <p className={cx("mt-1 text-xs", t.textMuted)}>Alerte activée sous {favorite.target_price} {favorite.product_detail.currency}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveListing(favorite)}
                    className={cx("mt-2 inline-flex items-center gap-1.5 text-xs font-semibold", t.textMuted, "hover:text-rose-600")}
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Retirer des favoris
                  </button>
                </div>
              ))}
            </div>
          )
        ) : state.sellers.length === 0 ? (
          <div className={cx("flex flex-col items-center gap-3 py-16 text-center", t.textMuted)}>
            <Heart className="h-8 w-8" />
            <p className="text-sm">Vous ne suivez encore aucun vendeur.</p>
            <Link to="/catalogue" className="text-sm font-semibold text-indigo-600 hover:underline">Découvrir les vendeurs</Link>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {state.sellers.map((seller) => (
              <article key={seller.id} className={cx("flex items-center gap-3 rounded-xl border p-4", t.cardBorder, t.cardBg)}>
                <Link to={`/vendeurs/${seller.seller_username}`} className="flex min-w-0 flex-1 items-center gap-3">
                  {seller.seller_avatar_url ? (
                    <img src={seller.seller_avatar_url} alt={`Photo de ${seller.seller_username}`} className="h-12 w-12 shrink-0 rounded-full object-cover" />
                  ) : (
                    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-lg font-semibold text-white">
                      {seller.seller_username.charAt(0).toUpperCase()}
                    </span>
                  )}
                  <span className="min-w-0">
                    <span className={cx("block truncate text-sm font-semibold", t.textPrimary)}>{seller.seller_full_name}</span>
                    <span className={cx("block truncate text-xs", t.textMuted)}>@{seller.seller_username}{seller.city ? ` · ${seller.city}` : ""}</span>
                  </span>
                </Link>
                <button
                  type="button"
                  onClick={() => handleRemoveSeller(seller)}
                  aria-label={`Retirer ${seller.seller_username} des vendeurs favoris`}
                  className={cx("rounded-full border p-2", t.border, t.textMuted, "hover:border-rose-300 hover:text-rose-600")}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </article>
            ))}
          </div>
        )}
      </main>
      <SiteFooter t={t} />
    </div>
  );
}