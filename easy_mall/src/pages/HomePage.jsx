import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Star, MapPin, ShieldCheck, Truck, Users, ChevronDown, ChevronLeft, ChevronRight, Eye, Tag } from "lucide-react";
import { useTheme } from "../features/theme/ThemeContext";
import { fetchCategories, fetchProducts, toggleFavorite } from "../features/catalog/api";
import { useAuth } from "../features/auth/AuthContext";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { ProductCard } from "../components/catalog/ProductCard";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { cx } from "../styles/theme";

/** Pas d'endpoint dédié "vendeurs populaires" : déduits des produits déjà chargés. */
function deriveTopSellers(products) {
  const byUsername = new Map();
  products.forEach((p) => {
    if (p.seller_username && !byUsername.has(p.seller_username)) {
      byUsername.set(p.seller_username, {
        username: p.seller_username,
        avatar_url: p.seller_avatar_url,
        rating: p.seller_rating,
        city: p.city,
      });
    }
  });
  return [...byUsername.values()].sort((a, b) => Number(b.rating || 0) - Number(a.rating || 0)).slice(0, 4);
}

const TESTIMONIALS = [
  { name: "Grace W.", city: "Nairobi", quote: "J'ai vendu toute ma garde-robe en deux semaines, sans jamais quitter mon quartier." },
  { name: "Jean-Paul K.", city: "Abidjan", quote: "La remise organisée avec le vendeur via la messagerie, c'est exactement ce qui me manquait." },
  { name: "Fatou S.", city: "Dakar", quote: "J'ai pu vérifier les avis du vendeur avant d'acheter mon téléphone. Zéro stress." },
];

const FAQS = [
  { q: "Comment se passe le paiement ?", a: "Convenez de la remise avec le vendeur via la messagerie, puis payez en espèces en main propre au moment de la remise." },
  { q: "Quels moyens de paiement sont acceptés ?", a: "Pour le moment : espèces à la remise en main propre. Le paiement Mobile Money (M-Pesa, Orange Money, Airtel Money) arrive bientôt." },
  { q: "Comment un vendeur est-il vérifié ?", a: "Chaque vendeur confirme son adresse e-mail avant de pouvoir publier sa première annonce." },
  { q: "Que faire en cas de litige ?", a: "Signalez un litige depuis votre commande afin que notre équipe puisse examiner la situation." },
  { q: "Dans quels pays Mall est-il disponible ?", a: "Mall est disponible en RDC et s'étend progressivement à d'autres pays d'Afrique." },
  { q: "Comment publier une annonce ?", a: "Ajoutez jusqu'à 3 photos, un titre, un prix et une description : votre annonce est en ligne en quelques minutes." },
];

const STEPS = [
  { n: "01", title: "Publiez votre annonce", text: "Photos, prix, état, ville — en quelques minutes, votre article est visible par des milliers d'acheteurs." },
  { n: "02", title: "Discutez et négociez", text: "Répondez aux questions et fixez les détails de la remise ou de la livraison via la messagerie intégrée." },
  { n: "03", title: "Encaissez à la remise", text: "Remettez le produit ou réalisez la prestation, puis recevez le paiement en espèces en main propre." },
];

const HERO_FALLBACKS = [
  {
    src: "https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=2000&q=85",
    alt: "Personne portant une tenue proposée sur une marketplace",
    type: "Mode et accessoires",
  },
  {
    src: "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=2000&q=85",
    alt: "Chaussure proposée à la vente",
    type: "Articles du quotidien",
  },
  {
    src: "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=2000&q=85",
    alt: "Téléphone disponible parmi les annonces",
    type: "Électronique",
  },
  {
    src: "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?auto=format&fit=crop&w=2000&q=85",
    alt: "Professionnel dans son espace de travail",
    type: "Services près de chez vous",
  },
];

function buildHeroSlides(products, services) {
  const listings = [
    ...products.map((product) => ({
      src: product.primary_image,
      alt: product.title,
      type: product.category_name || "Produits",
    })),
    ...services.map((service) => ({
      src: service.primary_image,
      alt: service.title,
      type: service.category_name || "Services",
    })),
  ].filter((slide) => slide.src);

  return [...listings.slice(0, 4), ...HERO_FALLBACKS].slice(0, 5);
}

function ProductRail({ products, t, onToggleFavorite, showViews = false }) {
  const railRef = useRef(null);

  function scrollRail(direction) {
    railRef.current?.scrollBy({
      left: direction * railRef.current.clientWidth * 0.8,
      behavior: "smooth",
    });
  }

  return (
    <div className="group/rail relative">
      <button
        type="button"
        onClick={() => scrollRail(-1)}
        aria-label="Défiler vers la gauche"
        className={cx("absolute left-2 top-1/2 z-10 hidden -translate-y-1/2 rounded-full border p-2 shadow-md transition hover:scale-105 md:flex", t.cardBg, t.cardBorder, t.textPrimary)}
      >
        <ChevronLeft className="h-5 w-5" />
      </button>
      <div
        ref={railRef}
        className="flex snap-x snap-mandatory gap-4 overflow-x-auto overscroll-x-contain scroll-smooth pb-4"
      >
        {products.map((product, index) => (
          <div key={product.id} className="w-[min(78vw,18rem)] shrink-0 snap-start sm:w-56 lg:w-60">
            {showViews ? (
              <div className="relative">
                <ProductCard product={product} index={index} t={t} onToggleFavorite={onToggleFavorite} showSeller />
                <span className={cx("pointer-events-none absolute -top-2 right-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold", t.cardBg, t.cardBorder, t.textMuted)}>
                  <Eye className="h-3 w-3" /> {product.views_count}
                </span>
              </div>
            ) : (
              <ProductCard product={product} index={index} t={t} onToggleFavorite={onToggleFavorite} showSeller />
            )}
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => scrollRail(1)}
        aria-label="Défiler vers la droite"
        className={cx("absolute right-2 top-1/2 z-10 hidden -translate-y-1/2 rounded-full border p-2 shadow-md transition hover:scale-105 md:flex", t.cardBg, t.cardBorder, t.textPrimary)}
      >
        <ChevronRight className="h-5 w-5" />
      </button>
    </div>
  );
}

export default function MallHomePage() {
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();
  const [openFaq, setOpenFaq] = useState(0);
  const popularSectionsRef = useRef(null);
  const [popularLoading, setPopularLoading] = useState(false);
  const [popularLoaded, setPopularLoaded] = useState(false);
  const [heroIndex, setHeroIndex] = useState(0);
  const [heroPaused, setHeroPaused] = useState(false);
  const [data, setData] = useState({ loading: true, error: null, categories: [], recentProducts: [], recentServices: [], popularProducts: [], popularServices: [] });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const results = await Promise.allSettled([
          fetchCategories(),
          fetchProducts({ item_type: "product", ordering: "-created_at", page_size: 8 }),
          fetchProducts({ item_type: "service", ordering: "-created_at", page_size: 8 }),
        ]);
        if (cancelled) return;
        const [categories, recentProducts, recentServices] = results.map(
          (result) => result.status === "fulfilled" ? result.value : []
        );
        const failedRequest = results.find((result) => result.status === "rejected");
        setData({
          loading: false,
          error: failedRequest ? `Certaines sections n’ont pas pu être chargées : ${failedRequest.reason?.message || "erreur réseau"}` : null,
          categories,
          recentProducts,
          recentServices,
          popularProducts: [],
          popularServices: [],
        });
      } catch (err) {
        if (!cancelled) setData((s) => ({ ...s, loading: false, error: err.message }));
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const heroSlides = buildHeroSlides(data.recentProducts, data.recentServices);
  const activeHero = heroSlides[heroIndex % heroSlides.length];

  useEffect(() => {
    if (heroPaused || heroSlides.length < 2 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return undefined;
    }
    const intervalId = window.setInterval(() => {
      setHeroIndex((current) => (current + 1) % heroSlides.length);
    }, 5500);
    return () => window.clearInterval(intervalId);
  }, [heroPaused, heroSlides.length]);

  useEffect(() => {
    const section = popularSectionsRef.current;
    if (!section) return undefined;

    let cancelled = false;
    let started = false;
    const loadPopular = async () => {
      if (started) return;
      started = true;
      setPopularLoading(true);
      const results = await Promise.allSettled([
        fetchProducts({ item_type: "product", ordering: "-views_count", page_size: 8 }),
        fetchProducts({ item_type: "service", ordering: "-views_count", page_size: 8 }),
      ]);
      if (cancelled) return;

      const [popularProducts, popularServices] = results.map(
        (result) => result.status === "fulfilled" ? result.value : []
      );
      const failedRequest = results.find((result) => result.status === "rejected");
      setData((current) => ({
        ...current,
        popularProducts,
        popularServices,
        error: failedRequest ? `Certaines sections n’ont pas pu être chargées : ${failedRequest.reason?.message || "erreur réseau"}` : current.error,
      }));
      setPopularLoading(false);
      setPopularLoaded(true);
    };

    if (!("IntersectionObserver" in window)) {
      loadPopular();
      return () => { cancelled = true; };
    }

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        observer.disconnect();
        loadPopular();
      }
    }, { rootMargin: "400px" });
    observer.observe(section);

    return () => {
      cancelled = true;
      observer.disconnect();
    };
  }, []);

  async function handleToggleFavorite(product) {
    if (!isAuthenticated) {
      window.location.href = "/auth";
      return;
    }
    try {
      await toggleFavorite(product.id);
    } catch {
      /* pas critique pour la navigation */
    }
  }

  const { loading, error, categories, recentProducts, recentServices, popularProducts, popularServices } = data;
  // Pas encore de champ "prix barré" côté backend : en attendant, les récents au meilleur prix.
  const deals = [...recentProducts].sort((a, b) => Number(a.price) - Number(b.price)).slice(0, 4);
  const sellers = deriveTopSellers([...recentProducts, ...recentServices, ...popularProducts, ...popularServices]);

  return (
    <div className={cx("min-h-screen font-sans transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <section
        className="relative isolate min-h-[min(68vh,38rem)] overflow-hidden bg-zinc-900"
        aria-label="Produits et services sur Mall"
        onMouseEnter={() => setHeroPaused(true)}
        onMouseLeave={() => setHeroPaused(false)}
        onFocusCapture={() => setHeroPaused(true)}
        onBlurCapture={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setHeroPaused(false);
        }}
      >
        <img
          key={activeHero.src}
          src={activeHero.src}
          alt={activeHero.alt}
          className="hero-image-reveal absolute inset-0 h-full w-full object-cover"
          onError={(event) => {
            event.currentTarget.onerror = null;
            event.currentTarget.src = HERO_FALLBACKS[0].src;
          }}
        />
        <div className="absolute inset-0 bg-zinc-950/50" aria-hidden="true" />
        <div className="relative mx-auto flex min-h-[min(68vh,38rem)] max-w-7xl items-center px-4 py-14 sm:px-6 sm:py-16">
          <div className="max-w-3xl pb-12 text-white">
            <span className="inline-flex items-center rounded-full border border-white/40 bg-black/20 px-3 py-1 text-xs font-semibold text-white">
              {activeHero.type} · Marketplace en Afrique
            </span>
            <h1 className="mt-5 max-w-2xl text-4xl font-semibold leading-[1.1] sm:text-5xl lg:text-6xl">
              Vendez ce qui dort. Trouvez ce qu'il vous faut.
            </h1>
            <p className="mt-5 max-w-xl text-base text-white/90 sm:text-lg">
              Découvrez des produits près de chez vous ou trouvez un professionnel pour votre prochain besoin.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to={isAuthenticated ? "/vendeur" : "/auth?mode=register"} className="rounded-lg bg-white px-5 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-100">
                Commencer à vendre
              </Link>
              <Link to="/catalogue?item_type=product" className="rounded-lg border border-white/70 bg-black/15 px-5 py-3 text-sm font-semibold text-white hover:bg-white/15">
                Découvrir les produits
              </Link>
              <Link to="/catalogue?item_type=service" className="rounded-lg border border-white/70 bg-black/15 px-5 py-3 text-sm font-semibold text-white hover:bg-white/15">
                Trouver un service
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs font-medium text-white/90 sm:text-sm">
              <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Paiement à la remise</span>
              <span className="inline-flex items-center gap-2"><Users className="h-4 w-4" /> Vendeurs vérifiés</span>
              <span className="inline-flex items-center gap-2"><Truck className="h-4 w-4" /> Livraison suivie</span>
            </div>
          </div>
        </div>
        <div className="absolute bottom-4 right-4 flex items-center gap-2 sm:bottom-6 sm:right-6">
          <button
            type="button"
            onClick={() => setHeroIndex((current) => (current - 1 + heroSlides.length) % heroSlides.length)}
            aria-label="Image précédente"
            className="flex h-10 w-10 items-center justify-center rounded-full border border-white/60 bg-black/30 text-white hover:bg-black/50"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <span className="min-w-12 text-center text-xs font-semibold text-white" aria-live="polite">
            {heroIndex + 1} / {heroSlides.length}
          </span>
          <button
            type="button"
            onClick={() => setHeroIndex((current) => (current + 1) % heroSlides.length)}
            aria-label="Image suivante"
            className="flex h-10 w-10 items-center justify-center rounded-full border border-white/60 bg-black/30 text-white hover:bg-black/50"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>
      </section>

      {error && (
        <section className="mx-auto max-w-7xl px-4 pt-10 sm:px-6"><ErrorBlock message={error} t={t} /></section>
      )}

      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <SectionHeading title="Catégories populaires" t={t} />
        {loading ? <LoadingBlock t={t} /> : categories.length === 0 ? (
          <p className={cx("text-sm", t.textMuted)}>Aucune catégorie pour le moment.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
            {categories.slice(0, 8).map((category) => (
              <Link key={category.id} to={`/catalogue?category=${category.id}&item_type=${category.category_type}`} className={cx("flex flex-col items-center gap-2 rounded-2xl border p-4 text-center transition hover:border-indigo-400 hover:shadow-sm", t.cardBorder, t.cardBg)}>
                {category.icon_url ? <img src={category.icon_url} alt="" className="h-5 w-5" /> : <Tag className="h-5 w-5 text-indigo-600" />}
                <span className={cx("text-xs font-medium", t.textPrimary)}>{category.name}</span>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className={cx("py-14", t.surfaceAlt)}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <SectionHeading eyebrow="Fraîchement publié" title="Produits récents" t={t} />
          {loading ? <LoadingBlock t={t} /> : recentProducts.length === 0 ? (
            <p className={cx("text-sm", t.textMuted)}>Aucun produit publié pour le moment.</p>
          ) : (
            <ProductRail products={recentProducts.slice(0, 12)} t={t} onToggleFavorite={handleToggleFavorite} />
          )}
          <Link to="/catalogue?item_type=product" className="mt-5 inline-flex text-sm font-semibold text-indigo-600 hover:underline">Tous les produits</Link>
        </div>
      </section>

      <section className={cx("py-14", t.surfaceAlt)}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <SectionHeading eyebrow="Prestations" title="Services récents" t={t} />
          {loading ? <LoadingBlock t={t} /> : recentServices.length === 0 ? (
            <p className={cx("text-sm", t.textMuted)}>Aucun service publié pour le moment.</p>
          ) : (
            <ProductRail products={recentServices.slice(0, 12)} t={t} onToggleFavorite={handleToggleFavorite} />
          )}
          <Link to="/catalogue?item_type=service" className="mt-5 inline-flex text-sm font-semibold text-emerald-700 hover:underline">Tous les services</Link>
        </div>
      </section>

      <div ref={popularSectionsRef}>
      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <SectionHeading eyebrow="Les plus consultés" title="Produits populaires" t={t} />
        {loading || popularLoading || !popularLoaded ? <LoadingBlock t={t} /> : popularProducts.length === 0 ? (
          <p className={cx("text-sm", t.textMuted)}>Pas encore assez de vues sur les produits.</p>
        ) : (
          <ProductRail products={popularProducts.slice(0, 12)} t={t} onToggleFavorite={handleToggleFavorite} showViews />
        )}
      </section>

      <section className={cx("py-14", t.surfaceAlt)}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <SectionHeading eyebrow="À découvrir" title="Services populaires" t={t} />
          {loading || popularLoading || !popularLoaded ? <LoadingBlock t={t} /> : popularServices.length === 0 ? (
            <p className={cx("text-sm", t.textMuted)}>Pas encore assez de vues sur les services.</p>
          ) : (
            <ProductRail products={popularServices.slice(0, 12)} t={t} onToggleFavorite={handleToggleFavorite} showViews />
          )}
        </div>
      </section>
      </div>

      <section className={cx("py-14", t.surfaceAlt)}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <SectionHeading eyebrow="À saisir" title="Meilleures offres produits" subtitle="Les produits récents au meilleur prix." t={t} />
          {loading ? <LoadingBlock t={t} /> : deals.length === 0 ? (
            <p className={cx("text-sm", t.textMuted)}>Aucune offre pour le moment.</p>
          ) : (
            <ProductRail products={deals} t={t} onToggleFavorite={handleToggleFavorite} />
          )}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <SectionHeading title="Vendeurs populaires" t={t} />
        {loading ? <LoadingBlock t={t} /> : sellers.length === 0 ? (
          <p className={cx("text-sm", t.textMuted)}>Aucun vendeur pour le moment.</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {sellers.map((s) => (
              <Link
                key={s.username}
                to={`/vendeurs/${s.username}`}
                className={cx("flex flex-col items-center rounded-2xl border p-5 text-center transition hover:border-indigo-400", t.cardBorder, t.cardBg)}
              >
                {s.avatar_url ? (
                  <img src={s.avatar_url} alt={`Photo de ${s.username}`} className="h-14 w-14 rounded-full object-cover" />
                ) : (
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-lg font-semibold text-white">
                    {s.username.charAt(0).toUpperCase()}
                  </div>
                )}
                <p className={cx("mt-3 text-sm font-semibold", t.textPrimary)}>{s.username}</p>
                <p className={cx("flex items-center gap-1 text-xs", t.textMuted)}><MapPin className="h-3 w-3" /> {s.city}</p>
                <p className="mt-2 flex items-center gap-1 text-xs font-mono">
                  <Star className="h-3 w-3 fill-amber-400 text-amber-400" /> {Number(s.rating || 0).toFixed(1)}
                </p>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section id="comment-ca-marche" className={cx("py-14", t.surfaceAlt)}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <SectionHeading title="Comment ça marche" subtitle="Trois étapes, de l’annonce à la remise." t={t} />
          <div className="grid gap-6 sm:grid-cols-3">
            {STEPS.map((step) => (
              <div key={step.n} className={cx("rounded-2xl border p-6", t.cardBorder, t.cardBg)}>
                <span className="font-mono text-3xl font-semibold text-indigo-200">{step.n}</span>
                <p className={cx("mt-3 text-lg font-semibold", t.textPrimary)}>{step.title}</p>
                <p className={cx("mt-2 text-sm", t.textMuted)}>{step.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <SectionHeading title="Ils utilisent Mall" t={t} />
        <div className="grid gap-4 sm:grid-cols-3">
          {TESTIMONIALS.map((testimonial) => (
            <div key={testimonial.name} className={cx("rounded-2xl border p-6", t.cardBorder, t.cardBg)}>
              <div className="flex gap-0.5 text-amber-400">
                {Array.from({ length: 5 }).map((_, i) => <Star key={i} className="h-3.5 w-3.5 fill-amber-400" />)}
              </div>
              <p className={cx("mt-3 text-sm italic", t.textPrimary)}>« {testimonial.quote} »</p>
              <p className={cx("mt-3 text-xs font-semibold", t.textMuted)}>{testimonial.name} · {testimonial.city}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="faq" className={cx("py-14", t.surfaceAlt)}>
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <SectionHeading title="Questions fréquentes" t={t} />
          <div className="flex flex-col">
            {FAQS.map((item, i) => (
              <div key={item.q} className={cx("border-b py-4", t.border)}>
                <button onClick={() => setOpenFaq(openFaq === i ? -1 : i)} className="flex w-full items-center justify-between text-left">
                  <span className={cx("text-sm font-semibold", t.textPrimary)}>{item.q}</span>
                  <ChevronDown className={cx("h-4 w-4 shrink-0 transition-transform", t.textMuted, openFaq === i && "rotate-180")} />
                </button>
                {openFaq === i && <p className={cx("mt-2 text-sm", t.textMuted)}>{item.a}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>

      <SiteFooter t={t} />
    </div>
  );
}
