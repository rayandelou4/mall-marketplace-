import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, MessageCircle, PackageCheck } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, ErrorBlock } from "../components/ui/StatusBlocks";
import { Button, TextField } from "../components/ui/FormControls";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { useCart } from "../features/cart/CartContext";
import { fetchCountries, fetchAreas } from "../features/localization/api";
import { createOrder } from "../features/orders/api";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";

export default function CheckoutPage() {
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();
  const { items, clearCurrency } = useCart();
  const location = useLocation();
  const navigate = useNavigate();
  const currencies = [...new Set(items.map(({ product }) => product.currency || "USD"))];
  const [selectedCurrency, setSelectedCurrency] = useState(location.state?.currency || "");
  const activeCurrency = currencies.includes(selectedCurrency)
    ? selectedCurrency
    : currencies.length === 1 ? currencies[0] : "";
  const checkoutItems = items.filter(({ product }) => (product.currency || "USD") === activeCurrency);
  const hasUnavailableStock = checkoutItems.some(({ product, quantity }) => (
    product.stock_quantity != null
    && Number.isFinite(Number(product.stock_quantity))
    && quantity > Number(product.stock_quantity)
  ));

  const [shippingAddress, setShippingAddress] = useState("");
  const [countries, setCountries] = useState([]);
  const [areas, setAreas] = useState([]);
  const [selectedCountryId, setSelectedCountryId] = useState("");
  const [selectedAreaId, setSelectedAreaId] = useState("");
  const [step, setStep] = useState("form");
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth");
    } else if (items.length === 0 && step === "form") {
      navigate("/panier");
    }
  }, [isAuthenticated, items.length, navigate, step]);

  useEffect(() => {
    fetchCountries().then(setCountries).catch(() => setCountries([]));
  }, []);

  useEffect(() => {
    if (!selectedCountryId) {
      setAreas([]);
      setSelectedAreaId("");
      return;
    }
    fetchAreas({ country: selectedCountryId, level: "province" }).then(setAreas).catch(() => setAreas([]));
  }, [selectedCountryId]);

  const selectedCountry = countries.find((country) => country.id === selectedCountryId) || null;
  const selectedArea = areas.find((area) => area.id === selectedAreaId) || null;
  const formattedShippingAddress = [selectedCountry?.name, selectedArea?.name, shippingAddress]
    .filter(Boolean)
    .join(", ");

  async function handleConfirmOrder(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const createdOrder = await createOrder({ shippingAddress: formattedShippingAddress, items: checkoutItems });
      setOrder(createdOrder);
      clearCurrency(activeCurrency);
      setStep("done");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
        <SectionHeading title="Commande" t={t} />

        {error && <div className="mb-4"><ErrorBlock message={error} t={t} /></div>}

        {step === "form" && (
          <form onSubmit={handleConfirmOrder} className="flex flex-col gap-5">
            {!activeCurrency && currencies.length > 1 && (
              <div className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                <p className="mb-3 text-sm font-semibold">Choisissez le panier à commander</p>
                <div className="flex flex-wrap gap-2">
                  {currencies.map((currency) => (
                    <button key={currency} type="button" onClick={() => setSelectedCurrency(currency)} className={cx("rounded-full border px-4 py-2 text-sm font-semibold", t.border, t.textPrimary)}>
                      {currency} · {formatPrice(items
                        .filter(({ product }) => (product.currency || "USD") === currency)
                        .reduce((sum, { product, quantity }) => sum + Number(product.price) * quantity + Number(product.shipping_cost || 0), 0), currency)}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {hasUnavailableStock && <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">Le stock disponible a changé pour au moins un article. Retournez au panier et ajustez les quantités.</p>}
            <div className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
              <p className={cx("mb-2 text-sm font-semibold", t.textPrimary)}>Récapitulatif {activeCurrency}</p>
              {checkoutItems.map(({ product, quantity }) => (
                <div key={product.id} className="flex justify-between gap-4 py-1 text-sm">
                  <span className={t.textMuted}>{product.title} × {quantity}{Number(product.shipping_cost) > 0 ? ` · livraison ${formatPrice(product.shipping_cost, product.currency)}` : ""}</span>
                  <span className="shrink-0 font-mono">{formatPrice(Number(product.price) * quantity + Number(product.shipping_cost || 0), product.currency)}</span>
                </div>
              ))}
              {activeCurrency && <div className={cx("mt-2 flex justify-between border-t pt-2 text-sm font-semibold", t.border)}>
                <span>Total avec livraison ({activeCurrency})</span>
                <span className="font-mono">{formatPrice(checkoutItems.reduce((sum, { product, quantity }) => sum + Number(product.price) * quantity + Number(product.shipping_cost || 0), 0), activeCurrency)}</span>
              </div>}
            </div>

            <TextField
              label="Adresse de livraison"
              value={shippingAddress}
              onChange={setShippingAddress}
              placeholder="Quartier, avenue, ville, pays"
              required
              t={t}
            />

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Pays</span>
                <select value={selectedCountryId} onChange={(event) => { setSelectedCountryId(event.target.value); setSelectedAreaId(""); }} className={cx("w-full rounded-xl border px-4 py-2.5 text-sm", t.inputBg, t.border, t.textPrimary)}>
                  <option value="">Sélectionner</option>
                  {countries.map((country) => (
                    <option key={country.id} value={country.id}>{country.name}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Province</span>
                <select value={selectedAreaId} onChange={(event) => setSelectedAreaId(event.target.value)} className={cx("w-full rounded-xl border px-4 py-2.5 text-sm", t.inputBg, t.border, t.textPrimary)} disabled={!selectedCountryId}>
                  <option value="">Sélectionner</option>
                  {areas.map((area) => (
                    <option key={area.id} value={area.id}>{area.name}</option>
                  ))}
                </select>
              </label>
            </div>

            <p className={cx("text-xs", t.textMuted)}>
              Adresse finale: {formattedShippingAddress || "Compléter la livraison"}
            </p>

            <fieldset>
              <legend className={cx("mb-2 block text-sm font-medium", t.textPrimary)}>Moyen de paiement</legend>
              <div className={cx("flex items-center gap-3 rounded-xl border p-4", t.border, t.cardBg)}>
                <input type="radio" name="payment-method" checked readOnly aria-label="Espèces à la remise" />
                <span className="flex-1">
                  <span className={cx("block text-sm font-semibold", t.textPrimary)}>Paiement en espèces à la remise</span>
                  <span className={cx("mt-0.5 block text-xs", t.textMuted)}>Vous payez le vendeur en main propre.</span>
                </span>
              </div>
              <div className={cx("mt-2 flex items-center justify-between gap-3 rounded-xl border p-4 opacity-55", t.border)} aria-disabled="true">
                <span className="text-sm text-zinc-500">Mobile Money (M-Pesa, Orange Money, Airtel Money)</span>
                <span className="shrink-0 rounded-full bg-zinc-200 px-2.5 py-1 text-[10px] font-semibold text-zinc-600">Bientôt disponible</span>
              </div>
            </fieldset>

            <Button type="submit" loading={loading} disabled={loading || !activeCurrency || checkoutItems.length === 0 || hasUnavailableStock}>Enregistrer la commande {activeCurrency}</Button>
          </form>
        )}

        {step === "done" && order && (
          <div className={cx("flex flex-col items-center gap-4 rounded-2xl border p-8 text-center", t.cardBorder, t.cardBg)}>
            <CheckCircle2 className="h-10 w-10 text-emerald-500" />
            <h2 className={cx("text-lg font-semibold", t.textPrimary)}>Commande enregistrée</h2>
            <p className={cx("max-w-lg text-sm", t.textMuted)}>Convenez de la remise avec le vendeur via la messagerie et payez en main propre.</p>
            <p className={cx("text-xs", t.textMuted)}>Commande #{order.id.slice(0, 8)} · {formatPrice(order.total_amount, order.currency)}</p>
            <div className="flex flex-wrap justify-center gap-3">
              <Link to="/mes-commandes" className="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white">
                <PackageCheck className="h-4 w-4" /> Mes commandes
              </Link>
              <Link to="/messages" className={cx("inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-semibold", t.border, t.textPrimary)}>
                <MessageCircle className="h-4 w-4" /> Messages
              </Link>
            </div>
          </div>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
