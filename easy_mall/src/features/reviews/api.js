import { apiRequest, unwrap } from "../../lib/apiClient";

export function fetchReviews(params = {}) {
  const query = new URLSearchParams(params).toString();
  return apiRequest(`/reviews/reviews/${query ? `?${query}` : ""}`).then(unwrap);
}

export function createReview(payload) {
  return apiRequest("/reviews/reviews/", { method: "POST", body: payload });
}
