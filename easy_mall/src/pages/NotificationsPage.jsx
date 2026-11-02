import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Trash2 } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading, LoadingBlock, ErrorBlock } from "../components/ui/StatusBlocks";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { deleteNotification, fetchNotifications, markAllRead, markRead } from "../features/notifications/api";
import { cx } from "../styles/theme";

const TYPE_LABELS = {
  new_message: "Message",
  new_sale: "Vente",
  payment_received: "Paiement",
  shipping: "Expédition",
  delivery: "Livraison",
  new_favorite: "Favori",
  promotion: "Promotion",
};

function formatDate(value) {
  return new Date(value).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function NotificationsPage() {
  const { t } = useTheme();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, error: null, items: [] });

  function load() {
    setState((s) => ({ ...s, loading: true }));
    fetchNotifications()
      .then((items) => setState({ loading: false, error: null, items }))
      .catch((err) => setState({ loading: false, error: err.message, items: [] }));
  }

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  async function handleOpen(notification) {
    if (!notification.is_read) {
      markRead(notification.id)
        .then(() => window.dispatchEvent(new Event("mall-notifications-updated")))
        .catch(() => {});
      setState((s) => ({
        ...s,
        items: s.items.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)),
      }));
    }
    if (notification.link_path) navigate(notification.link_path);
  }

  async function handleMarkAllRead() {
    try {
      await markAllRead();
      setState((s) => ({ ...s, items: s.items.map((n) => ({ ...n, is_read: true })) }));
      window.dispatchEvent(new Event("mall-notifications-updated"));
    } catch (err) {
      window.alert(err.message);
    }
  }

  async function handleDelete(notification) {
    if (!window.confirm("Supprimer définitivement cette notification ?")) return;
    try {
      await deleteNotification(notification.id);
      setState((current) => ({
        ...current,
        items: current.items.filter((item) => item.id !== notification.id),
      }));
      window.dispatchEvent(new Event("mall-notifications-updated"));
    } catch (err) {
      window.alert(err.message);
    }
  }

  const { loading, error, items } = state;
  const hasUnread = items.some((n) => !n.is_read);

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-2">
          <SectionHeading title="Notifications" t={t} />
          {hasUnread && (
            <button onClick={handleMarkAllRead} className="text-sm font-semibold text-indigo-600 hover:underline">
              Tout marquer comme lu
            </button>
          )}
        </div>

        {loading ? (
          <LoadingBlock t={t} />
        ) : error ? (
          <ErrorBlock message={error} t={t} />
        ) : items.length === 0 ? (
          <div className={cx("flex flex-col items-center gap-2 rounded-2xl border p-10 text-center", t.cardBorder, t.textMuted)}>
            <Bell className="h-8 w-8" />
            <p className="text-sm">Aucune notification pour l'instant.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {items.map((n) => (
              <div
                key={n.id}
                className={cx(
                  "flex items-center gap-2 rounded-2xl border p-3",
                  n.is_read ? t.cardBorder : "border-indigo-400",
                  t.cardBg
                )}
              >
                <button onClick={() => handleOpen(n)} className="flex min-w-0 flex-1 flex-col items-start gap-1 p-1 text-left">
                  <div className="flex w-full items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2">
                      {!n.is_read && <span className="h-2 w-2 shrink-0 rounded-full bg-indigo-600" />}
                      <span className={cx("truncate text-sm font-semibold", t.textPrimary)}>{n.title}</span>
                    </span>
                    <span className="shrink-0 rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-indigo-600">
                      {TYPE_LABELS[n.notification_type] || n.notification_type}
                    </span>
                  </div>
                  {n.body && <p className={cx("text-left text-sm", t.textMuted)}>{n.body}</p>}
                  <span className={cx("text-xs", t.textMuted)}>{formatDate(n.created_at)}</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(n)}
                  aria-label={`Supprimer la notification ${n.title}`}
                  className={cx("shrink-0 rounded-full border p-2", t.border, t.textMuted, "hover:border-rose-300 hover:text-rose-600")}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
