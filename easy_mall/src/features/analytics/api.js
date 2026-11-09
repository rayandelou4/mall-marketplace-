import { apiRequest } from "../../lib/apiClient";

export const fetchGlobalStats = () => apiRequest("/analytics/stats/");

export const fetchSellerStats = (period = "weekly") =>
	apiRequest(`/analytics/seller/?period=${encodeURIComponent(period)}`);
