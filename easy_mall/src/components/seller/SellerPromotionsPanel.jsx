import React, { useEffect, useState } from "react";
import { Tag, Trash2 } from "lucide-react";
import { Button, TextField } from "../ui/FormControls";
import { SectionHeading } from "../ui/StatusBlocks";
import { fetchMyProducts } from "../../features/seller/api";
import { createPromotion, deletePromotion, fetchMyPromotions } from "../../features/promotions/api";
import { formatPrice } from "../../lib/format";
import { cx } from "../../styles/theme";

const INITIAL_FORM = {
  name: "",
  discount_type: "percentage",
  value: "10",
  min_quantity: "1",
  min_customer_purchases: "0",
  free_shipping: false,
  starts_at: "",
  ends_at: "",
  products: [],
};

export function SellerPromotionsPanel({ t }) {
  const [products, setProducts] = useState([]);
  const [promotions, setPromotions] = useState([]);
  const [form, setForm] = useState(INITIAL_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [sellerProducts, sellerPromotions] = await Promise.all([
        fetchMyProducts(),
        fetchMyPromotions(),
      ]);
      setProducts(sellerProducts);
      setPromotions(sellerPromotions);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([fetchMyProducts(), fetchMyPromotions()])
      .then(([sellerProducts, sellerPromotions]) => {
        if (active) {
          setProducts(sellerProducts);
          setPromotions(sellerPromotions);
        }
      })
      .catch((loadError) => { if (active) setError(loadError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function toggleProduct(productId) {
    setForm((current) => ({
      ...current,
      products: current.products.includes(productId)
        ? current.products.filter((id) => id !== productId)
        : [...current.products, productId],
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await createPromotion({
        ...form,
        value: form.value || "0",
        min_quantity: Number(form.min_quantity),
        min_customer_purchases: Number(form.min_customer_purchases),
        starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null,
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
        currency: form.discount_type === "percentage"
          ? ""
          : products.find((product) => form.products.includes(product.id))?.currency || "",
      });
      setForm(INITIAL_FORM);
      setNotice("Promotion créée.");
      await load();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(promotion) {
    if (!window.confirm(`Supprimer la promotion « ${promotion.name} » ?`)) return;
    try {
      await deletePromotion(promotion.id);
      setPromotions((current) => current.filter((item) => item.id !== promotion.id));
    } catch (deleteError) {
      setError(deleteError.message);
    }
  }

  const inputClass = cx("w-full rounded-xl border px-4 py-2.5 text-sm", t.inputBg, t.border, t.textPrimary);
  const productNames = new Map(products.map((product) => [product.id, product.title]));

  return (
    <div className="flex flex-col gap-8">
      <section>
        <SectionHeading title="Créer une promotion" t={t} />
        <form onSubmit={handleSubmit} className={cx("mt-4 flex flex-col gap-4 rounded-xl border p-4", t.cardBorder, t.cardBg)}>
          <TextField label="Nom de l’offre" value={form.name} onChange={(value) => update("name", value)} required maxLength={120} t={t} />
          <label className="block">
            <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Type de réduction</span>
            <select value={form.discount_type} onChange={(event) => update("discount_type", event.target.value)} className={inputClass}>
              <option value="percentage">Pourcentage</option>
              <option value="fixed">Montant fixe par article</option>
              <option value="sale_price">Prix promotionnel par article</option>
            </select>
          </label>
          <TextField
            label={form.discount_type === "percentage" ? "Réduction (%)" : form.discount_type === "fixed" ? "Réduction par article" : "Nouveau prix par article"}
            type="number"
            min="0"
            max={form.discount_type === "percentage" ? "100" : undefined}
            step={form.discount_type === "percentage" ? "1" : "0.01"}
            value={form.value}
            onChange={(value) => update("value", value)}
            required
            t={t}
          />
          <fieldset className="flex flex-col gap-2">
            <legend className={cx("mb-1 text-sm font-medium", t.textPrimary)}>Annonces concernées</legend>
            {products.length === 0 ? (
              <p className={cx("text-sm", t.textMuted)}>Aucune annonce à sélectionner.</p>
            ) : products.map((product) => (
              <label key={product.id} className={cx("flex items-center gap-2 text-sm", t.textPrimary)}>
                <input type="checkbox" checked={form.products.includes(product.id)} onChange={() => toggleProduct(product.id)} className="h-4 w-4 accent-indigo-600" />
                <span className="min-w-0 flex-1 truncate">{product.title}</span>
                <span className={cx("text-xs", t.textMuted)}>{formatPrice(product.price, product.currency)}</span>
              </label>
            ))}
          </fieldset>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextField label="Quantité minimale de l’offre" type="number" min="1" value={form.min_quantity} onChange={(value) => update("min_quantity", value)} required t={t} />
            <TextField label="Achats antérieurs minimum (fidélité)" type="number" min="0" value={form.min_customer_purchases} onChange={(value) => update("min_customer_purchases", value)} required t={t} />
          </div>
          <label className={cx("flex items-start gap-3 rounded-lg border p-3 text-sm", t.border, t.cardBg)}>
            <input type="checkbox" checked={form.free_shipping} onChange={(event) => update("free_shipping", event.target.checked)} className="mt-0.5 h-4 w-4 accent-indigo-600" />
            <span>Offrir la livraison pour ces annonces</span>
          </label>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block">
              <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Début (facultatif)</span>
              <input type="datetime-local" value={form.starts_at} onChange={(event) => update("starts_at", event.target.value)} className={inputClass} />
            </label>
            <label className="block">
              <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Fin (facultatif)</span>
              <input type="datetime-local" value={form.ends_at} onChange={(event) => update("ends_at", event.target.value)} className={inputClass} />
            </label>
          </div>
          {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
          {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
          <Button type="submit" loading={saving} disabled={saving || form.products.length === 0}>Créer l’offre</Button>
        </form>
      </section>

      <section>
        <SectionHeading title="Mes promotions" t={t} />
        {loading ? <p className={cx("mt-3 text-sm", t.textMuted)}>Chargement…</p> : promotions.length === 0 ? (
          <p className={cx("mt-3 text-sm", t.textMuted)}>Aucune promotion créée.</p>
        ) : (
          <ul className={cx("mt-3 divide-y border-y", t.border)}>
            {promotions.map((promotion) => (
              <li key={promotion.id} className="flex flex-wrap items-center gap-3 py-3">
                <Tag className="h-4 w-4 shrink-0 text-emerald-600" />
                <div className="min-w-0 flex-1">
                  <p className={cx("text-sm font-semibold", t.textPrimary)}>{promotion.name}</p>
                  <p className={cx("text-xs", t.textMuted)}>
                    {promotion.discount_type === "percentage" ? `${promotion.value}%` : `${promotion.value} ${promotion.currency}`}
                    {promotion.free_shipping ? " · Livraison offerte" : ""}
                    {promotion.min_quantity > 1 ? ` · Dès ${promotion.min_quantity} articles` : ""}
                    {promotion.min_customer_purchases > 0 ? ` · Fidélité ${promotion.min_customer_purchases}+ achats` : ""}
                  </p>
                  <p className={cx("truncate text-xs", t.textMuted)}>{promotion.products.map((id) => productNames.get(id) || "Annonce").join(" · ")}</p>
                </div>
                <button type="button" onClick={() => handleDelete(promotion)} aria-label={`Supprimer ${promotion.name}`} className="rounded-lg border border-rose-200 p-2 text-rose-600 hover:bg-rose-50">
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}