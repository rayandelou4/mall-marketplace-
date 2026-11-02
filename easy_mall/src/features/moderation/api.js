import { apiRequest, unwrap } from "../../lib/apiClient";

export const fetchReports = () => apiRequest("/moderation/reports/").then(unwrap);
export const fetchDisputes = () => apiRequest("/moderation/disputes/").then(unwrap);

export function createReport(payload) {
  return apiRequest("/moderation/reports/", { method: "POST", body: payload });
}

export function decideReport(reportId, payload) {
  return apiRequest(`/moderation/reports/${reportId}/decide/`, { method: "POST", body: payload });
}

export function createDispute(payload) {
  return apiRequest("/moderation/disputes/", { method: "POST", body: payload });
}
