import { apiRequest } from "../../lib/apiClient";

export const fetchBuyerAssistantConfig = () => apiRequest("/buyer-assistant/config/");

export const askBuyerAssistant = (message) =>
  apiRequest("/buyer-assistant/search/", { method: "POST", body: { message } });