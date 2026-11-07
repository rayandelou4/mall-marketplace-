import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Heart, MapPin, MessageCircle, ShoppingCart, Star, ImageOff } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { ProductCard } from "../components/catalog/ProductCard";
import { LoadingBlock, ErrorBlock, SectionHeading } from "../components/ui/StatusBlocks";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { useCart } from "../features/cart/CartContext";
import { fetchProduct, fetchComparisons, toggleFavorite } from "../features/catalog/api";
import { fetchReviews } from "../features/reviews/api";
import { createReport } from "../features/moderation/api";
import { ModerationMessageForm } from "../components/ui/ModerationMessageForm";
import { PRODUCT_REPORT_REASONS } from "../features/moderation/formOptions";
import { formatPrice } from "../lib/format";
import { optimizedImageUrl } from "../lib/cloudinary";
import { createWhatsAppUrl } from "../lib/whatsapp";
import { cx } from "../styles/theme";

function loadComparisonPage(productId, page, setComparisonState) {
  setComparisonState((current) => ({ ...current, loading: true, error: null }));
  fetchComparisons(productId, { page })
    .then((data) => setComparisonState((current) => ({
      ...current,
      ...data,
      loading: false,
      error: null,
      similar: data.similar?.length ? data.similar : current.similar,
    })))
    .catch((error) => setComparisonState((current) => ({ ...current, loading: false, error: error.message })));
}

export default function ProductPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();
  const { addItem } = useCart();

  const [state, setState] = useState({ loading: true, error: null, product: null });
  const [comparisonState, setComparisonState] = useState({ loading: false, error: null, exact: null, similar: [] });
  const [reviews, setReviews] = useState([]);
  const [activeImage, setActiveImage] = useState(0);
  const [actionNotice, setActionNotice] = useState(null);
  const [contactOptionsOpen, setContactOptionsOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportSending, setReportSending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, error: null, product: null });
    setActiveImage(0);
    setComparisonState({ loading: false, error: null, exact: null, similar: [] });

    fetchProduct(id)
      .then((product) => {
        if (cancelled) return;
        setState({ loading: false, error: null, product });
        fetchReviews({ user: product.seller_username })
          .then((items) => !cancelled && setReviews(items))
          .catch(() => {});
        if (product.item_type !== "service") {
          loadComparisonPage(id, 1, (nextState) => {
            if (!cancelled) setComparisonState(nextState);
          });
        }
      })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err.message, product: null });
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  async function handleFavorite() {
    if (!isAuthenticated) return navigate("/auth");
    try {
      await toggleFavorite(id);
      setActionNotice("Ajouté aux favoris.");
    } catch (err) {
      setActionNotice(err.message);
    }
  }

  function handleAddToCart() {
    if (product.status === "archived") {
      setActionNotice("Cette annonce est archivée et n'est plus disponible.");
      return;
    }
    if (product.item_type === "service") return setContactOptionsOpen((open) => !open);
    if (!product.is_available) {
      setActionNotice("Cette annonce n'est pas disponible à l'achat.");
      return;
    }
    addItem(product, 1);
    setActionNotice("Ajouté au panier.");
  }

  function handleContact() {
    setContactOptionsOpen(false);
    if (!isAuthenticated) return navigate("/auth");
    navigate("/messages", {
      state: { startWith: { username: product.seller_username, productId: product.id, productTitle: product.title, phoneNumber: product.seller_phone_number } },
    });
  }

  function handleWhatsAppContact() {
    setContactOptionsOpen(false);
    if (!isAuthenticated) return navigate("/auth");
    if (!whatsappUrl) {
      setActionNotice("Le vendeur n'a pas fourni de numéro WhatsApp valide.");
      return;
    }
    window.open(whatsappUrl, "_blank", "noopener,noreferrer");
  }

  const { loading, error, product } = state;
  const { exact: exactComparison, similar: similarProducts, loading: comparisonsLoading, error: comparisonsError } = comparisonState;
  const canBuy = product?.status === "published" && product?.is_available;
  const productUrl = product ? `${window.location.origin}/produit/${product.id}` : "";
  const shareText = product ? `Je viens de trouver cette annonce sur Easy Mall : ${product.title} • ${formatPrice(product.price, product.currency)}` : "";
  const whatsappShareUrl = product ? `https://wa.me/?text=${encodeURIComponent(`${shareText} ${productUrl}`)}` : "";
  const facebookShareUrl = product ? `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(productUrl)}` : "";
  const whatsappUrl = product && createWhatsAppUrl(
    product.seller_phone_number,
    `Bonjour, je vous contacte au sujet de votre annonce « ${product.title} » sur Easy Mall.`,
  );

  useEffect(() => {
    if (!product) return;

    document.title = `${product.title} | Easy Mall`;

    const ensureMeta = (selector, attributes) => {
      let tag = document.head.querySelector(selector);
      if (!tag) {
        tag = document.createElement("meta");
        document.head.appendChild(tag);
      }
      Object.entries(attributes).forEach(([key, value]) => tag.setAttribute(key, value));
      return tag;
    };

    ensureMeta('meta[name="description"]', {
      name: "description",
      content: product.description ? `${product.title} — ${product.description.slice(0, 160)}` : `${product.title} sur Easy Mall`,
    });
    ensureMeta('meta[property="og:title"]', {
      property: "og:title",
      content: product.title,
    });
    ensureMeta('meta[property="og:description"]', {
      property: "og:description",
      content: product.description ? product.description.slice(0, 200) : "Découvrez cette annonce sur Easy Mall.",
    });
    ensureMeta('meta[property="og:url"]', {
      property: "og:url",
      content: productUrl,
    });
    if (product.images?.[0]?.image_url) {
      ensureMeta('meta[property="og:image"]', {
        property: "og:image",
        content: product.images[0].image_url,
      });
    }
  }, [product, productUrl]);

  async function handleCopyShareLink() {
    if (!productUrl) return;
    try {
      await navigator.clipboard.writeText(productUrl);
      setActionNotice("Lien de l’annonce copié. Vous pouvez le coller dans WhatsApp, Facebook ou Instagram.");
    } catch {
      setActionNotice("Copie impossible dans ce navigateur. Vous pouvez copier manuellement le lien ci-dessous.");
    }
  }

  async function handleSubmitReport({ reason, description }) {
    if (!isAuthenticated) return navigate("/auth");
    if (!product) return;
    try {
      setReportSending(true);
      await createReport({
        product_id: product.id,
        reason,
        description,
      });
      setReportOpen(false);
      setActionNotice("Signalement envoyé au modérateur. Un examen sera effectué.");
    } catch (err) {
      setActionNotice(err.message);
    } finally {
      setReportSending(false);
    }
  }

  const contactOptions = contactOptionsOpen && (
    <div role="menu" className={cx("absolute right-0 top-full z-20 mt-2 flex min-w-56 flex-col overflow-hidden rounded-xl border p-1 shadow-lg", t.cardBorder, t.cardBg)}>
      <button type="button" role="menuitem" onClick={handleContact} className={cx("rounded-lg px-3 py-2.5 text-left text-sm hover:bg-black/5 dark:hover:bg-white/5", t.textPrimary)}>
        Message sur Easy Mall
      </button>
      <button type="button" role="menuitem" onClick={handleWhatsAppContact} className="rounded-lg px-3 py-2.5 text-left text-sm text-emerald-700 hover:bg-emerald-50 dark:text-emerald-300 dark:hover:bg-emerald-950">
        WhatsApp direct
      </button>
    </div>
  );

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        {loading ? (
          <LoadingBlock t={t} label="Chargement de l'annonce…" />
        ) : error ? (
          <ErrorBlock message={error} t={t} />
        ) : product ? (
          <>
            <div className="grid gap-10 lg:grid-cols-2">
              <div>
                <div className={cx("aspect-square overflow-hidden rounded-2xl border", t.cardBorder)}>
                  {product.images?.length ? (
                    <img src={optimizedImageUrl(product.images[activeImage]?.image_url, 1400)} alt={product.title} decoding="async" className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-indigo-400 to-violet-600">
                      <ImageOff className="h-10 w-10 text-white/80" strokeWidth={1.5} />
                    </div>
                  )}
                </div>
                {product.images?.length > 1 && (
                  <div className="mt-3 flex gap-2">
                    {product.images.map((img, i) => (
                      <button
                        key={img.id}
                        onClick={() => setActiveImage(i)}
                        className={cx("h-16 w-16 overflow-hidden rounded-xl border-2", i === activeImage ? "border-indigo-600" : t.cardBorder)}
                      >
                        <img src={optimizedImageUrl(img.image_url, 180)} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" />
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <h1 className="text-2xl font-semibold sm:text-3xl">{product.title}</h1>
                <p className={cx("mt-1 flex flex-wrap items-center gap-3 text-sm", t.textMuted)}>
                  <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" /> {product.city}</span>
                  {product.item_type !== "service" && <span>{product.condition_display}</span>}
                  <span>{product.category_name}</span>
                </p>
                <p className="mt-4 font-mono text-3xl font-semibold">
                  {formatPrice(product.price, product.currency)}
                  {product.item_type === "service" && product.price_unit !== "fixed" ? <span className="ml-2 text-base font-normal">{product.price_unit_display?.toLowerCase()}</span> : null}
                </p>
                {product.status === "archived" && (
                  <p className="mt-2 text-sm font-semibold text-amber-700">Annonce archivée : consultation uniquement, achat indisponible.</p>
                )}
                {product.item_type !== "service" && (
                  <p className={cx("mt-1 text-sm", t.textMuted)}>
                    {product.sale_method === "pickup"
                      ? "Remise en main propre avec le vendeur"
                      : `Livraison${Number(product.shipping_cost) > 0 ? ` : ${formatPrice(product.shipping_cost, product.currency)}` : ""}`}
                  </p>
                )}

                <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                  {product.item_type === "service" ? (
                    <div className="relative flex-1">
                      <button type="button" onClick={handleAddToCart} disabled={product.status === "archived"} aria-haspopup="menu" aria-expanded={contactOptionsOpen} className="flex w-full items-center justify-center gap-2 rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50">
                        <MessageCircle className="h-4 w-4" /> Contacter pour réserver
                      </button>
                      {contactOptions}
                    </div>
                  ) : (
                    <>
                      <button onClick={handleAddToCart} disabled={product.status === "archived" || !canBuy} className="flex flex-1 items-center justify-center gap-2 rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50">
                        <ShoppingCart className="h-4 w-4" /> Ajouter au panier
                      </button>
                      <div className="relative">
                        <button type="button" onClick={() => setContactOptionsOpen((open) => !open)} aria-haspopup="menu" aria-expanded={contactOptionsOpen} className={cx("flex w-full items-center justify-center gap-2 rounded-full border px-6 py-3 text-sm font-semibold", t.border)}>
                          <MessageCircle className="h-4 w-4" /> Contacter
                        </button>
                        {contactOptions}
                      </div>
                    </>
                  )}
                  <button onClick={handleFavorite} className={cx("flex items-center justify-center gap-2 rounded-full border px-6 py-3 text-sm font-semibold", t.border)}>
                    <Heart className="h-4 w-4" /> Favoris
                  </button>
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => (isAuthenticated ? setReportOpen((value) => !value) : navigate("/auth"))}
                    className="rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-xs font-semibold text-amber-700 hover:bg-amber-100 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300"
                  >
                    Signaler l’annonce
                  </button>
                </div>

                {reportOpen && (
                  <ModerationMessageForm
                    t={t}
                    reasons={PRODUCT_REPORT_REASONS}
                    defaultReason="misleading_description"
                    submitLabel="Envoyer le signalement"
                    loading={reportSending}
                    onSubmit={handleSubmitReport}
                    onCancel={() => setReportOpen(false)}
                  />
                )}

                <div className={cx("mt-5 rounded-2xl border p-3", t.cardBorder)}>
                  <p className={cx("mb-2 text-xs font-semibold uppercase tracking-[0.16em]", t.textMuted)}>Partager l’annonce</p>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={handleCopyShareLink} className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 dark:border-indigo-900 dark:bg-indigo-950 dark:text-indigo-300">
                      Copier le lien
                    </button>
                    <a href={whatsappShareUrl} target="_blank" rel="noreferrer" className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300">
                      WhatsApp
                    </a>
                    <a href={facebookShareUrl} target="_blank" rel="noreferrer" className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-300">
                      Facebook
                    </a>
                    <a href="https://www.instagram.com/" target="_blank" rel="noreferrer" className="rounded-full border border-pink-200 bg-pink-50 px-3 py-1.5 text-xs font-semibold text-pink-700 hover:bg-pink-100 dark:border-pink-900 dark:bg-pink-950 dark:text-pink-300">
                      Instagram
                    </a>
                  </div>
                  <p className={cx("mt-2 break-all text-[11px]", t.textMuted)}>{productUrl}</p>
                </div>

                {actionNotice && <p className={cx("mt-3 text-sm", t.textMuted)}>{actionNotice}</p>}

                <div className={cx("mt-6 rounded-2xl border p-4 text-sm", t.cardBorder, t.textPrimary)}>{product.description}</div>

                <Link to={`/vendeurs/${product.seller_username}`} className={cx("mt-6 flex items-center gap-3 rounded-2xl border p-4 transition hover:border-indigo-400", t.cardBorder)}>
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600 text-sm font-semibold text-white">
                    {product.seller_username?.charAt(0)?.toUpperCase()}
                  </span>
                  <span>
                    <span className={cx("block text-sm font-semibold", t.textPrimary)}>{product.seller_username}</span>
                    <span className={cx("flex items-center gap-1 text-xs", t.textMuted)}>
                      <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                      {Number(product.seller_rating || 0).toFixed(1)} ({reviews.length} avis) · {product.seller_total_sales} vente{product.seller_total_sales > 1 ? "s" : ""}
                    </span>
                  </span>
                </Link>
              </div>
            </div>

            {reviews.length > 0 && (
              <div className="mt-14">
                <SectionHeading title={`Avis sur ce vendeur (${reviews.length})`} t={t} />
                <div className="flex flex-col gap-3">
                  {reviews.slice(0, 5).map((r) => (
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
              </div>
            )}

            {product.item_type === "product" && (
              <div className="mt-14">
                <SectionHeading
                  title="Comparateur de prix"
                  subtitle="Les offres exactes reposent sur une référence produit validée. Les prix sont comparés uniquement dans la même devise."
                  t={t}
                />
                {comparisonsLoading && <p className={cx("py-3 text-sm", t.textMuted)}>Chargement des offres…</p>}
                {comparisonsError && (
                  <div className="flex items-center gap-3 py-3">
                    <p role="alert" className="text-sm text-rose-600">{comparisonsError}</p>
                    <button type="button" onClick={() => loadComparisonPage(id, 1, setComparisonState)} className="text-sm font-semibold text-indigo-600">Réessayer</button>
                  </div>
                )}

                {exactComparison?.identity ? (
                  <section className={cx("mt-4 rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h2 className={cx("font-semibold", t.textPrimary)}>{exactComparison.identity.name}</h2>
                        <p className={cx("mt-1 text-xs", t.textMuted)}>
                          {exactComparison.offer_count} offre{exactComparison.offer_count === 1 ? "" : "s"} · {exactComparison.seller_count} vendeur{exactComparison.seller_count === 1 ? "" : "s"} · {exactComparison.currency}
                        </p>
                      </div>
                      {exactComparison.lowest_price != null && (
                        <p className="font-mono text-sm font-semibold text-emerald-700">
                          Dès {formatPrice(exactComparison.lowest_price, exactComparison.currency)}
                        </p>
                      )}
                    </div>
                    {exactComparison.results?.length > 0 ? (
                      <div className="mt-4 flex flex-col divide-y">
                        {exactComparison.results.map((offer) => (
                          <Link key={offer.id} to={`/produit/${offer.id}`} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                            <div className="h-12 w-12 shrink-0 overflow-hidden rounded-lg bg-zinc-100">
                              {offer.primary_image ? <img src={optimizedImageUrl(offer.primary_image, 480)} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center"><ImageOff className="h-5 w-5 text-zinc-400" /></div>}
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className={cx("truncate text-sm font-medium", t.textPrimary)}>{offer.title}</p>
                              <p className={cx("text-xs", t.textMuted)}>
                                {offer.condition_display || "État non précisé"} · {offer.seller_username}{offer.city ? ` · ${offer.city}` : ""}
                              </p>
                              <p className={cx("text-xs", t.textMuted)}>
                                {offer.shipping_cost_known ? `Livraison : ${formatPrice(offer.shipping_cost, offer.currency)}` : "Frais de livraison à confirmer"}
                              </p>
                            </div>
                            <p className={cx("shrink-0 font-mono text-sm font-semibold", t.textPrimary)}>{formatPrice(offer.price, offer.currency)}</p>
                          </Link>
                        ))}
                      </div>
                    ) : <p className={cx("mt-4 text-sm", t.textMuted)}>Aucune offre disponible pour cette identité produit.</p>}
                    {(exactComparison.next || exactComparison.previous) && (
                      <div className="mt-4 flex justify-between border-t pt-3">
                        <button type="button" disabled={!exactComparison.previous || comparisonsLoading} onClick={() => loadComparisonPage(id, Math.max(1, Number(new URL(exactComparison.previous).searchParams.get("page") || 1)), setComparisonState)} className="text-sm font-semibold text-indigo-600 disabled:opacity-40">Précédent</button>
                        <button type="button" disabled={!exactComparison.next || comparisonsLoading} onClick={() => loadComparisonPage(id, Number(new URL(exactComparison.next).searchParams.get("page") || 2), setComparisonState)} className="text-sm font-semibold text-indigo-600 disabled:opacity-40">Suivant</button>
                      </div>
                    )}
                  </section>
                ) : !comparisonsLoading && !comparisonsError ? (
                  <p className={cx("mt-3 text-sm", t.textMuted)}>Aucune identité exacte n’a été validée pour cette annonce. Les offres ne sont pas regroupées sur la seule base de leur titre.</p>
                ) : null}

                {similarProducts?.length > 0 && (
                  <section className="mt-8">
                    <h2 className={cx("mb-3 text-base font-semibold", t.textPrimary)}>Alternatives similaires, non garanties identiques</h2>
                    <div className="flex flex-col gap-2">
                      {similarProducts.map((alternative) => (
                        <Link key={alternative.id} to={`/produit/${alternative.id}`} className={cx("flex items-center justify-between gap-3 rounded-xl border p-3", t.cardBorder, t.cardBg)}>
                          <span className={cx("min-w-0 truncate text-sm", t.textPrimary)}>{alternative.title} · {alternative.condition_display || "État non précisé"}</span>
                          <span className={cx("shrink-0 font-mono text-sm font-semibold", t.textPrimary)}>{formatPrice(alternative.price, alternative.currency)}</span>
                        </Link>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            )}
          </>
        ) : null}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
