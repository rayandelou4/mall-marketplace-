import { apiRequest, unwrap } from "../../lib/apiClient";

const ROOT = "/localization";

export const fetchCountries = () =>
  apiRequest(`${ROOT}/countries/`).then(unwrap);

export const fetchAreas = (params = {}) => {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value != null && value !== "")
  );
  const suffix = query.size ? `?${query}` : "";
  return apiRequest(`${ROOT}/areas/${suffix}`).then(unwrap);
};

export const fetchSellerLocation = () => apiRequest(`${ROOT}/seller-location/me/`);

export const saveSellerLocation = (payload) =>
  apiRequest(`${ROOT}/seller-location/me/`, { method: "PUT", body: payload });

export const fetchLocationPreferences = () =>
  apiRequest(`${ROOT}/seller-location/preferences/`);

export const saveLocationPreferences = (payload) =>
  apiRequest(`${ROOT}/seller-location/preferences/`, { method: "PATCH", body: payload });

export const fetchDeliveryOptions = () =>
  apiRequest(`${ROOT}/delivery-options/`).then(unwrap);

export const createDeliveryOption = (payload) =>
  apiRequest(`${ROOT}/delivery-options/`, { method: "POST", body: payload });

export const updateDeliveryOption = (id, payload) =>
  apiRequest(`${ROOT}/delivery-options/${id}/`, { method: "PATCH", body: payload });

export const deleteDeliveryOption = (id) =>
  apiRequest(`${ROOT}/delivery-options/${id}/`, { method: "DELETE" });

export const fetchPickupLocations = () =>
  apiRequest(`${ROOT}/pickup-locations/`).then(unwrap);

export const fetchPrivateAddresses = () =>
  apiRequest(`${ROOT}/addresses/`).then(unwrap);

export const createPrivateAddress = (payload) =>
  apiRequest(`${ROOT}/addresses/`, { method: "POST", body: payload });

export const updatePrivateAddress = (id, payload) =>
  apiRequest(`${ROOT}/addresses/${id}/`, { method: "PATCH", body: payload });

export const deletePrivateAddress = (id) =>
  apiRequest(`${ROOT}/addresses/${id}/`, { method: "DELETE" });

export const createPickupLocation = (payload) =>
  apiRequest(`${ROOT}/pickup-locations/`, { method: "POST", body: payload });

export const updatePickupLocation = (id, payload) =>
  apiRequest(`${ROOT}/pickup-locations/${id}/`, { method: "PATCH", body: payload });

export const deletePickupLocation = (id) =>
  apiRequest(`${ROOT}/pickup-locations/${id}/`, { method: "DELETE" });