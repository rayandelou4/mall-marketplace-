import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Minus, Plus, Trash2, ImageOff } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading } from "../components/ui/StatusBlocks";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { useCart } from "../features/cart/CartContext";
import { formatPrice } from "../lib/format";
import { cx } from "../styles/theme";

export default function CartPage() {
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();
  const { items, totalItems, updateQuantity, removeItem } = useCart();
  const navigate = useNavigate();
  const itemsByCurrency = items.reduce((groups, item) => {
    const currency = item.product.currency || "USD";
    groups[currency] = [...(groups[currency] || []), item];
    return groups;
  }, {});

  function handleCheckout(currency) {
    if (!isAuthenticated) return navigate("/auth");
    navigate("/commande", { state: { currency } });
  }

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <SectionHeading title="Mon panier" subtitle={`${totalItems} article${totalItems > 1 ? "s" : ""}`} t={t} />

        {items.length === 0 ? (
          <div className={cx("rounded-2xl border p-8 text-center text-sm", t.cardBorder, t.textMuted)}>
            Votre panier est vide.{" "}
            <Link to="/catalogue" className="font-semibold text-indigo-600 hover:underline">Parcourir le catalogue</Link>
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-8">
              {Object.entries(itemsByCurrency).map(([currency, currencyItems]) => {
                const total = currencyItems.reduce((sum, { product, quantity }) => (
                  sum + Number(product.price) * quantity
                    + (product.sale_method === "pickup" ? 0 : Number(product.shipping_cost || 0))
                ), 0);
                const hasUnavailableStock = currencyItems.some(({ product, quantity }) => (
                  product.stock_quantity != null
                  && Number.isFinite(Number(product.stock_quantity))
                  && quantity > Number(product.stock_quantity)
                ));

                return (
                  <section key={currency} aria-labelledby={`cart-${currency}`}>
                    <h2 id={`cart-${currency}`} className="mb-3 text-lg font-semibold">Panier {currency}</h2>
                    <div className="flex flex-col gap-4">
                      {currencyItems.map(({ product, quantity }) => (
                        <div key={product.id} className={cx("flex items-center gap-4 rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                          <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl">
                            {product.primary_image ? (
                              <img src={product.primary_image} alt={product.title} className="h-full w-full object-cover" />
                            ) : (
                              <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-indigo-400 to-violet-600">
                                <ImageOff className="h-5 w-5 text-white/80" />
                              </div>
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <Link to={`/produit/${product.id}`} className={cx("text-sm font-medium hover:underline", t.textPrimary)}>
                              {product.title}
                            </Link>
                            <p className="font-mono text-sm text-indigo-600">{formatPrice(Number(product.price) * quantity, currency)} · {quantity}</p>
                            <p className={cx("text-xs", t.textMuted)}>
                              {product.sale_method === "pickup" ? "Remise en main propre" : `Livraison${Number(product.shipping_cost) > 0 ? ` : ${formatPrice(product.shipping_cost, currency)}` : ""}`}
                            </p>
                            {product.stock_quantity != null && quantity > Number(product.stock_quantity) && <p className="text-xs font-medium text-rose-600">Stock insuffisant : {product.stock_quantity} disponible(s).</p>}
                          </div>
                          <div className={cx("flex items-center gap-2 rounded-full border px-2 py-1", t.border)}>
                            <button type="button" onClick={() => updateQuantity(product.id, quantity - 1)} aria-label="Diminuer la quantité">
                              <Minus className="h-3.5 w-3.5" />
                            </button>
                            <span className="w-5 text-center text-sm">{quantity}</span>
                            <button type="button" onClick={() => updateQuantity(product.id, quantity + 1)} disabled={product.stock_quantity != null && quantity >= Number(product.stock_quantity)} aria-label="Augmenter la quantité" className="disabled:cursor-not-allowed disabled:opacity-40">
                              <Plus className="h-3.5 w-3.5" />
                            </button>
                          </div>
                          <button type="button" onClick={() => removeItem(product.id)} aria-label="Retirer du panier" className="text-rose-500 hover:text-rose-600">
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                    <div className={cx("mt-4 rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
                      <div className="flex justify-between text-sm">
                        <span className={t.textMuted}>Total ({currency})</span>
                        <span className="font-mono font-semibold">{formatPrice(total, currency)}</span>
                      </div>
                      {hasUnavailableStock && <p className="mt-3 text-sm text-rose-600">La quantité d’au moins un article dépasse le stock disponible. Ajustez-la pour continuer.</p>}
                      <button
                        type="button"
                        onClick={() => handleCheckout(currency)}
                        disabled={hasUnavailableStock}
                        className="mt-4 w-full rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Commander en {currency}
                      </button>
                    </div>
                  </section>
                );
              })}
            </div>
          </>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
