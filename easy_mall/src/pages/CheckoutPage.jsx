import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, MessageCircle, PackageCheck } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, ErrorBlock } from "../components/ui/StatusBlocks";
import { AreaField, Button, TextField } from "../components/ui/FormControls";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { useCart } from "../features/cart/CartContext";
import {
  createPrivateAddress,
  fetchCountries,
  fetchAreas,
  fetchPrivateAddresses,
  updatePrivateAddress,
} from "../features/localization/api";
import { createOrder } from "../features/orders/api";
import { fetchCheckoutQuote, fetchLoyaltyStatus } from "../features/promotions/api";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";
import { WORLD_COUNTRIES } from "../features/localization/countries";

function getItemShippingCost(product) {
  return product.sale_method === "pickup" ? 0 : Number(product.shipping_cost || 0);
}

function getItemUnitPrice(product, negotiation) {
  return Number(negotiation?.accepted_price ?? product.price);
}

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
  const requiresDelivery = checkoutItems.some(({ product }) => product.sale_method !== "pickup");
  const hasUnavailableStock = checkoutItems.some(({ product, variant, quantity }) => {
    if (product.variants?.length && !variant) return true;
    const available = variant ? variant.stock_quantity : product.stock_quantity;
    return available != null
      && Number.isFinite(Number(available))
      && quantity > Number(available);
  });

  const [privateAddresses, setPrivateAddresses] = useState([]);
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const [isAddingAddress, setIsAddingAddress] = useState(false);
  const [addressDraft, setAddressDraft] = useState({
    label: "",
    countryId: "",
    countryCode: "",
    countryName: "",
    areaName: "",
    streetAddress: "",
    landmark: "",
    phoneNumber: "",
  });
  const [countries, setCountries] = useState([]);
  const [areas, setAreas] = useState([]);
  const [addressLoading, setAddressLoading] = useState(false);
  const [addressError, setAddressError] = useState(null);
  const [defaultAddressLoading, setDefaultAddressLoading] = useState(false);
  const [step, setStep] = useState("form");
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loyalty, setLoyalty] = useState(null);
  const [pointsToRedeem, setPointsToRedeem] = useState(0);
  const [checkoutQuote, setCheckoutQuote] = useState(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState(null);
  const quoteItemsKey = JSON.stringify(checkoutItems.map(({ product, variant, quantity, visitorId, negotiation }) => ({
    product_id: product.id,
    ...(variant?.id ? { variant_id: variant.id } : {}),
    ...(negotiation?.id ? { negotiation_id: negotiation.id } : {}),
    quantity,
    ...(visitorId ? { conversion_visitor_id: visitorId } : {}),
    unit_price: negotiation?.accepted_price ?? product.price,
    shipping_cost: product.shipping_cost || 0,
  })));

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
    if (!isAuthenticated) return;
    fetchPrivateAddresses()
      .then((savedAddresses) => {
        setPrivateAddresses(savedAddresses);
        setSelectedAddressId(
          savedAddresses.find((address) => address.is_default)?.id
            || savedAddresses[0]?.id
            || ""
        );
      })
      .catch((err) => setAddressError(err.message));
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchLoyaltyStatus().then(setLoyalty).catch(() => setLoyalty(null));
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || !activeCurrency || !checkoutItems.length) {
      setCheckoutQuote(null);
      setQuoteLoading(false);
      return undefined;
    }
    let active = true;
    setQuoteLoading(true);
    setQuoteError(null);
    setCheckoutQuote(null);
    fetchCheckoutQuote({
      items: JSON.parse(quoteItemsKey),
      points_to_redeem: Number(pointsToRedeem) || 0,
    })
      .then((quote) => { if (active) setCheckoutQuote(quote); })
      .catch((quoteRequestError) => { if (active) setQuoteError(quoteRequestError.message); })
      .finally(() => { if (active) setQuoteLoading(false); });
    return () => { active = false; };
  }, [isAuthenticated, activeCurrency, quoteItemsKey, pointsToRedeem, checkoutItems.length]);

  useEffect(() => {
    if (!addressDraft.countryId) {
      setAreas([]);
      return;
    }
    fetchAreas({ country: addressDraft.countryId, level: "province" })
      .then(setAreas)
      .catch(() => setAreas([]));
  }, [addressDraft.countryId]);

  const selectedAddress = privateAddresses.find((address) => address.id === selectedAddressId) || null;

  async function handleSaveAddress() {
    setAddressLoading(true);
    setAddressError(null);
    try {
      const savedAddress = await createPrivateAddress({
        label: addressDraft.label,
        ...(addressDraft.countryId
          ? { country_id: addressDraft.countryId }
          : { country_code: addressDraft.countryCode, country_name: addressDraft.countryName }),
        administrative_area_id: null,
        administrative_area_name: addressDraft.areaName,
        street_address: addressDraft.streetAddress,
        landmark: addressDraft.landmark,
        phone_number: addressDraft.phoneNumber,
        is_default: privateAddresses.length === 0,
      });
      setPrivateAddresses((current) => [savedAddress, ...current]);
      setSelectedAddressId(savedAddress.id);
      setIsAddingAddress(false);
    } catch (err) {
      setAddressError(err.message);
    } finally {
      setAddressLoading(false);
    }
  }

  async function handleSetDefaultAddress() {
    if (!selectedAddressId || selectedAddress?.is_default) return;
    setDefaultAddressLoading(true);
    setAddressError(null);
    try {
      await updatePrivateAddress(selectedAddressId, { is_default: true });
      setPrivateAddresses((current) => current.map((address) => ({
        ...address,
        is_default: address.id === selectedAddressId,
      })));
    } catch (err) {
      setAddressError(err.message);
    } finally {
      setDefaultAddressLoading(false);
    }
  }

  async function handleConfirmOrder(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (requiresDelivery && !selectedAddressId) {
        setError("Sélectionnez ou ajoutez une adresse de livraison.");
        return;
      }
      const createdOrder = await createOrder({
        privateAddressId: requiresDelivery ? selectedAddressId : undefined,
        items: checkoutItems,
        pointsToRedeem,
      });
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
                        .reduce((sum, { product, quantity, negotiation }) => sum + getItemUnitPrice(product, negotiation) * quantity + getItemShippingCost(product), 0), currency)}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {hasUnavailableStock && <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">Le stock disponible a changé pour au moins un article. Retournez au panier et ajustez les quantités.</p>}
            <div className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
              <p className={cx("mb-2 text-sm font-semibold", t.textPrimary)}>Récapitulatif {activeCurrency}</p>
              {checkoutItems.map(({ product, variant, quantity, negotiation }) => {
                const quoteLine = checkoutQuote?.items.find((line) => line.product_id === product.id
                  && line.variant_id === (variant?.id || null)
                  && line.negotiation_id === (negotiation?.id || null));
                const lineAmount = quoteLine
                  ? Number(quoteLine.unit_price) * quantity + Number(quoteLine.shipping_cost) - Number(quoteLine.loyalty_discount)
                  : getItemUnitPrice(product, negotiation) * quantity + getItemShippingCost(product);
                return (
                <div key={`${product.id}:${variant?.id || ""}:${negotiation?.id || ""}`} className="flex justify-between gap-4 py-1 text-sm">
                  <span className={t.textMuted}>
                    {product.title}{variant ? ` · ${variant.label}` : ""} × {quantity}{product.sale_method === "pickup"
                      ? " · retrait en boutique"
                      : quoteLine?.original_shipping_cost > 0 && quoteLine.shipping_cost === 0
                        ? " · livraison offerte"
                        : ` · livraison${getItemShippingCost(product) > 0 ? ` ${formatPrice(quoteLine?.shipping_cost ?? getItemShippingCost(product), product.currency)}` : ""}`}
                    {quoteLine?.promotion_name && <span className="block text-xs font-medium text-emerald-700">{quoteLine.promotion_name}</span>}
                  </span>
                  <span className="shrink-0 text-right font-mono">
                    {quoteLine?.promotion_discount > 0 && <span className={cx("mr-2 text-xs line-through", t.textMuted)}>{formatPrice(Number(quoteLine.original_unit_price) * quantity + Number(quoteLine.original_shipping_cost), product.currency)}</span>}
                    {formatPrice(lineAmount, product.currency)}
                    {quoteLine?.loyalty_discount > 0 && <span className="block text-xs text-emerald-700">Fidélité −{formatPrice(quoteLine.loyalty_discount, product.currency)}</span>}
                  </span>
                </div>
              );})}
              {loyalty?.is_active && loyalty.points_balance > 0 && (
                <label className={cx("mt-3 flex flex-wrap items-center justify-between gap-3 border-t pt-3 text-sm", t.border)}>
                  <span>
                    <span className={cx("block font-medium", t.textPrimary)}>Points fidélité</span>
                    <span className={cx("text-xs", t.textMuted)}>{loyalty.points_balance} point(s) disponibles · maximum {loyalty.max_redemption_percent}% du panier</span>
                  </span>
                  <input
                    type="number"
                    min="0"
                    max={loyalty.points_balance}
                    step="1"
                    value={pointsToRedeem}
                    onChange={(event) => setPointsToRedeem(Math.min(loyalty.points_balance, Math.max(0, Number(event.target.value) || 0)))}
                    aria-label="Points fidélité à utiliser"
                    className={cx("w-28 rounded-lg border px-3 py-2", t.border, t.inputBg, t.textPrimary)}
                  />
                </label>
              )}
              {quoteLoading && <p className={cx("mt-2 text-xs", t.textMuted)}>Calcul des promotions…</p>}
              {quoteError && <p className="mt-2 text-xs text-amber-700">Aperçu indisponible : le total sera recalculé par le serveur à la commande.</p>}
              {activeCurrency && <div className={cx("mt-2 flex justify-between border-t pt-2 text-sm font-semibold", t.border)}>
                <span>Total à payer ({activeCurrency})</span>
                <span className="font-mono">{formatPrice(checkoutQuote?.total ?? checkoutItems.reduce((sum, { product, quantity, negotiation }) => sum + getItemUnitPrice(product, negotiation) * quantity + getItemShippingCost(product), 0), activeCurrency)}</span>
              </div>}
              {checkoutQuote?.loyalty_discount > 0 && <p className={cx("mt-1 text-right text-xs", t.textMuted)}>{checkoutQuote.points_redeemed} point(s) utilisés · Économie {formatPrice(checkoutQuote.loyalty_discount, activeCurrency)}</p>}
            </div>

            {requiresDelivery ? <section className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className={cx("text-sm font-semibold", t.textPrimary)}>Adresse de livraison</h2>
                  <p className={cx("mt-1 text-xs", t.textMuted)}>Visible uniquement pour vous et les personnes autorisées à traiter cette commande.</p>
                  <p className={cx("mt-1 text-xs", t.textMuted)}>L’adresse par défaut de votre profil est présélectionnée. Vous pouvez en choisir une autre ou en ajouter une pour cette commande.</p>
                </div>
                {privateAddresses.length > 0 && (
                  <button type="button" onClick={() => setIsAddingAddress(!isAddingAddress)} className="text-sm font-semibold text-indigo-600">
                    {isAddingAddress ? "Choisir une adresse" : "Ajouter une adresse"}
                  </button>
                )}
              </div>

              {addressError && <p role="alert" className="mt-3 text-sm text-rose-600">{addressError}</p>}

              {!isAddingAddress && privateAddresses.length > 0 && (
                <div className="mt-4 flex flex-col gap-3">
                  <label className="block">
                    <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Adresse enregistrée</span>
                    <select value={selectedAddressId} onChange={(event) => setSelectedAddressId(event.target.value)} required className={cx("w-full rounded-xl border px-4 py-2.5 text-sm", t.inputBg, t.border, t.textPrimary)}>
                      <option value="">Sélectionner une adresse</option>
                      {privateAddresses.map((address) => (
                        <option key={address.id} value={address.id}>
                          {[address.label || "Adresse", address.locality?.name, address.administrative_area?.name, address.country?.name].filter(Boolean).join(" · ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedAddress && (
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className={cx("text-sm", t.textMuted)}>
                        {[selectedAddress.street_address, selectedAddress.landmark, selectedAddress.locality?.name, selectedAddress.administrative_area?.name || selectedAddress.administrative_area_name, selectedAddress.country?.name].filter(Boolean).join(", ")}
                      </p>
                      <button type="button" onClick={handleSetDefaultAddress} disabled={defaultAddressLoading || selectedAddress.is_default} className="text-xs font-semibold text-indigo-600 disabled:text-emerald-700">
                        {selectedAddress.is_default ? "Adresse par défaut" : defaultAddressLoading ? "Enregistrement…" : "Définir par défaut"}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {(isAddingAddress || privateAddresses.length === 0) && (
                <div className="mt-4 flex flex-col gap-4">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <TextField label="Nom de l’adresse (facultatif)" value={addressDraft.label} onChange={(value) => setAddressDraft((current) => ({ ...current, label: value }))} placeholder="Maison, travail" t={t} />
                    <label className="block">
                      <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Pays</span>
                      <select value={addressDraft.countryCode} onChange={(event) => {
                        const country = WORLD_COUNTRIES.find((item) => item.code === event.target.value);
                        const saved = countries.find((item) => item.code === event.target.value
                          || (event.target.value === "CD" && item.code === "COD"));
                        setAddressDraft((current) => ({
                          ...current,
                          countryId: saved?.id || "",
                          countryCode: country?.code || "",
                          countryName: country?.name || "",
                          areaName: "",
                        }));
                      }} required className={cx("w-full rounded-xl border px-4 py-2.5 text-sm", t.inputBg, t.border, t.textPrimary)}>
                        <option value="">Sélectionner</option>
                        {WORLD_COUNTRIES.map((country) => <option key={country.code} value={country.code}>{country.name}</option>)}
                      </select>
                    </label>
                  </div>
                  <AreaField label="Province / région (facultatif)" value={addressDraft.areaName} onChange={(value) => setAddressDraft((current) => ({ ...current, areaName: value }))} areas={areas} placeholder="Choisir une suggestion ou saisir une région" maxLength={150} t={t} />
                  <TextField label="Adresse détaillée" value={addressDraft.streetAddress} onChange={(value) => setAddressDraft((current) => ({ ...current, streetAddress: value }))} placeholder="Avenue, numéro ou repère" required t={t} />
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <TextField label="Repère (facultatif)" value={addressDraft.landmark} onChange={(value) => setAddressDraft((current) => ({ ...current, landmark: value }))} placeholder="Près du marché" t={t} />
                    <TextField label="Téléphone (facultatif)" value={addressDraft.phoneNumber} onChange={(value) => setAddressDraft((current) => ({ ...current, phoneNumber: value }))} type="tel" autoComplete="tel" t={t} />
                  </div>
                  <Button type="button" loading={addressLoading} disabled={addressLoading || !addressDraft.countryCode || !addressDraft.streetAddress.trim()} onClick={handleSaveAddress}>
                    Enregistrer cette adresse
                  </Button>
                </div>
              )}
            </section> : (
              <p className={cx("rounded-xl border p-4 text-sm", t.border, t.textMuted)}>
                Cette commande se fera en remise en boutique. Aucune adresse de livraison n’est nécessaire.
              </p>
            )}

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

            <Button type="submit" loading={loading} disabled={loading || (requiresDelivery && !selectedAddressId) || !activeCurrency || checkoutItems.length === 0 || hasUnavailableStock}>Enregistrer la commande {activeCurrency}</Button>
          </form>
        )}

        {step === "done" && order && (
          <div className={cx("flex flex-col items-center gap-4 rounded-2xl border p-8 text-center", t.cardBorder, t.cardBg)}>
            <CheckCircle2 className="h-10 w-10 text-emerald-500" />
            <h2 className={cx("text-lg font-semibold", t.textPrimary)}>
              {order.orders?.length > 1 ? "Commandes enregistrées" : "Commande enregistrée"}
            </h2>
            <p className={cx("max-w-lg text-sm", t.textMuted)}>
              {order.items?.some((item) => item.sale_method === "pickup") && order.items?.some((item) => item.sale_method !== "pickup")
                ? "Convenez avec les vendeurs, via la messagerie, des modalités de retrait en boutique et de livraison."
                : order.items?.some((item) => item.sale_method !== "pickup")
                  ? "Le vendeur organisera la livraison. Convenez des détails via la messagerie."
                  : "Convenez du retrait en boutique avec le vendeur via la messagerie et payez en main propre."}
            </p>
            <p className={cx("text-xs", t.textMuted)}>Commande #{order.id.slice(0, 8)} · {formatPrice(order.total_amount, order.currency)}</p>
            {order.orders?.length > 0 && (
              <div className={cx("w-full max-w-lg divide-y border-y text-left", t.border)}>
                {order.orders.map((sellerOrder) => (
                  <div key={sellerOrder.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                    <div className="min-w-0">
                      <p className={cx("font-semibold", t.textPrimary)}>
                        {sellerOrder.items?.[0]?.seller_username || "Vendeur"}
                      </p>
                      <p className={cx("text-xs", t.textMuted)}>
                        Commande #{sellerOrder.id.slice(0, 8)} · {sellerOrder.items?.length || 0} article(s)
                      </p>
                    </div>
                    <span className="shrink-0 font-mono text-sm">
                      {formatPrice(sellerOrder.total_amount, sellerOrder.currency)}
                    </span>
                  </div>
                ))}
              </div>
            )}
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
