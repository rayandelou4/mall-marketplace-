import React, { useEffect, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { ProductCard } from "../components/catalog/ProductCard";
import { SectionHeading } from "../components/ui/StatusBlocks";
import { fetchBuyerAssistantConfig, askBuyerAssistant } from "../features/catalog/buyerAssistantApi";
import { useTheme } from "../features/theme/ThemeContext";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";

const EXAMPLES = [
  "Je cherche un ordinateur portable pour mes études avec un budget de 350 dollars.",
  "Un téléphone en bon état, pas plus de 200 USD.",
];

export default function BuyerAssistantPage() {
  const { t } = useTheme();
  const [enabled, setEnabled] = useState(false);
  const [configLoading, setConfigLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [response, setResponse] = useState(null);

  useEffect(() => {
    let active = true;
    fetchBuyerAssistantConfig()
      .then(({ enabled: isEnabled }) => { if (active) setEnabled(Boolean(isEnabled)); })
      .catch(() => { if (active) setEnabled(false); })
      .finally(() => { if (active) setConfigLoading(false); });
    return () => { active = false; };
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!enabled || !message.trim()) return;
    setSearching(true);
    setError(null);
    setResponse(null);
    try {
      setResponse(await askBuyerAssistant(message.trim()));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSearching(false);
    }
  }

  const criteria = response?.criteria || {};
  const offers = response?.offers || [];
  const priceRanges = Object.entries(offers.reduce((totals, { product }) => {
    const price = Number(product.price);
    const currency = product.currency;
    const current = totals[currency] || { min: price, max: price };
    totals[currency] = { min: Math.min(current.min, price), max: Math.max(current.max, price) };
    return totals;
  }, {}));

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />
      <main className="mx-auto min-h-[65vh] max-w-5xl px-4 py-10 sm:px-6">
        <SectionHeading
          eyebrow="Assistant d’achat"
          title="Trouvez ce qui vous convient"
          subtitle="Décrivez votre besoin, vos priorités et votre budget. Les recommandations proviennent uniquement des annonces disponibles."
          t={t}
        />

        <form onSubmit={handleSubmit} className={cx("mt-7 border-y py-5", t.border)}>
          <label htmlFor="buyer-assistant-message" className={cx("mb-2 block text-sm font-semibold", t.textPrimary)}>
            Que recherchez-vous ?
          </label>
          <textarea
            id="buyer-assistant-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            maxLength={1200}
            rows={4}
            placeholder="Ex. un ordinateur portable pour mes études, avec un budget de 350 dollars…"
            className={cx("w-full resize-y rounded-xl border px-4 py-3 text-sm outline-none focus:border-indigo-500", t.inputBg, t.border, t.textPrimary)}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className={cx("text-xs", t.textMuted)}>
              {configLoading
                ? "Vérification de la disponibilité…"
                : enabled
                  ? "Les prix, vendeurs et disponibilités sont vérifiés dans le catalogue."
                  : "Assistant non configuré. Aucune recommandation simulée ne sera affichée."}
            </p>
            <button
              type="submit"
              disabled={!enabled || configLoading || searching || !message.trim()}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {searching ? <Sparkles className="h-4 w-4 animate-pulse" /> : <Send className="h-4 w-4" />}
              {searching ? "Recherche…" : "Chercher des offres"}
            </button>
          </div>
          {!enabled && !configLoading && (
            <div className={cx("mt-4 flex flex-wrap gap-2", t.textMuted)}>
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setMessage(example)}
                  className={cx("min-h-11 rounded-lg border px-3 py-2 text-left text-xs", t.border, t.textPrimary)}
                >
                  {example}
                </button>
              ))}
            </div>
          )}
        </form>

        {error && <p role="alert" className="mt-5 text-sm text-rose-600">{error}</p>}
        {response && (
          <section className="mt-8" aria-live="polite">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className={cx("text-lg font-semibold", t.textPrimary)}>Offres disponibles ({offers.length})</h2>
                <p className={cx("mt-1 text-sm", t.textMuted)}>
                  {criteria.max_price != null && criteria.currency
                    ? `Budget appliqué : ${formatPrice(criteria.max_price, criteria.currency)}`
                    : "Aucun budget détecté"}
                  {criteria.important_features?.length > 0 && ` · Priorités : ${criteria.important_features.join(", ")}`}
                </p>
                {priceRanges.length > 0 && (
                  <p className={cx("mt-1 text-xs", t.textMuted)}>
                    Écarts comparés séparément par devise : {priceRanges.map(([currency, range]) => (
                      `${currency} ${formatPrice(range.min, currency)}${range.min !== range.max ? ` à ${formatPrice(range.max, currency)}` : ""}`
                    )).join(" · ")}
                  </p>
                )}
              </div>
              {criteria.keywords?.length > 0 && (
                <p className={cx("text-xs", t.textMuted)}>Critères : {criteria.keywords.join(", ")}</p>
              )}
            </div>
            {offers.length ? (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {offers.map(({ product, reasons }, index) => (
                  <div key={product.id}>
                    <ProductCard product={product} index={index} t={t} showSeller />
                    <div className={cx("mt-2 border-t pt-2 text-xs", t.border, t.textMuted)}>
                      <p className="font-medium">Points de comparaison</p>
                      <ul className="mt-1 list-inside list-disc">
                        {(reasons || []).map((reason) => <li key={reason}>{reason}</li>)}
                        <li>État : {product.condition_display || "non précisé"}</li>
                        <li>Stock disponible : {product.stock_quantity}</li>
                        <li>Vendeur : {product.seller_username} · note {Number(product.seller_rating || 0).toFixed(1)} / 5</li>
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className={cx("border-y py-8 text-center text-sm", t.border, t.textMuted)}>
                Aucune annonce disponible ne correspond à ces critères.
              </p>
            )}
          </section>
        )}
      </main>
      <SiteFooter t={t} />
    </div>
  );
}