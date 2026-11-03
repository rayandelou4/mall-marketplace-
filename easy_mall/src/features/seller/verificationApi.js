import { apiRequest } from "../../lib/apiClient";

const ROOT = "/seller-verification";

export const fetchVerificationStatus = () => apiRequest(`${ROOT}/status/`);
export const fetchVerificationLevels = () => apiRequest(`${ROOT}/levels/`);

export const createVerificationRequest = (payload) =>
  apiRequest(`${ROOT}/requests/`, { method: "POST", body: payload });

export const uploadVerificationDocument = (requestId, payload) =>
  apiRequest(`${ROOT}/requests/${requestId}/documents/`, { method: "POST", body: payload });

export const submitVerificationRequest = (requestId) =>
  apiRequest(`${ROOT}/requests/${requestId}/submit/`, { method: "POST", body: {} });