import { apiRequest } from "../../lib/apiClient";

export const fetchGlobalStats = () => apiRequest("/analytics/stats/");
