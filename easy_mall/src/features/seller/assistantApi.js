import { apiRequest } from "../../lib/apiClient";

export const fetchSellerAssistantConfig = () => apiRequest("/seller-assistant/config/");

export const requestListingSuggestions = (payload) =>
  apiRequest("/seller-assistant/suggestions/", { method: "POST", body: payload });