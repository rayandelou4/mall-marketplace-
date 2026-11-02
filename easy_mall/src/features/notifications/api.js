import { apiRequest, unwrap } from "../../lib/apiClient";

const NOTIFICATIONS_PATH = "/notifications/notifications/";

export const fetchNotifications = () => apiRequest(NOTIFICATIONS_PATH).then(unwrap);

export const fetchUnreadCount = () => apiRequest(`${NOTIFICATIONS_PATH}unread_count/`);

export const markRead = (notificationId) =>
  apiRequest(`${NOTIFICATIONS_PATH}${notificationId}/mark_read/`, { method: "POST" });

export const markAllRead = () =>
  apiRequest(`${NOTIFICATIONS_PATH}mark_all_read/`, { method: "POST" });

export const deleteNotification = (notificationId) =>
  apiRequest(`${NOTIFICATIONS_PATH}${notificationId}/`, { method: "DELETE" });