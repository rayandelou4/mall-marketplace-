import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ImagePlus, Sparkles, Trash2 } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock } from "../components/ui/StatusBlocks";
import { TextField, Button, Alert } from "../components/ui/FormControls";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { fetchCategories } from "../features/catalog/api";
import { fetchCountries, fetchAreas } from "../features/localization/api";
import { WORLD_COUNTRIES, getCountryAlpha2 } from "../features/localization/countries";
import { fetchProductForEdit, createProduct, updateProduct } from "../features/seller/api";
import { fetchSellerAssistantConfig, requestListingSuggestions } from "../features/seller/assistantApi";
import { uploadToCloudinary } from "../lib/cloudinary";
import { cx } from "../styles/theme";

const CONDITIONS = [
  { value: "neuf", label: "Neuf" },
  { value: "comme_neuf", label: "Comme neuf" },
  { value: "bon_etat", label: "Bon état" },
  { value: "satisfaisant", label: "Satisfaisant" },
  { value: "a_reconditionner", label: "À reconditionner" },
];

function flattenCategories(items) {
  return items.flatMap((category) => [category, ...flattenCategories(category.children || [])]);
}

const EMPTY_FORM = {
  item_type: "product", title: "", description: "", category: "", price: "", currency: "USD", price_unit: "fixed", condition: "bon_etat",
  city: "", country: "", stock_quantity: 1, shipping_cost: 0, sale_method: "delivery", status: "draft",
  image_1: "", image_2: "", image_3: "", variants: [],
};

export default function ListingFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();

  const [categories, setCategories] = useState([]);
  const [countries, setCountries] = useState([]);
  const [areas, setAreas] = useState([]);
  const [selectedCountryId, setSelectedCountryId] = useState("");
  const [selectedCountryCode, setSelectedCountryCode] = useState("");
  const [selectedAreaId, setSelectedAreaId] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [originalStockQuantity, setOriginalStockQuantity] = useState(null);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [uploadingImages, setUploadingImages] = useState({
    image_1: false,
    image_2: false,
    image_3: false,
  });
  const [assistantEnabled, setAssistantEnabled] = useState(false);
  const [assistantConfigLoading, setAssistantConfigLoading] = useState(true);
  const [assistantRequesting, setAssistantRequesting] = useState(false);
  const [assistantError, setAssistantError] = useState(null);
  const [assistantSuggestions, setAssistantSuggestions] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) navigate("/auth");
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => {});
    fetchCountries().then((items) => {
      setCountries(items);
      const storedCountry = (form.country || "").trim().toLowerCase();
      const match = items.find((country) => country.name.toLowerCase() === storedCountry
        || getCountryAlpha2(country.code).toLowerCase() === storedCountry);
      const worldCountry = WORLD_COUNTRIES.find((country) => country.name.toLowerCase() === storedCountry);
      if (match) {
        setSelectedCountryId(match.id);
        setSelectedCountryCode(getCountryAlpha2(match.code));
      } else {
        setSelectedCountryId("");
        setSelectedCountryCode(worldCountry?.code || "");
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    let active = true;
    fetchSellerAssistantConfig()
      .then(({ enabled }) => {
        if (active) setAssistantEnabled(Boolean(enabled));
      })
      .catch(() => {
        if (active) setAssistantEnabled(false);
      })
      .finally(() => {
        if (active) setAssistantConfigLoading(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selectedCountryId) {
      setAreas([]);
      setSelectedAreaId("");
      return;
    }

    fetchAreas({ country: selectedCountryId, level: "province" }).then((items) => {
      setAreas(items);
      const storedCity = (form.city || "").trim();
      const match = items.find((area) => area.name.toLowerCase() === storedCity.toLowerCase());
      if (match) setSelectedAreaId(match.id);
    }).catch(() => setAreas([]));
  }, [selectedCountryId, form.city]);

  function handleCountryChange(countryCode) {
    const targetCountry = WORLD_COUNTRIES.find((country) => country.code === countryCode) || null;
    const storedCountry = countries.find((country) => getCountryAlpha2(country.code) === countryCode);
    setSelectedCountryCode(countryCode);
    setSelectedCountryId(storedCountry?.id || "");
    setSelectedAreaId("");
    setAreas([]);
    setForm((current) => ({ ...current, country: targetCountry ? targetCountry.name : "", city: "" }));
  }

  function handleAreaChange(areaId) {
    const targetArea = areas.find((area) => area.id === areaId) || null;
    setSelectedAreaId(areaId);
    setForm((current) => ({ ...current, city: targetArea ? targetArea.name : current.city }));
  }

  useEffect(() => {
    if (!isEdit) return;
    fetchProductForEdit(id)
      .then((p) => {
        setOriginalStockQuantity(p.stock_quantity);
        setForm({
          title: p.title,
          item_type: p.item_type || "product",
          description: p.description,
          category: p.category,
          price: p.price,
          currency: p.currency,
          price_unit: p.price_unit || "fixed",
          condition: p.condition,
          city: p.city,
          country: p.country,
          stock_quantity: p.stock_quantity,
          variants: (p.variants || []).map((variant) => ({
            ...variant,
            attributesText: Object.entries(variant.attributes || {}).map(([key, value]) => `${key}=${value}`).join(", "),
          })),
          shipping_cost: p.shipping_cost,
          sale_method: p.sale_method || "delivery",
          status: p.status,
          image_1: p.images?.[0]?.image_url || "",
          image_2: p.images?.[1]?.image_url || "",
          image_3: p.images?.[2]?.image_url || "",
        });
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, isEdit]);

  const update = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));
  function addVariant() {
    setForm((current) => ({
      ...current,
      variants: [...current.variants, {
        label: "",
        attributes: {},
        attributesText: "",
        stock_quantity: current.variants.length ? 0 : Number(current.stock_quantity || 0),
      }],
    }));
  }

  function updateVariant(index, field, value) {
    setForm((current) => ({
      ...current,
      variants: current.variants.map((variant, variantIndex) => variantIndex === index
        ? { ...variant, [field]: value }
        : variant),
    }));
  }

  function removeVariant(index) {
    setForm((current) => ({
      ...current,
      variants: current.variants.filter((_, variantIndex) => variantIndex !== index),
    }));
  }
  const inputClass = cx(
    "w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:border-indigo-500",
    t.inputBg, t.border, t.textPrimary
  );
  const allCategories = useMemo(() => flattenCategories(categories), [categories]);
  const listingCategories = allCategories.filter(
    (category) => category.category_type === form.item_type
  );

  useEffect(() => {
    const selectedCategory = allCategories.find((category) => category.id === form.category);
    if (selectedCategory && selectedCategory.category_type !== form.item_type) {
      setForm((current) => ({ ...current, category: "" }));
    }
  }, [categories, form.category, form.item_type]);

  async function handleImageSelection(fileList) {
    const files = Array.from(fileList || []);
    const availableFields = ["image_1", "image_2", "image_3"].filter((field) => !form[field]);
    if (files.length > availableFields.length) {
      setError("Vous pouvez ajouter jusqu’à trois photos.");
      return;
    }
    setError(null);
    setAssistantSuggestions(null);

    for (const [index, file] of files.entries()) {
      const field = availableFields[index];
      setUploadingImages((current) => ({ ...current, [field]: true }));
      try {
        const url = await uploadToCloudinary(file);
        setForm((current) => ({ ...current, [field]: url }));
      } catch (err) {
        setError(err.message || "L’envoi d’une photo a échoué.");
      } finally {
        setUploadingImages((current) => ({ ...current, [field]: false }));
      }
    }
  }

  async function handleAssistantRequest() {
    const imageUrls = [form.image_1, form.image_2, form.image_3]
      .filter((url) => url.startsWith("https://"));
    if (!imageUrls.length) {
      setAssistantError("Ajoutez au moins une photo HTTPS pour demander des suggestions.");
      return;
    }
    setAssistantRequesting(true);
    setAssistantError(null);
    setAssistantSuggestions(null);
    try {
      const suggestions = await requestListingSuggestions({
        image_urls: imageUrls,
        title: form.title,
        description: form.description,
        category_id: form.category || null,
      });
      setAssistantSuggestions(suggestions);
    } catch (err) {
      setAssistantError(err.message);
    } finally {
      setAssistantRequesting(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const images = [form.image_1, form.image_2, form.image_3].filter(Boolean);
    const payload = {
      item_type: form.item_type,
      title: form.title,
      description: form.description,
      category: form.category,
      price: form.price,
      currency: form.currency,
      price_unit: form.price_unit,
      condition: form.item_type === "product" ? form.condition : "",
      city: form.city,
      country: form.country,
      stock_quantity: form.item_type === "product"
        ? form.variants.length
          ? form.variants.reduce((total, variant) => total + Number(variant.stock_quantity || 0), 0)
          : Number(form.stock_quantity)
        : 1,
      ...(form.item_type === "product" && form.variants.length > 0 ? {
        variants: form.variants.map((variant) => ({
          ...(variant.id ? { id: variant.id } : {}),
          label: variant.label,
          attributes: Object.fromEntries((variant.attributesText || "").split(",").map((pair) => pair.trim().split("=")).filter(([key, value]) => key && value).map(([key, value]) => [key.trim(), value.trim()])),
          stock_quantity: Number(variant.stock_quantity),
        })),
      } : {}),
      ...(isEdit && form.item_type === "product"
        ? { expected_stock_quantity: originalStockQuantity }
        : {}),
      shipping_cost: form.item_type === "product" ? form.shipping_cost : 0,
      sale_method: form.item_type === "product" ? form.sale_method : "delivery",
      status: form.status,
      images,
    };
    try {
      if (isEdit) await updateProduct(id, payload);
      else await createProduct(payload);
      navigate("/vendeur");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
        <SectionHeading title={isEdit ? "Modifier l'annonce" : "Nouvelle annonce"} t={t} />

        {loading ? (
          <LoadingBlock t={t} />
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {error && <Alert type="error">{error}</Alert>}

            <fieldset>
              <legend className={cx("mb-2 text-sm font-medium", t.textPrimary)}>Type d'annonce</legend>
              <div className={cx("grid grid-cols-2 gap-2 rounded-xl border p-1", t.border)}>
                {[['product', 'Produit'], ['service', 'Service']].map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={form.item_type === value}
                    onClick={() => {
                      setForm((current) => ({
                        ...current,
                        item_type: value,
                        category: allCategories.find((category) => category.id === current.category)?.category_type === value
                          ? current.category
                          : "",
                        condition: value === "product" && !current.condition ? "bon_etat" : current.condition,
                        variants: value === "service" ? [] : current.variants,
                      }));
                    }}
                    className={cx("rounded-lg px-3 py-2 text-sm font-medium", form.item_type === value ? "bg-indigo-600 text-white" : t.textMuted)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </fieldset>

            <TextField label="Titre" value={form.title} onChange={update("title")} required t={t} />

            <label className="block">
              <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Description</span>
              <textarea
                value={form.description}
                onChange={(e) => update("description")(e.target.value)}
                required
                rows={4}
                placeholder={form.item_type === "service" ? "Décris la prestation, tes disponibilités et les conditions…" : "Décris l'article…"}
                className={inputClass}
              />
            </label>

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Catégorie</span>
                <select value={form.category} onChange={(e) => update("category")(e.target.value)} required className={inputClass}>
                  <option value="">Choisir…</option>
                  {listingCategories.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </label>
              {form.item_type === "product" && <label className="block">
                <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>État</span>
                <select value={form.condition} onChange={(e) => update("condition")(e.target.value)} className={inputClass}>
                  {CONDITIONS.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </label>}
            </div>

            <div className={cx("grid grid-cols-2 gap-3", form.item_type === "service" && "sm:grid-cols-3")}>
              <TextField label={form.item_type === "service" ? "Tarif" : "Prix"} type="number" value={form.price} onChange={update("price")} required t={t} />
              <label className="block">
                <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Devise</span>
                <select value={form.currency} onChange={(e) => update("currency")(e.target.value)} className={inputClass}>
                  <option value="USD">USD</option>
                  <option value="CDF">CDF</option>
                </select>
              </label>
              {form.item_type === "service" ? (
                <label className="block">
                  <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Tarification</span>
                  <select value={form.price_unit} onChange={(e) => update("price_unit")(e.target.value)} className={inputClass}>
                    <option value="fixed">Forfait</option>
                    <option value="hour">Par heure</option>
                    <option value="day">Par jour</option>
                  </select>
                </label>
              ) : (
                <TextField
                  label="Frais de livraison"
                  type="number"
                  value={form.sale_method === "delivery" ? form.shipping_cost : 0}
                  onChange={update("shipping_cost")}
                  disabled={form.sale_method === "pickup"}
                  t={t}
                />
              )}
            </div>

            {form.item_type === "product" && (
              <fieldset>
                <legend className={cx("mb-2 block text-sm font-medium", t.textPrimary)}>Mode de vente</legend>
                <div className={cx("grid grid-cols-2 gap-2 rounded-xl border p-1", t.border)}>
                  {[["delivery", "Livraison"], ["pickup", "Remise en main propre"]].map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={form.sale_method === value}
                      onClick={() => update("sale_method")(value)}
                      className={cx(
                        "rounded-lg px-3 py-2 text-sm font-semibold transition",
                        form.sale_method === value ? "bg-indigo-600 text-white" : t.textMuted,
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </fieldset>
            )}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="block">
                <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Pays</span>
                <select value={selectedCountryCode} onChange={(event) => handleCountryChange(event.target.value)} className={inputClass}>
                  <option value="">Sélectionner un pays</option>
                  {WORLD_COUNTRIES.map((country) => (
                    <option key={country.code} value={country.code}>{country.name}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Province / commune</span>
                <select value={selectedAreaId} onChange={(event) => handleAreaChange(event.target.value)} className={inputClass} disabled={!selectedCountryId}>
                  <option value="">Sélectionner</option>
                  {areas.map((area) => (
                    <option key={area.id} value={area.id}>{area.name}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <TextField label="Ville affichée" value={form.city} onChange={update("city")} required t={t} />
              <TextField label="Pays affiché" value={form.country} onChange={update("country")} required t={t} />
            </div>

            {form.item_type === "product" && (
              <section className="flex flex-col gap-3" aria-label="Gestion du stock">
                {form.variants.length === 0 ? (
                  <TextField label="Stock disponible" type="number" value={form.stock_quantity} onChange={update("stock_quantity")} required t={t} />
                ) : (
                  <p className={cx("text-sm font-medium", t.textPrimary)}>
                    Stock total : {form.variants.reduce((total, variant) => total + Number(variant.stock_quantity || 0), 0)} unité(s)
                  </p>
                )}
                {form.variants.map((variant, index) => (
                  <div key={variant.id || `variant-${index}`} className={cx("grid grid-cols-1 gap-3 rounded-xl border p-3 sm:grid-cols-[1fr_1fr_8rem_auto]", t.border, t.cardBg)}>
                    <TextField label="Variante" value={variant.label} onChange={(value) => updateVariant(index, "label", value)} required t={t} />
                    <TextField label="Attributs (taille=M, couleur=Noir)" value={variant.attributesText || ""} onChange={(value) => updateVariant(index, "attributesText", value)} t={t} />
                    <TextField label="Quantité" type="number" value={variant.stock_quantity} onChange={(value) => updateVariant(index, "stock_quantity", value)} required t={t} />
                    <button type="button" onClick={() => removeVariant(index)} disabled={form.variants.length === 1} aria-label={`Retirer la variante ${variant.label || index + 1}`} className="self-end rounded-lg border border-rose-200 p-2 text-rose-600 disabled:opacity-40">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
                <button type="button" onClick={addVariant} className="self-start text-sm font-semibold text-indigo-600 hover:underline">Ajouter une variante</button>
              </section>
            )}

            <section aria-label="Photos du produit">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className={cx("text-sm font-medium", t.textPrimary)}>Photos</h2>
                  <p className={cx("text-xs", t.textMuted)}>Jusqu’à 3 photos. Vous pouvez en sélectionner plusieurs à la fois.</p>
                </div>
                <label className={cx("inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold", t.border, t.textPrimary, Object.values(uploadingImages).some(Boolean) && "pointer-events-none opacity-60")}>
                  <ImagePlus className="h-4 w-4" />
                  {Object.values(uploadingImages).some(Boolean) ? "Envoi…" : "Ajouter"}
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    disabled={Object.values(uploadingImages).some(Boolean)}
                    className="sr-only"
                    onChange={(event) => {
                      handleImageSelection(event.target.files);
                      event.target.value = "";
                    }}
                  />
                </label>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {[
                  ["image_1", "Photo 1"],
                  ["image_2", "Photo 2"],
                  ["image_3", "Photo 3"],
                ].map(([field, label]) => (
                  <div key={field} className={cx("min-w-0 rounded-xl border p-3", t.border, t.cardBg)}>
                    <div className="relative mb-2 aspect-square overflow-hidden rounded-lg bg-black/5">
                      {form[field] ? (
                        <img src={form[field]} alt={label} className="h-full w-full object-cover" />
                      ) : (
                        <div className={cx("flex h-full items-center justify-center text-sm", t.textMuted)}>
                          {uploadingImages[field] ? "Envoi…" : label}
                        </div>
                      )}
                      {form[field] && (
                        <button
                          type="button"
                          onClick={() => setForm((current) => ({ ...current, [field]: "" }))}
                          aria-label={`Supprimer ${label.toLowerCase()}`}
                          className="absolute right-2 top-2 rounded-full bg-white p-2 text-rose-600 shadow"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                    <TextField label={`URL ${label.toLowerCase()}`} value={form[field]} onChange={update(field)} t={t} />
                  </div>
                ))}
              </div>
            </section>

            <section className={cx("rounded-xl border p-4", t.border, t.cardBg)} aria-labelledby="listing-assistant-title">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 id="listing-assistant-title" className={cx("flex items-center gap-2 text-sm font-semibold", t.textPrimary)}>
                    <Sparkles className="h-4 w-4" /> Assistant annonce
                  </h2>
                  <p className={cx("mt-1 text-xs", t.textMuted)}>
                    Les suggestions restent modifiables. Les photos ne permettent pas de vérifier des caractéristiques techniques invisibles.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  className="min-h-11 w-auto rounded-lg px-3"
                  onClick={handleAssistantRequest}
                  disabled={!assistantEnabled || assistantConfigLoading || assistantRequesting || Object.values(uploadingImages).some(Boolean)}
                  loading={assistantRequesting}
                >
                  {assistantConfigLoading
                    ? "Vérification…"
                    : assistantRequesting
                      ? "Analyse…"
                      : "Suggérer"}
                </Button>
              </div>
              {!assistantConfigLoading && !assistantEnabled && (
                <p className={cx("mt-3 text-xs", t.textMuted)} role="status">
                  Assistant désactivé : aucun fournisseur IA n’est configuré.
                </p>
              )}
              {assistantError && <p className="mt-3 text-sm text-rose-600" role="alert">{assistantError}</p>}
              {assistantSuggestions && (
                <div className={cx("mt-4 flex flex-col gap-3 border-t pt-4", t.border)}>
                  {assistantSuggestions.title && (
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className={cx("text-sm", t.textPrimary)}><span className="font-medium">Titre proposé :</span> {assistantSuggestions.title}</p>
                      <button type="button" onClick={() => update("title")(assistantSuggestions.title)} className="min-h-11 rounded-lg px-3 text-sm font-semibold text-indigo-600">Utiliser</button>
                    </div>
                  )}
                  {assistantSuggestions.description && (
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className={cx("min-w-0 flex-1 whitespace-pre-wrap text-sm", t.textPrimary)}><span className="font-medium">Description proposée :</span> {assistantSuggestions.description}</p>
                      <button type="button" onClick={() => update("description")(assistantSuggestions.description)} className="min-h-11 rounded-lg px-3 text-sm font-semibold text-indigo-600">Utiliser</button>
                    </div>
                  )}
                  {assistantSuggestions.category_id && (
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className={cx("text-sm", t.textPrimary)}>
                        <span className="font-medium">Catégorie :</span>{" "}
                        {categories.find((category) => category.id === assistantSuggestions.category_id)?.name || "Catégorie suggérée"}
                      </p>
                      <button
                        type="button"
                        disabled={!listingCategories.some((category) => category.id === assistantSuggestions.category_id)}
                        onClick={() => update("category")(assistantSuggestions.category_id)}
                        className="min-h-11 rounded-lg px-3 text-sm font-semibold text-indigo-600 disabled:opacity-50"
                      >Utiliser</button>
                    </div>
                  )}
                  {assistantSuggestions.visual_attributes?.length > 0 && (
                    <p className={cx("text-sm", t.textMuted)}><span className="font-medium">Éléments visuellement observables, à vérifier :</span> {assistantSuggestions.visual_attributes.join(", ")}</p>
                  )}
                  {assistantSuggestions.keywords?.length > 0 && (
                    <p className={cx("text-sm", t.textMuted)}><span className="font-medium">Mots-clés proposés :</span> {assistantSuggestions.keywords.join(", ")}</p>
                  )}
                  {assistantSuggestions.quality_suggestions?.length > 0 && (
                    <div className={cx("text-sm", t.textMuted)}>
                      <p className="font-medium">Pistes d’amélioration</p>
                      <ul className="mt-1 list-inside list-disc">
                        {assistantSuggestions.quality_suggestions.map((suggestion, index) => <li key={`${index}-${suggestion}`}>{suggestion}</li>)}
                      </ul>
                    </div>
                  )}
                  <p className="text-xs text-amber-700">{assistantSuggestions.disclaimer}</p>
                </div>
              )}
            </section>

            <label className="block">
              <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Statut</span>
              <select value={form.status} onChange={(e) => update("status")(e.target.value)} className={inputClass}>
                <option value="draft">Brouillon</option>
                <option value="published">Publié</option>
                <option value="archived">Archivé</option>
              </select>
            </label>

            <Button
              type="submit"
              loading={saving}
              disabled={saving || Object.values(uploadingImages).some(Boolean)}
            >
              {Object.values(uploadingImages).some(Boolean)
                ? "Préparation des photos…"
                : form.status === "draft"
                  ? "Enregistrer le brouillon"
                  : form.status === "archived"
                    ? "Archiver l'annonce"
                    : isEdit ? "Enregistrer les modifications" : "Publier l'annonce"}
            </Button>
          </form>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
