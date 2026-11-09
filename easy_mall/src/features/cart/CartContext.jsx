import React, { createContext, useContext, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";

const CartContext = createContext(null);

function loadInitialCart(storageKey) {
  try {
    const raw = localStorage.getItem(storageKey);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function getStockLimit(product, variant = null) {
  const stock = Number(variant ? variant.stock_quantity : product.stock_quantity);
  return Number.isFinite(stock) ? Math.max(0, Math.floor(stock)) : Infinity;
}

function isSameEntry(item, productId, variantId) {
  return item.product.id === productId && (item.variant?.id || null) === (variantId || null);
}

export function CartProvider({ children }) {
  const { user } = useAuth();
  const storageKey = `mall_cart:${user?.id || "guest"}`;
  const [items, setItems] = useState(() => loadInitialCart(storageKey));

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(items));
  }, [items, storageKey]);

  function addItem(product, quantity = 1, visitorId = null, variant = null) {
    setItems((prev) => {
      const maxQty = getStockLimit(product, variant);
      const requestedQuantity = Math.max(1, Math.floor(Number(quantity) || 1));
      if (maxQty < 1) return prev;
      const existing = prev.find((item) => isSameEntry(item, product.id, variant?.id));
      if (existing) {
        return prev.map((i) =>
          isSameEntry(i, product.id, variant?.id) ? { ...i, product, variant, visitorId: visitorId || i.visitorId, quantity: Math.min(i.quantity + requestedQuantity, maxQty) } : i
        );
      }
      return [...prev, { product, variant, quantity: Math.min(requestedQuantity, maxQty), visitorId }];
    });
  }

  function updateQuantity(productId, quantity, variantId = null) {
    setItems((prev) =>
      quantity <= 0
        ? prev.filter((item) => !isSameEntry(item, productId, variantId))
        : prev.map((i) => {
          if (!isSameEntry(i, productId, variantId)) return i;
          const requestedQuantity = Math.floor(Number(quantity));
          if (!Number.isFinite(requestedQuantity)) return i;
          return {
            ...i,
            quantity: Math.min(Math.max(1, requestedQuantity), Math.max(1, getStockLimit(i.product, i.variant))),
          };
        })
    );
  }

  function removeItem(productId, variantId = null) {
    setItems((prev) => prev.filter((item) => !isSameEntry(item, productId, variantId)));
  }

  function clear() {
    setItems([]);
  }

  function clearCurrency(currency) {
    setItems((prev) => prev.filter((item) => item.product.currency !== currency));
  }

  const totalItems = items.reduce((sum, i) => sum + i.quantity, 0);

  // Total par devise : un panier peut mélanger USD et CDF, hors de question
  // de les additionner directement.
  const totalsByCurrency = items.reduce((totals, i) => {
    const key = i.product.currency;
    totals[key] = (totals[key] || 0)
      + Number(i.product.price) * i.quantity
      + (i.product.sale_method === "pickup" ? 0 : Number(i.product.shipping_cost || 0));
    return totals;
  }, {});

  const value = { items, addItem, updateQuantity, removeItem, clear, clearCurrency, totalItems, totalsByCurrency };
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart() doit être appelé à l'intérieur d'un <CartProvider>.");
  return ctx;
}
