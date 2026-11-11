import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ImagePlus, RotateCcw, Search, X } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { ProductCard } from "../components/catalog/ProductCard";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { fetchCategories, fetchProductsPaginated, toggleFavorite, saveSearch } from "../features/catalog/api";
import { fetchVisualSearchConfig, searchProductsByImage } from "../features/catalog/visualSearchApi";
import { cx } from "../styles/theme";

const CONDITIONS = [
  { value: "neuf", label: "Neuf" },
  { value: "comme_neuf", label: "Comme neuf" },
  { value: "bon_etat", label: "Bon état" },
  { value: "satisfaisant", label: "Satisfaisant" },
  { value: "a_reconditionner", label: "À reconditionner" },
];

// Valeur par défaut de REST_FRAMEWORK["PAGE_SIZE"] dans settings.py.
const PAGE_SIZE = 20;

function flattenCategories(items) {
  return items.flatMap((category) => [category, ...flattenCategories(category.children || [])]);
}

function writeFilters(searchParams, setSearchParams, values) {
  const next = new URLSearchParams(searchParams);
  Object.entries(values).forEach(([key, value]) => {
    const normalized = typeof value === "string" ? value.trim() : value;
    if (normalized) next.set(key, normalized);
    else next.delete(key);
  });
  next.delete("page");
  setSearchParams(next);
}

export default function CatalogPage() {
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(
    () => ({
      search: searchParams.get("search") || "",
      category: searchParams.get("category") || "",
      city: searchParams.get("city") || "",
      condition: searchParams.get("condition") || "",
      item_type: searchParams.get("item_type") || "",
      price_min: searchParams.get("price_min") || "",
      price_max: searchParams.get("price_max") || "",
      currency: searchParams.get("currency") || "",
      seller_type: searchParams.get("seller_type") || "",
      available: searchParams.get("available") || "",
      ordering: searchParams.get("ordering") || "-created_at",
      page: Math.max(1, Number(searchParams.get("page") || 1) || 1),
    }),
    [searchParams]
  );

  const [categories, setCategories] = useState([]);
  const [state, setState] = useState({ loading: true, error: null, results: [], count: 0 });
  const [saveNotice, setSaveNotice] = useState(null);
  const [searchDraft, setSearchDraft] = useState(filters.search);
  const [cityDraft, setCityDraft] = useState(filters.city);
  const [visualSearchEnabled, setVisualSearchEnabled] = useState(false);
  const [visualSearchConfigLoading, setVisualSearchConfigLoading] = useState(true);
  const [visualSearchImage, setVisualSearchImage] = useState(null);
  const [visualSearchPreview, setVisualSearchPreview] = useState("");
  const [visualSearchResults, setVisualSearchResults] = useState(null);
  const [visualSearchLoading, setVisualSearchLoading] = useState(false);
  const [visualSearchError, setVisualSearchError] = useState(null);
  const flatCategories = useMemo(() => flattenCategories(categories), [categories]);

  const filterError = useMemo(() => {
    const hasMinimum = filters.price_min !== "";
    const hasMaximum = filters.price_max !== "";
    const minimum = Number(filters.price_min);
    const maximum = Number(filters.price_max);
    if (hasMinimum && (!Number.isFinite(minimum) || minimum < 0)) return "Le prix minimum doit être un nombre positif ou nul.";
    if (hasMaximum && (!Number.isFinite(maximum) || maximum < 0)) return "Le prix maximum doit être un nombre positif ou nul.";
    if (hasMinimum && hasMaximum && minimum > maximum) return "Le prix minimum ne peut pas dépasser le prix maximum.";
    if ((hasMinimum || hasMaximum) && !filters.currency) return "Choisissez une devise pour filtrer par prix.";
    return null;
  }, [filters]);

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => {});
  }, []);

  useEffect(() => {
    let active = true;
    fetchVisualSearchConfig()
      .then(({ enabled }) => { if (active) setVisualSearchEnabled(Boolean(enabled)); })
      .catch(() => { if (active) setVisualSearchEnabled(false); })
      .finally(() => { if (active) setVisualSearchConfigLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!visualSearchImage) {
      setVisualSearchPreview("");
      return undefined;
    }
    const previewUrl = URL.createObjectURL(visualSearchImage);
    setVisualSearchPreview(previewUrl);
    return () => URL.revokeObjectURL(previewUrl);
  }, [visualSearchImage]);

  useEffect(() => setSearchDraft(filters.search), [filters.search]);
  useEffect(() => setCityDraft(filters.city), [filters.city]);

  useEffect(() => {
    const normalizedSearch = searchDraft.trim().replace(/\s+/g, " ");
    const normalizedCity = cityDraft.trim().replace(/\s+/g, " ");
    if (normalizedSearch === filters.search && normalizedCity === filters.city) return undefined;
    const timeout = window.setTimeout(() => writeFilters(searchParams, setSearchParams, {
      search: normalizedSearch,
      city: normalizedCity,
    }), 400);
    return () => window.clearTimeout(timeout);
  }, [searchDraft, cityDraft, filters.search, filters.city, searchParams, setSearchParams]);

  useEffect(() => {
    if (filterError) {
      setState((s) => ({ ...s, loading: false, error: null }));
      return undefined;
    }
    let cancelled = false;
    setState((s) => ({ ...s, loading: true }));
    fetchProductsPaginated(filters)
      .then((data) => {
        if (cancelled) return;
        setState({ loading: false, error: null, results: data.results || [], count: data.count || 0 });
      })
      .catch((err) => {
        if (!cancelled) setState((s) => ({ ...s, loading: false, error: err.message }));
      });
    return () => {
      cancelled = true;
    };
  }, [filters, filterError]);

  function updateFilter(key, value) {
    writeFilters(searchParams, setSearchParams, { [key]: value });
  }

  function applySearch(event) {
    event.preventDefault();
    writeFilters(searchParams, setSearchParams, {
      search: searchDraft.replace(/\s+/g, " ").trim(),
      city: cityDraft.replace(/\s+/g, " ").trim(),
    });
  }

  function resetFilters() {
    setSearchDraft("");
    setCityDraft("");
    setSearchParams({});
  }

  function goToPage(page) {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(page));
    setSearchParams(next);
  }

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

  async function handleSaveSearch() {
    try {
      await saveSearch(filters.search || "Recherche sans nom", filters);
      setSaveNotice("Recherche enregistrée.");
    } catch (err) {
      setSaveNotice(err.message);
    }
  }

  async function handleVisualSearch(event) {
    event.preventDefault();
    if (!visualSearchEnabled || !visualSearchImage) return;
    setVisualSearchLoading(true);
    setVisualSearchError(null);
    setVisualSearchResults(null);
    try {
      const response = await searchProductsByImage(visualSearchImage);
      setVisualSearchResults(response.results || []);
    } catch (error) {
      setVisualSearchError(error.message);
    } finally {
      setVisualSearchLoading(false);
    }
  }

  function handleVisualImageChange(file) {
    setVisualSearchResults(null);
    setVisualSearchError(null);
    if (!file) {
      setVisualSearchImage(null);
      return;
    }
    if (!file.type.startsWith("image/")) {
      setVisualSearchError("Sélectionnez un fichier image.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setVisualSearchError("La photo ne peut pas dépasser 8 Mo.");
      return;
    }
    setVisualSearchImage(file);
  }

  const totalPages = Math.max(1, Math.ceil(state.count / PAGE_SIZE));
  const inputClass = cx("rounded-xl border px-3 py-2 text-sm", t.border, t.cardBg, t.textPrimary);
  const activeFilters = [
    filters.search && { key: "search", label: `Recherche : ${filters.search}` },
    filters.category && { key: "category", label: `Catégorie : ${flatCategories.find((item) => item.id === filters.category)?.name || "sélectionnée"}` },
    filters.item_type && { key: "item_type", label: filters.item_type === "service" ? "Services" : "Produits" },
    filters.condition && { key: "condition", label: `État : ${CONDITIONS.find((item) => item.value === filters.condition)?.label || filters.condition}` },
    filters.city && { key: "city", label: `Ville : ${filters.city}` },
    filters.price_min && { key: "price_min", label: `Dès ${filters.price_min} ${filters.currency}` },
    filters.price_max && { key: "price_max", label: `Jusqu'à ${filters.price_max} ${filters.currency}` },
    filters.currency && { key: "currency", label: `Devise : ${filters.currency}` },
    filters.seller_type && { key: "seller_type", label: filters.seller_type === "professional" ? "Commerçant professionnel" : "Particulier" },
    filters.available === "true" && { key: "available", label: "Disponibles uniquement" },
  ].filter(Boolean);
  const catalogTitle = filters.item_type === "product"
    ? "Produits"
    : filters.item_type === "service" ? "Services" : "Produits et services";

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader initialSearch={filters.search} />

      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <SectionHeading
          eyebrow={filters.search ? `Résultats pour « ${filters.search} »` : null}
          title={catalogTitle}
          subtitle={`${state.count} ${filters.item_type === "service" ? "service" : filters.item_type === "product" ? "produit" : "annonce"}${state.count > 1 ? "s" : ""}`}
          t={t}
        />

        <form onSubmit={applySearch} className={cx("mb-4 flex items-center gap-2 rounded-xl border px-3 py-2", t.border, t.cardBg)} role="search">
          <Search className={cx("h-4 w-4 shrink-0", t.textMuted)} aria-hidden="true" />
          <input
            type="search"
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
            placeholder="Rechercher un produit, une description, une catégorie…"
            aria-label="Rechercher dans le catalogue"
            className={cx("min-w-0 flex-1 bg-transparent text-sm outline-none", t.textPrimary)}
          />
          {searchDraft && (
            <button type="button" onClick={() => { setSearchDraft(""); updateFilter("search", ""); }} aria-label="Effacer la recherche" className={cx("rounded-full p-1", t.textMuted)}>
              <X className="h-4 w-4" />
            </button>
          )}
          <button type="submit" aria-label="Lancer la recherche" className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white">
            Rechercher
          </button>
        </form>

        {filters.item_type !== "service" && (
          <section className={cx("mb-6 border-y py-4", t.border)} aria-labelledby="visual-search-title">
            <form onSubmit={handleVisualSearch} className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <h2 id="visual-search-title" className={cx("text-sm font-semibold", t.textPrimary)}>Recherche par photo</h2>
                <p className={cx("mt-1 text-xs", t.textMuted)}>
                  {visualSearchConfigLoading
                    ? "Vérification de la disponibilité…"
                    : visualSearchEnabled
                      ? isAuthenticated
                        ? "Votre photo sera transmise au moteur configuré uniquement lorsque vous lancerez la recherche."
                        : "Connectez-vous pour lancer une recherche. Votre photo ne sera transmise qu’après votre action."
                      : "Aucun moteur visuel n’est configuré. Votre photo reste sur cet appareil et aucun résultat fictif ne sera affiché."}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label className={cx("inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold", t.border, t.textPrimary)}>
                  <ImagePlus className="h-4 w-4" />
                  Choisir une photo
                  <input
                    type="file"
                    accept="image/*"
                    className="sr-only"
                    onChange={(event) => {
                      handleVisualImageChange(event.target.files?.[0]);
                      event.target.value = "";
                    }}
                  />
                </label>
                <button
                  type="submit"
                  disabled={!visualSearchEnabled || !isAuthenticated || !visualSearchImage || visualSearchLoading || visualSearchConfigLoading}
                  className="min-h-11 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {visualSearchLoading ? "Recherche…" : "Rechercher"}
                </button>
              </div>
            </form>
            {visualSearchPreview && (
              <div className="mt-3 flex items-center gap-3">
                <img src={visualSearchPreview} alt="Aperçu de la photo sélectionnée" className="h-16 w-16 rounded-lg object-cover" />
                <span className={cx("min-w-0 truncate text-sm", t.textMuted)}>{visualSearchImage.name}</span>
                <button type="button" onClick={() => handleVisualImageChange(null)} aria-label="Retirer la photo sélectionnée" className="min-h-11 min-w-11 rounded-lg text-rose-600">
                  <X className="mx-auto h-4 w-4" />
                </button>
              </div>
            )}
            {visualSearchError && <p role="alert" className="mt-2 text-sm text-rose-600">{visualSearchError}</p>}
            {visualSearchResults && (
              <div className="mt-5">
                <h3 className={cx("mb-3 text-sm font-semibold", t.textPrimary)}>
                  Résultats visuels ({visualSearchResults.length})
                </h3>
                {visualSearchResults.length ? (
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                    {visualSearchResults.map((product, index) => (
                      <ProductCard key={product.id} product={product} index={index} t={t} onToggleFavorite={handleToggleFavorite} />
                    ))}
                  </div>
                ) : <p className={cx("text-sm", t.textMuted)}>Aucun produit similaire trouvé.</p>}
              </div>
            )}
          </section>
        )}

        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <select value={filters.item_type} onChange={(e) => updateFilter("item_type", e.target.value)} className={inputClass}>
            <option value="">Produits et services</option>
            <option value="product">Produits</option>
            <option value="service">Services</option>
          </select>
          <select value={filters.category} onChange={(e) => updateFilter("category", e.target.value)} className={inputClass}>
            <option value="">Toutes catégories</option>
            {flatCategories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {filters.item_type !== "service" && <select aria-label="État du produit" value={filters.condition} onChange={(e) => updateFilter("condition", e.target.value)} className={inputClass}>
              <option value="">Tout état</option>
              {CONDITIONS.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>}
          <input aria-label="Ville" placeholder="Ville" value={cityDraft} onChange={(e) => setCityDraft(e.target.value)} className={inputClass} />
          <input aria-label="Prix minimum" placeholder="Prix min" type="number" min="0" step="0.01" value={filters.price_min} onChange={(e) => updateFilter("price_min", e.target.value)} className={inputClass} />
          <input aria-label="Prix maximum" placeholder="Prix max" type="number" min="0" step="0.01" value={filters.price_max} onChange={(e) => updateFilter("price_max", e.target.value)} className={inputClass} />
          <select aria-label="Devise des prix" value={filters.currency} onChange={(e) => updateFilter("currency", e.target.value)} className={inputClass}>
            <option value="">Toutes devises</option>
            <option value="USD">USD</option>
            <option value="CDF">CDF</option>
          </select>
          <select aria-label="Type de vendeur" value={filters.seller_type} onChange={(e) => updateFilter("seller_type", e.target.value)} className={inputClass}>
            <option value="">Tous les vendeurs</option>
            <option value="individual">Particulier</option>
            <option value="professional">Commerçant professionnel</option>
          </select>
          <select aria-label="Disponibilité" value={filters.available} onChange={(e) => updateFilter("available", e.target.value)} className={inputClass}>
            <option value="">Toute disponibilité</option>
            <option value="true">Disponibles uniquement</option>
          </select>
          <select value={filters.ordering} onChange={(e) => updateFilter("ordering", e.target.value)} className={inputClass}>
            <option value="relevance">Pertinence</option>
            <option value="-created_at">Plus récents</option>
            <option value="created_at">Plus anciens</option>
            <option value="price">Prix croissant</option>
            <option value="-price">Prix décroissant</option>
          </select>
        </div>

        {filterError && <p role="alert" className="mb-4 text-sm font-medium text-rose-600">{filterError}</p>}

        {activeFilters.length > 0 && (
          <div className="mb-5 flex flex-wrap items-center gap-2" aria-label="Filtres actifs">
            {activeFilters.map(({ key, label }) => (
              <button key={key} type="button" onClick={() => updateFilter(key, "")} className={cx("inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs", t.border, t.textMuted)}>
                {label}<X className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            ))}
            <button type="button" onClick={resetFilters} className="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-semibold text-indigo-600 hover:underline">
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" /> Réinitialiser
            </button>
          </div>
        )}

        {isAuthenticated && (
          <div className="mb-6 flex items-center gap-2">
            <button onClick={handleSaveSearch} className="text-xs font-medium text-indigo-600 hover:underline">
              Enregistrer cette recherche
            </button>
            {saveNotice && <span className={cx("text-xs", t.textMuted)}>{saveNotice}</span>}
          </div>
        )}

        {filterError ? null : state.loading ? (
          <LoadingBlock t={t} label="Chargement des annonces…" />
        ) : state.error ? (
          <ErrorBlock message={state.error} t={t} />
        ) : state.results.length === 0 ? (
          <p className={cx("text-sm", t.textMuted)}>Aucune annonce ne correspond à ces critères.</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {state.results.map((p, i) => (
                <ProductCard key={p.id} product={p} index={i} t={t} onToggleFavorite={handleToggleFavorite} />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="mt-8 flex items-center justify-center gap-4 text-sm">
                <button disabled={filters.page <= 1} onClick={() => goToPage(filters.page - 1)} className={cx("rounded-full border px-4 py-2 disabled:opacity-40", t.border)}>
                  Précédent
                </button>
                <span className={t.textMuted}>Page {filters.page} / {totalPages}</span>
                <button disabled={filters.page >= totalPages} onClick={() => goToPage(filters.page + 1)} className={cx("rounded-full border px-4 py-2 disabled:opacity-40", t.border)}>
                  Suivant
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
