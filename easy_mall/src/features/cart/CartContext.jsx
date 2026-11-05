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

function getStockLimit(product) {
  const stock = Number(product.stock_quantity);
  return Number.isFinite(stock) ? Math.max(0, Math.floor(stock)) : Infinity;
}

export function CartProvider({ children }) {
  const { user } = useAuth();
  const storageKey = `mall_cart:${user?.id || "guest"}`;
  const [items, setItems] = useState(() => loadInitialCart(storageKey));

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(items));
  }, [items, storageKey]);

  function addItem(product, quantity = 1) {
    setItems((prev) => {
      const maxQty = getStockLimit(product);
      const requestedQuantity = Math.max(1, Math.floor(Number(quantity) || 1));
      if (maxQty < 1) return prev;
      const existing = prev.find((i) => i.product.id === product.id);
      if (existing) {
        return prev.map((i) =>
          i.product.id === product.id ? { ...i, product, quantity: Math.min(i.quantity + requestedQuantity, maxQty) } : i
        );
      }
      return [...prev, { product, quantity: Math.min(requestedQuantity, maxQty) }];
    });
  }

  function updateQuantity(productId, quantity) {
    setItems((prev) =>
      quantity <= 0
        ? prev.filter((i) => i.product.id !== productId)
        : prev.map((i) => {
          if (i.product.id !== productId) return i;
          const requestedQuantity = Math.floor(Number(quantity));
          if (!Number.isFinite(requestedQuantity)) return i;
          return {
            ...i,
            quantity: Math.min(Math.max(1, requestedQuantity), Math.max(1, getStockLimit(i.product))),
          };
        })
    );
  }

  function removeItem(productId) {
    setItems((prev) => prev.filter((i) => i.product.id !== productId));
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
