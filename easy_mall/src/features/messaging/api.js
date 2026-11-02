import { apiRequest, unwrap } from "../../lib/apiClient";

export const fetchConversations = () => apiRequest("/messaging/conversations/").then(unwrap);

export const hideConversation = (conversationId) =>
  apiRequest(`/messaging/conversations/${conversationId}/hide/`, { method: "DELETE" });

export const fetchMessages = (conversationId, page = 1) =>
  apiRequest(`/messaging/conversations/${conversationId}/messages/?page=${page}`);

export function sendMessage(conversationId, payload) {
  return apiRequest(`/messaging/conversations/${conversationId}/messages/`, {
    method: "POST",
    body: payload,
  });
}

export function updateMessage(conversationId, messageId, content) {
  return apiRequest(`/messaging/conversations/${conversationId}/messages/${messageId}/`, {
    method: "PATCH",
    body: { content },
  });
}

export function deleteMessage(conversationId, messageId, scope = "me") {
  return apiRequest(`/messaging/conversations/${conversationId}/messages/?message_id=${encodeURIComponent(messageId)}&scope=${scope}`, {
    method: "DELETE",
  });
}

export function clearMessages(conversationId) {
  return apiRequest(`/messaging/conversations/${conversationId}/messages/clear/`, { method: "POST" });
}

export function startConversation({ recipientUsername, productId, content }) {
  return apiRequest("/messaging/conversations/start/", {
    method: "POST",
    body: { recipient_username: recipientUsername, product_id: productId || null, content },
  });
}
