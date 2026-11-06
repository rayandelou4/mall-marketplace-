import { apiDownload, apiRequest, unwrap } from "../../lib/apiClient";

const ROOT = "/seller-verification";

export const fetchVerificationStatus = () => apiRequest(`${ROOT}/status/`);
export const fetchVerificationLevels = () => apiRequest(`${ROOT}/levels/`);

export const createVerificationRequest = (payload) =>
  apiRequest(`${ROOT}/requests/`, { method: "POST", body: payload });

export const uploadVerificationDocument = (requestId, payload) =>
  apiRequest(`${ROOT}/requests/${requestId}/documents/`, { method: "POST", body: payload });

export const submitVerificationRequest = (requestId) =>
  apiRequest(`${ROOT}/requests/${requestId}/submit/`, { method: "POST", body: {} });

export const fetchAdminVerificationRequests = () =>
  apiRequest(`${ROOT}/admin/verification-requests/`).then(unwrap);

export const reviewAdminVerificationRequest = (requestId, payload) =>
  apiRequest(`${ROOT}/admin/verification-requests/${requestId}/review/`, { method: "POST", body: payload });

export const downloadVerificationDocument = (documentId) =>
  apiDownload(`${ROOT}/documents/${documentId}/download/`);