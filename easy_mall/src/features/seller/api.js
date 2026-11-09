import { apiRequest, unwrap } from "../../lib/apiClient";

export const fetchMyProducts = () => apiRequest("/catalog/products/mine/").then(unwrap);

export const fetchProductForEdit = (id) => apiRequest(`/catalog/products/${id}/`);

export const createProduct = (payload) => apiRequest("/catalog/products/", { method: "POST", body: payload });

export const updateProduct = (id, payload) => apiRequest(`/catalog/products/${id}/`, { method: "PATCH", body: payload });

export const deleteProduct = (id) => apiRequest(`/catalog/products/${id}/`, { method: "DELETE" });

export const fetchMySales = () => apiRequest("/orders/my-sales/").then(unwrap);

export const deleteSale = (itemId) => apiRequest(`/orders/my-sales/${itemId}/`, { method: "DELETE" });

export const fetchConfirmedSalesCount = () => apiRequest("/orders/my-sales/confirmed-count/");

export const fetchStockHistory = (productId) =>
	apiRequest(`/catalog/products/${productId}/stock_history/`).then(unwrap);

export const markSaleShipped = (itemId) => apiRequest(`/orders/my-sales/${itemId}/mark_shipped/`, { method: "POST" });

export const fetchWallet = () => apiRequest("/payments/wallet/");

export const fetchPaymentConfig = () => apiRequest("/payments/config/");
