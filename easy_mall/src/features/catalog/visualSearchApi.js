import { apiRequest } from "../../lib/apiClient";

export const fetchVisualSearchConfig = () => apiRequest("/visual-search/config/");

export const searchProductsByImage = (image) => {
  const body = new FormData();
  body.append("image", image);
  return apiRequest("/visual-search/search/", { method: "POST", body });
};