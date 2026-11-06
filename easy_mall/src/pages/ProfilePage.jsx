import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { MapPin, Star, Package, ShoppingBag, Settings, Heart, MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { StatCard } from "../components/ui/StatCard";
import { ProductCard } from "../components/catalog/ProductCard";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { fetchPublicProfile } from "../features/profile/api";
import { addSellerFavorite, fetchProducts, fetchSellerFavorites, removeSellerFavorite } from "../features/catalog/api";
import { fetchReviews } from "../features/reviews/api";
import { cx } from "../styles/theme";
import { ProfilePhotoViewer } from "../components/ui/ProfilePhotoViewer";

export default function ProfilePage() {
  const { username } = useParams();
  const navigate = useNavigate();
  const { t } = useTheme();
  const { user, isAuthenticated } = useAuth();
  const [state, setState] = useState({ loading: true, error: null, profile: null, products: [], reviews: [], sellerFavorite: null, favoriteSaving: false });

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    const sellerFavoritesRequest = isAuthenticated
      ? fetchSellerFavorites()
      : Promise.resolve([]);
    Promise.all([
      fetchPublicProfile(username),
      fetchProducts({ seller: username }),
      fetchReviews({ user: username }),
      sellerFavoritesRequest,
    ])
      .then(([profile, products, reviews, sellerFavorites]) => {
        if (!cancelled) {
          setState({
            loading: false,
            error: null,
            profile,
            products,
            reviews,
            sellerFavorite: sellerFavorites.find((favorite) => favorite.seller_username === username) || null,
            favoriteSaving: false,
          });
        }
      })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err.message, profile: null, products: [], reviews: [], sellerFavorite: null, favoriteSaving: false });
      });
    return () => {
      cancelled = true;
    };
  }, [username, isAuthenticated]);

  async function handleToggleSellerFavorite() {
    if (!isAuthenticated) {
      navigate("/auth");
      return;
    }
    setState((current) => ({ ...current, favoriteSaving: true }));
    try {
      if (state.sellerFavorite) {
        await removeSellerFavorite(state.sellerFavorite.id);
        setState((current) => ({ ...current, sellerFavorite: null, favoriteSaving: false }));
      } else {
        const favorite = await addSellerFavorite(state.profile.id);
        setState((current) => ({ ...current, sellerFavorite: favorite, favoriteSaving: false }));
      }
    } catch (error) {
      setState((current) => ({ ...current, favoriteSaving: false }));
      window.alert(error.message);
    }
  }

  const { loading, error, profile, products, reviews } = state;

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        {loading ? (
          <LoadingBlock t={t} />
        ) : error ? (
          <ErrorBlock message={error} t={t} />
        ) : (
          <>
            <div
              className={cx(
                "flex flex-col items-center gap-4 rounded-2xl border p-8 text-center sm:flex-row sm:text-left",
                t.cardBorder,
                t.cardBg
              )}
            >
              {profile.avatar_url ? (
                <ProfilePhotoViewer
                  src={profile.avatar_url}
                  alt={`Photo de profil de ${profile.username}`}
                  title={`Photo de ${profile.full_name || profile.username}`}
                  showTriggerOverlay
                  className="h-20 w-20 shrink-0 overflow-hidden rounded-full ring-2 ring-white shadow-md"
                >
                  <img src={profile.avatar_url} alt="" className="h-full w-full object-cover" />
                </ProfilePhotoViewer>
              ) : (
                <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-3xl font-semibold text-white">
                  {profile.username.charAt(0).toUpperCase()}
                </div>
              )}
              <div>
                <h1 className={cx("text-2xl font-semibold", t.textPrimary)}>{profile.full_name || profile.username}</h1>
                <p className={cx("text-sm", t.textMuted)}>@{profile.username}</p>
                <p className={cx("mt-1 text-xs font-medium uppercase tracking-wide", t.textMuted)}>
                  {profile.seller_type_display || (profile.seller_type === "professional" ? "Commerçant professionnel" : "Particulier")}
                </p>
                {profile.verification_badges?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {profile.verification_badges.map((badge) => (
                      <span
                        key={badge.level}
                        title={badge.meaning}
                        className="rounded border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800"
                      >
                        {badge.label}
                      </span>
                    ))}
                  </div>
                )}
                {profile.shop_name && (
                  <p className={cx("mt-1 text-sm font-semibold text-indigo-600", t.textMuted)}>{profile.shop_name}</p>
                )}
                {profile.bio && <p className={cx("mt-2 text-sm", t.textMuted)}>{profile.bio}</p>}
                {profile.shop_description && <p className={cx("mt-2 text-sm", t.textMuted)}>{profile.shop_description}</p>}
                {(profile.public_location_display || profile.city) && (
                  <p className={cx("mt-1 flex items-center justify-center gap-1 text-xs sm:justify-start", t.textMuted)}>
                    <MapPin className="h-3 w-3" /> {profile.public_location_display || profile.city}
                  </p>
                )}
              </div>
              {user?.username === profile.username && (
                <Link
                  to="/parametres"
                  className={cx("ml-0 inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold sm:ml-auto", t.border, t.textPrimary)}
                >
                  <Settings className="h-4 w-4" /> Modifier mon profil
                </Link>
              )}
              {isAuthenticated && user?.username !== profile.username && (
                <div className="flex flex-wrap gap-2 sm:ml-auto">
                  <button
                    type="button"
                    onClick={() => navigate("/messages", { state: { startWith: { username: profile.username } } })}
                    className="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                  >
                    <MessageCircle className="h-4 w-4" /> Contacter
                  </button>
                  <button
                    type="button"
                    onClick={handleToggleSellerFavorite}
                    disabled={state.favoriteSaving}
                    className={cx(
                      "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold disabled:opacity-60",
                      t.border,
                      state.sellerFavorite ? "text-rose-600" : t.textPrimary
                    )}
                  >
                    <Heart className={cx("h-4 w-4", state.sellerFavorite && "fill-current")} />
                    {state.sellerFavorite ? "Retirer des favoris" : "Suivre ce vendeur"}
                  </button>
                </div>
              )}
            </div>

            <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatCard icon={Star} label="Note moyenne" value={Number(profile.average_rating || 0).toFixed(1)} t={t} />
              <StatCard icon={Package} label="Annonces publiées" value={products.length} t={t} />
              <StatCard icon={ShoppingBag} label="Ventes" value={profile.total_sales} t={t} />
              <StatCard icon={ShoppingBag} label="Achats" value={profile.total_purchases} t={t} />
            </div>

            <div className="mt-10">
              <SectionHeading title="Annonces publiées" t={t} />
              {products.length === 0 ? (
                <p className={cx("text-sm", t.textMuted)}>Aucune annonce publiée pour l'instant.</p>
              ) : (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  {products.map((p, i) => (
                    <ProductCard key={p.id} product={p} index={i} t={t} />
                  ))}
                </div>
              )}
            </div>

            <div className="mt-10">
              <SectionHeading title={`Avis reçus (${reviews.length})`} t={t} />
              {reviews.length === 0 ? (
                <p className={cx("text-sm", t.textMuted)}>Aucun avis reçu pour l'instant.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {reviews.map((r) => (
                    <div key={r.id} className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                      <div className="flex items-center justify-between">
                        <span className={cx("text-sm font-semibold", t.textPrimary)}>{r.reviewer_username}</span>
                        <span className="flex items-center gap-0.5 text-amber-400">
                          {Array.from({ length: 5 }).map((_, i) => (
                            <Star key={i} className={cx("h-3.5 w-3.5", i < r.rating && "fill-amber-400")} />
                          ))}
                        </span>
                      </div>
                      {r.comment && <p className={cx("mt-2 text-sm", t.textMuted)}>{r.comment}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
