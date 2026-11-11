import { apiRequest, unwrap } from "../../lib/apiClient";

const ROOT = "/promotions";

export const fetchMyPromotions = () => apiRequest(`${ROOT}/mine/`).then(unwrap);

export const createPromotion = (payload) =>
  apiRequest(`${ROOT}/mine/`, { method: "POST", body: payload });

export const updatePromotion = (id, payload) =>
  apiRequest(`${ROOT}/mine/${id}/`, { method: "PATCH", body: payload });

export const deletePromotion = (id) =>
  apiRequest(`${ROOT}/mine/${id}/`, { method: "DELETE" });

export const fetchCheckoutQuote = (payload) =>
  apiRequest(`${ROOT}/checkout-quote/`, { method: "POST", body: payload });

export const fetchLoyaltyStatus = () => apiRequest(`${ROOT}/loyalty/me/`);