import React from "react";
import { Link } from "react-router-dom";
import { Heart, ImageOff, MapPin } from "lucide-react";
import { cx } from "../../styles/theme";
import { formatPrice } from "../../lib/format";

const PLACEHOLDER_GRADIENTS = [
  "from-indigo-400 to-violet-600",
  "from-orange-400 to-rose-500",
  "from-emerald-400 to-teal-600",
  "from-sky-400 to-indigo-600",
];

export function ProductCard({ product, index = 0, t, onToggleFavorite, showSeller = false }) {
  const gradient = PLACEHOLDER_GRADIENTS[index % PLACEHOLDER_GRADIENTS.length];
  return (
    <div className={cx("group rounded-2xl border overflow-hidden transition hover:shadow-lg hover:-translate-y-0.5", t.cardBorder, t.cardBg)}>
      <div className="relative aspect-square">
        <Link to={`/produit/${product.id}`} className="block h-full w-full">
          {product.primary_image ? (
            <img src={product.primary_image} alt={product.title} className="h-full w-full object-cover" />
          ) : (
            <div className={cx("flex h-full w-full items-center justify-center bg-gradient-to-br", gradient)}>
              <ImageOff className="h-8 w-8 text-white/80" strokeWidth={1.5} />
            </div>
          )}
        </Link>
        {onToggleFavorite && (
          <button
            aria-label="Ajouter aux favoris"
            onClick={() => onToggleFavorite(product)}
            className="absolute right-2 top-2 rounded-full bg-black/30 p-1.5 text-white opacity-0 transition group-hover:opacity-100 hover:bg-black/50"
          >
            <Heart className="h-4 w-4" />
          </button>
        )}
        {product.status === "archived" && (
          <span className="absolute bottom-2 left-2 rounded-full bg-zinc-900/75 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-white">
            Archivé · non disponible
          </span>
        )}
        {product.item_type === "service" && (
          <span className="absolute left-2 top-2 rounded-full bg-emerald-700/90 px-2.5 py-1 text-[10px] font-semibold uppercase text-white">
            Service
          </span>
        )}
      </div>
      <Link to={`/produit/${product.id}`} className="block p-3">
        <div className={cx("mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.14em]", t.textMuted)}>
          <span>{product.category_name || "Catégorie"}</span>
          <span>{product.item_type === "service" ? "Service" : product.condition_display || "Produit"}</span>
        </div>
        <p className={cx("truncate text-sm font-medium", t.textPrimary)}>{product.title}</p>
        <p className={cx("mt-2 font-mono text-base font-semibold", t.textPrimary)}>
          {formatPrice(product.price, product.currency)}{product.item_type === "service" && product.price_unit !== "fixed" ? ` ${product.price_unit_display?.toLowerCase()}` : ""}
        </p>
        {product.item_type === "product" && product.comparison_identity && product.comparison_offer_count > 0 && (
          <p className={cx("mt-1 text-xs", t.textMuted)}>
            {product.comparison_offer_count} offre{product.comparison_offer_count > 1 ? "s" : ""} · dès {formatPrice(product.comparison_lowest_price, product.currency)}
          </p>
        )}
        <div className={cx("mt-2 flex items-center justify-between text-xs", t.textMuted)}>
          <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" /> {product.city}</span>
          <span>{product.item_type === "service" ? "Prestation" : "Prix"}</span>
        </div>
      </Link>
      {showSeller && product.seller_username && (
        <Link
          to={`/vendeurs/${product.seller_username}`}
          className={cx("mx-3 mb-3 flex items-center gap-2 border-t pt-3", t.border)}
        >
          {product.seller_avatar_url ? (
            <img
              src={product.seller_avatar_url}
              alt={`Photo de ${product.seller_username}`}
              className="h-7 w-7 shrink-0 rounded-full object-cover"
            />
          ) : (
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
              {product.seller_username.charAt(0).toUpperCase()}
            </span>
          )}
          <span className={cx("truncate text-xs font-medium", t.textMuted)}>{product.seller_username}</span>
        </Link>
      )}
    </div>
  );
}
