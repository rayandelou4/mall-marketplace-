import { apiRequest } from "../../lib/apiClient";

export const fetchPublicProfile = (username) => apiRequest(`/accounts/users/${username}/`);

export const updateProfile = (payload) => apiRequest("/accounts/me/", { method: "PATCH", body: payload });

export const changePassword = (payload) =>
  apiRequest("/accounts/password/change/", { method: "POST", body: payload });
