import { apiRequest } from "../../lib/apiClient";

export const fetchNegotiations = () => apiRequest("/negotiations/");

export const createNegotiation = ({ productId, variantId, amount }) =>
  apiRequest("/negotiations/", {
    method: "POST",
    body: {
      product_id: productId,
      ...(variantId ? { variant_id: variantId } : {}),
      amount,
    },
  });

export const acceptNegotiation = (id) =>
  apiRequest(`/negotiations/${id}/accept/`, { method: "POST" });

export const rejectNegotiation = (id) =>
  apiRequest(`/negotiations/${id}/reject/`, { method: "POST" });

export const counterNegotiation = (id, amount) =>
  apiRequest(`/negotiations/${id}/counter/`, { method: "POST", body: { amount } });