import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock } from "../components/ui/StatusBlocks";
import { TextField, Button, Alert } from "../components/ui/FormControls";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { fetchCategories } from "../features/catalog/api";
import { fetchCountries, fetchAreas } from "../features/localization/api";
import { fetchProductForEdit, createProduct, updateProduct } from "../features/seller/api";
import { uploadToCloudinary } from "../lib/cloudinary";
import { cx } from "../styles/theme";

const CONDITIONS = [
  { value: "neuf", label: "Neuf" },
  { value: "comme_neuf", label: "Comme neuf" },
  { value: "bon_etat", label: "Bon état" },
  { value: "satisfaisant", label: "Satisfaisant" },
  { value: "a_reconditionner", label: "À reconditionner" },
];

const EMPTY_FORM = {
  item_type: "product", title: "", description: "", category: "", price: "", currency: "USD", price_unit: "fixed", condition: "bon_etat",
  city: "", country: "", stock_quantity: 1, shipping_cost: 0, status: "draft",
  image_1: "", image_2: "", image_3: "",
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
  const [selectedAreaId, setSelectedAreaId] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [uploadingImages, setUploadingImages] = useState({
    image_1: false,
    image_2: false,
    image_3: false,
  });

  useEffect(() => {
    if (!isAuthenticated) navigate("/auth");
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => {});
    fetchCountries().then((items) => {
      setCountries(items);
      const storedCountry = (form.country || "").trim();
      const match = items.find((country) => country.name.toLowerCase() === storedCountry.toLowerCase());
      if (match) setSelectedCountryId(match.id);
    }).catch(() => {});
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

  function handleCountryChange(countryId) {
    const targetCountry = countries.find((country) => country.id === countryId) || null;
    setSelectedCountryId(countryId);
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
          shipping_cost: p.shipping_cost,
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
  const inputClass = cx(
    "w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:border-indigo-500",
    t.inputBg, t.border, t.textPrimary
  );
  const listingCategories = form.item_type === "service"
    ? categories.filter((category) => category.slug === "services")
    : categories;

  useEffect(() => {
    if (form.item_type !== "service") return;
    const servicesCategory = categories.find((category) => category.slug === "services");
    if (servicesCategory && form.category !== servicesCategory.id) {
      setForm((current) => ({ ...current, category: servicesCategory.id }));
    }
  }, [categories, form.category, form.item_type]);

  async function handleImageUpload(field, file) {
    if (!file) return;

    setUploadingImages((prev) => ({ ...prev, [field]: true }));
    setError(null);

    try {
      const url = await uploadToCloudinary(file);
      update(field)(url);
    } catch (err) {
      setError(err.message || "L'upload de l'image a échoué.");
    } finally {
      setUploadingImages((prev) => ({ ...prev, [field]: false }));
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
      stock_quantity: form.item_type === "product" ? Number(form.stock_quantity) : 1,
      shipping_cost: form.item_type === "product" ? form.shipping_cost : 0,
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
                      update("item_type")(value);
                      if (value === "product" && !form.condition) update("condition")("bon_etat");
                      if (value === "product" && categories.some((category) => category.id === form.category && category.slug === "services")) update("category")("");
                      if (value === "service") {
                        const servicesCategory = categories.find((category) => category.slug === "services");
                        if (servicesCategory) update("category")(servicesCategory.id);
                      }
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

            <div className={cx("grid gap-3", form.item_type === "service" ? "grid-cols-3" : "grid-cols-2")}>
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
              ) : <TextField label="Frais de livraison" type="number" value={form.shipping_cost} onChange={update("shipping_cost")} t={t} />}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Pays</span>
                <select value={selectedCountryId} onChange={(event) => handleCountryChange(event.target.value)} className={inputClass}>
                  <option value="">Sélectionner un pays</option>
                  {countries.map((country) => (
                    <option key={country.id} value={country.id}>{country.name}</option>
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

            <div className="grid grid-cols-2 gap-3">
              <TextField label="Ville affichée" value={form.city} onChange={update("city")} required t={t} />
              <TextField label="Pays affiché" value={form.country} onChange={update("country")} required t={t} />
            </div>

            {form.item_type === "product" && <TextField
              label="Stock disponible"
              type="number"
              value={form.stock_quantity}
              onChange={update("stock_quantity")}
              required
              t={t}
            />}

            <div>
              <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>
                Photos — upload Cloudinary ou URL (3 max)
              </span>
              <p className={cx("mb-2 text-xs", t.textMuted)}>
                Tu peux soit sélectionner un fichier, soit coller une URL déjà hébergée.
              </p>
              <div className="flex flex-col gap-3">
                {[
                  ["image_1", "Image 1"],
                  ["image_2", "Image 2"],
                  ["image_3", "Image 3"],
                ].map(([field, label]) => (
                  <div key={field} className="rounded-xl border border-dashed p-3">
                    <label className={cx("mb-2 flex cursor-pointer items-center justify-between text-xs font-medium", t.textPrimary)}>
                      <span>{label}</span>
                      <span className="rounded-full bg-indigo-500 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-white">
                        {uploadingImages[field] ? "Upload..." : "Choisir un fichier"}
                      </span>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => handleImageUpload(field, e.target.files?.[0])}
                      />
                    </label>
                    <TextField
                      label={label}
                      value={form[field]}
                      onChange={update(field)}
                      t={t}
                    />
                  </div>
                ))}
              </div>
            </div>

            <label className="block">
              <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Statut</span>
              <select value={form.status} onChange={(e) => update("status")(e.target.value)} className={inputClass}>
                <option value="draft">Brouillon</option>
                <option value="published">Publié</option>
                <option value="archived">Archivé</option>
              </select>
            </label>

            <Button type="submit" loading={saving}>{isEdit ? "Enregistrer" : "Publier l'annonce"}</Button>
          </form>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
