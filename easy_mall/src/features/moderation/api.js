import { apiRequest, unwrap } from "../../lib/apiClient";

export const fetchReports = () => apiRequest("/moderation/reports/").then(unwrap);
export const fetchDisputes = () => apiRequest("/moderation/disputes/").then(unwrap);
export const fetchMessageReports = () => apiRequest("/moderation/message-reports/").then(unwrap);

export function createReport(payload) {
  return apiRequest("/moderation/reports/", { method: "POST", body: payload });
}

export function decideReport(reportId, payload) {
  return apiRequest(`/moderation/reports/${reportId}/decide/`, { method: "POST", body: payload });
}

export function createDispute(payload) {
  return apiRequest("/moderation/disputes/", { method: "POST", body: payload });
}

export function reviewDispute(disputeId, payload) {
  return apiRequest(`/moderation/disputes/${disputeId}/review/`, { method: "POST", body: payload });
}

export function replyToDispute(disputeId, payload) {
  return apiRequest(`/moderation/disputes/${disputeId}/reply/`, { method: "POST", body: payload });
}

export function appealDispute(disputeId, payload) {
  return apiRequest(`/moderation/disputes/${disputeId}/appeal/`, { method: "POST", body: payload });
}

export function createMessageReport(payload) {
  return apiRequest("/moderation/message-reports/", { method: "POST", body: payload });
}

export function reviewMessageReport(reportId, payload) {
  return apiRequest(`/moderation/message-reports/${reportId}/review/`, { method: "POST", body: payload });
}

export function moderateAccount(accountId, payload) {
  return apiRequest(`/moderation/accounts/${accountId}/suspension/`, { method: "POST", body: payload });
}
