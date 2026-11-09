import { apiRequest, unwrap } from "../../lib/apiClient";

function buildQuery(params) {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== "" && v !== null)
  );
  return new URLSearchParams(clean).toString();
}

export const fetchCategories = () => apiRequest("/catalog/categories/").then(unwrap);

export function fetchProducts(params = {}) {
  const query = buildQuery(params);
  return apiRequest(`/catalog/products/${query ? `?${query}` : ""}`).then(unwrap);
}

// Version non "déballée" : garde count/next/previous, nécessaire pour la pagination.
export function fetchProductsPaginated(params = {}) {
  const query = buildQuery(params);
  return apiRequest(`/catalog/products/${query ? `?${query}` : ""}`);
}

export const fetchProduct = (id) => apiRequest(`/catalog/products/${id}/`);

export function getActivityVisitorId() {
  if (typeof window === "undefined" || !globalThis.crypto?.randomUUID) return null;
  try {
    let visitorId = window.sessionStorage.getItem("mall_activity_visitor");
    if (!visitorId) {
      visitorId = globalThis.crypto.randomUUID();
      window.sessionStorage.setItem("mall_activity_visitor", visitorId);
    }
    return visitorId;
  } catch {
    return null;
  }
}

export function trackProductActivity(productId, activityType, visitorId) {
  if (!visitorId || !globalThis.crypto?.randomUUID) return Promise.resolve(null);
  return apiRequest(`/catalog/products/${productId}/track_activity/`, {
    method: "POST",
    body: {
      activity_type: activityType,
      visitor_id: visitorId,
      event_id: globalThis.crypto.randomUUID(),
    },
  });
}

export const fetchComparisons = (id, params = {}) => {
  const query = buildQuery(params);
  return apiRequest(`/catalog/products/${id}/comparisons/${query ? `?${query}` : ""}`);
};

export const toggleFavorite = (id) => apiRequest(`/catalog/products/${id}/toggle_favorite/`, { method: "POST" });

export const fetchFavorites = () => apiRequest("/catalog/favorites/").then(unwrap);

export const removeFavorite = (favoriteId) => apiRequest(`/catalog/favorites/${favoriteId}/`, { method: "DELETE" });

export const fetchSellerFavorites = () => apiRequest("/catalog/seller-favorites/").then(unwrap);

export const addSellerFavorite = (sellerId) => apiRequest("/catalog/seller-favorites/", {
  method: "POST",
  body: { seller: sellerId },
});

export const removeSellerFavorite = (favoriteId) =>
  apiRequest(`/catalog/seller-favorites/${favoriteId}/`, { method: "DELETE" });

export const saveSearch = (name, queryParams) =>
  apiRequest("/catalog/saved-searches/", { method: "POST", body: { name, query_params: queryParams } });
