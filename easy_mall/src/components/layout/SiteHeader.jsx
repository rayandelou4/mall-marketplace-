import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, Menu, X, Sun, Moon, ShoppingBag, ChevronDown, UserRound, LogOut, Bell, CheckCheck } from "lucide-react";
import { useAuth } from "../../features/auth/AuthContext";
import { useTheme } from "../../features/theme/ThemeContext";
import { useCart } from "../../features/cart/CartContext";
import { cx } from "../../styles/theme";
import { ProfilePhotoViewer } from "../ui/ProfilePhotoViewer";
import { fetchNotifications, fetchUnreadCount, markAllRead, markRead } from "../../features/notifications/api";

function getNavLinks(isAuthenticated, isStaff) {
  const links = [
    { label: "Produits", to: "/catalogue?item_type=product" },
    { label: "Services", to: "/catalogue?item_type=service" },
    { label: "Vendre", to: isAuthenticated ? "/vendeur" : "/auth?mode=register" },
  ];
  if (isAuthenticated) {
    links.push(
      { label: "Mes commandes", to: "/mes-commandes" },
      { label: "Favoris", to: "/favoris" },
      { label: "Messages", to: "/messages" },
    );
  }
  if (isStaff === true) links.push({ label: "Administration", to: "/moderation" });
  links.push({ label: "Comment ça marche", to: "/#comment-ca-marche" }, { label: "Aide", to: "/aide" });
  return links;
}

function AuthArea({ t, mobile = false }) {
  const { isAuthenticated, user, logout, authLoading } = useAuth();
  const [open, setOpen] = useState(false);

  if (isAuthenticated) {
    return (
      <div className={cx("relative", mobile && "w-full")}>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-haspopup="menu"
          className={cx("flex items-center gap-2 rounded-full border px-2 py-1.5", t.border, mobile && "w-full justify-between")}
        >
          <span className="flex items-center gap-2">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="Photo de profil" className="h-7 w-7 rounded-full object-cover" />
            ) : (
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
                {user?.username?.charAt(0)?.toUpperCase() || "?"}
              </span>
            )}
            <span className={cx("text-sm font-medium", t.textPrimary)}>{user?.username}</span>
          </span>
          <ChevronDown className={cx("h-4 w-4 transition-transform", t.textMuted, open && "rotate-180")} />
        </button>

        {open && (
          <div className={cx("absolute right-0 top-full z-50 mt-2 min-w-48 rounded-xl border p-1 shadow-lg", t.cardBorder, t.cardBg, mobile && "left-0 right-auto w-full")} role="menu">
            <div className="flex items-center gap-2 px-2 py-2">
              {user?.avatar_url && (
                <ProfilePhotoViewer
                  src={user.avatar_url}
                  alt={`Photo de profil de ${user.username}`}
                  title={`Photo de ${user.username}`}
                  showTriggerOverlay
                  className="h-10 w-10 shrink-0 overflow-hidden rounded-full ring-2 ring-white shadow-sm"
                >
                  <img src={user.avatar_url} alt="" className="h-full w-full object-cover" />
                </ProfilePhotoViewer>
              )}
              <Link
                to={`/profil/${user?.username || ""}`}
                onClick={() => setOpen(false)}
                className={cx("flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-indigo-50", t.textPrimary)}
                role="menuitem"
              >
                <UserRound className="h-4 w-4" /> Mon profil
              </Link>
            </div>
            <button
              type="button"
              onClick={logout}
              disabled={authLoading}
              className={cx("flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-rose-50", t.textMuted)}
              role="menuitem"
            >
              <LogOut className="h-4 w-4" /> Se déconnecter
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={cx("flex items-center gap-2", mobile && "w-full")}>
      <Link to="/auth" className={cx("rounded-full px-4 py-2 text-sm font-medium", mobile && "flex-1 border text-center", t.textMuted, mobile && t.border)}>
        Connexion
      </Link>
      <Link to="/auth?mode=register" className={cx("rounded-full bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700", mobile && "flex-1 text-center")}>
        Inscription
      </Link>
    </div>
  );
}

export function SiteHeader({ initialSearch = "" }) {
  const { isDark, toggleTheme, t } = useTheme();
  const { isAuthenticated, user } = useAuth();
  const { totalItems } = useCart();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState(initialSearch);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const notificationsRef = useRef(null);
  const navLinks = getNavLinks(isAuthenticated, user?.is_staff === true);

  useEffect(() => {
    if (!isAuthenticated) {
      setNotifications([]);
      setUnreadCount(0);
      return undefined;
    }

    let active = true;
    function refreshNotifications() {
      Promise.all([fetchNotifications(), fetchUnreadCount()])
        .then(([items, count]) => {
          if (!active) return;
          setNotifications(items.slice(0, 6));
          setUnreadCount(count.unread_count || 0);
        })
        .catch(() => {});
    }

    refreshNotifications();
    const intervalId = window.setInterval(refreshNotifications, 30000);
    window.addEventListener("focus", refreshNotifications);
    window.addEventListener("mall-notifications-updated", refreshNotifications);
    return () => {
      active = false;
      window.clearInterval(intervalId);
      window.removeEventListener("focus", refreshNotifications);
      window.removeEventListener("mall-notifications-updated", refreshNotifications);
    };
  }, [isAuthenticated]);

  useEffect(() => {
    function closeNotifications(event) {
      if (!notificationsRef.current?.contains(event.target)) setNotificationsOpen(false);
    }
    document.addEventListener("pointerdown", closeNotifications);
    return () => document.removeEventListener("pointerdown", closeNotifications);
  }, []);

  function submitSearch(e) {
    e.preventDefault();
    navigate(search ? `/catalogue?search=${encodeURIComponent(search)}` : "/catalogue");
    setMobileOpen(false);
  }

  async function openNotification(notification) {
    setNotificationsOpen(false);
    if (!notification.is_read) {
      setNotifications((items) => items.map((item) => (
        item.id === notification.id ? { ...item, is_read: true } : item
      )));
      setUnreadCount((count) => Math.max(0, count - 1));
      markRead(notification.id).catch(() => {});
    }
    navigate(notification.link_path || "/notifications");
  }

  async function handleMarkAllNotificationsRead() {
    try {
      await markAllRead();
      setNotifications((items) => items.map((item) => ({ ...item, is_read: true })));
      setUnreadCount(0);
    } catch {
      /* La liste reste ouverte pour permettre une nouvelle tentative. */
    }
  }

  return (
    <header className={cx("sticky top-0 z-40 border-b backdrop-blur shadow-[0_6px_24px_rgba(24,24,27,0.04)]", t.headerBg, t.border)}>
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
        <Link to="/" className="text-2xl font-semibold text-indigo-600">Mall</Link>

        <nav className="ml-4 hidden items-center gap-4 xl:flex">
          {navLinks.map((link) => (
            <Link key={link.label} to={link.to} className={cx("text-sm font-medium hover:text-indigo-600", t.textMuted)}>
              {link.label}
            </Link>
          ))}
        </nav>

        <form onSubmit={submitSearch} className="ml-auto hidden flex-1 max-w-md items-center gap-2 rounded-full border px-4 py-2 md:flex">
          <Search className={cx("h-4 w-4 shrink-0", t.textMuted)} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher une robe, un téléphone, un canapé…"
            className={cx("w-full bg-transparent text-sm outline-none placeholder:text-zinc-400", t.textPrimary)}
          />
        </form>

        <Link to="/panier" aria-label="Panier" className={cx("relative rounded-full border p-2 hover:border-indigo-400", t.border)}>
          <ShoppingBag className="h-4 w-4" />
          {totalItems > 0 && (
            <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-indigo-600 px-1 text-[10px] font-semibold text-white">
              {totalItems}
            </span>
          )}
        </Link>

        {isAuthenticated && (
          <div ref={notificationsRef} className="relative">
            <button
              type="button"
              aria-label={`Notifications${unreadCount ? `, ${unreadCount} non lues` : ""}`}
              aria-expanded={notificationsOpen}
              onClick={() => setNotificationsOpen((open) => !open)}
              className={cx("relative rounded-full border p-2 hover:border-indigo-400", t.border, t.textPrimary)}
            >
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold text-white">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>

            {notificationsOpen && (
              <div className={cx("absolute right-0 top-full z-50 mt-3 w-[min(90vw,22rem)] overflow-hidden rounded-2xl border shadow-xl", t.cardBorder, t.cardBg)}>
                <div className={cx("flex items-center justify-between border-b px-4 py-3", t.border)}>
                  <span className={cx("text-sm font-semibold", t.textPrimary)}>Notifications</span>
                  {unreadCount > 0 && (
                    <button type="button" onClick={handleMarkAllNotificationsRead} className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:underline">
                      <CheckCheck className="h-3.5 w-3.5" /> Tout lire
                    </button>
                  )}
                </div>
                {notifications.length === 0 ? (
                  <p className={cx("px-4 py-8 text-center text-sm", t.textMuted)}>Aucune notification pour l’instant.</p>
                ) : (
                  <div className="max-h-96 overflow-y-auto">
                    {notifications.map((notification) => (
                      <button
                        key={notification.id}
                        type="button"
                        onClick={() => openNotification(notification)}
                        className={cx("flex w-full items-start gap-3 border-b px-4 py-3 text-left last:border-0 hover:bg-indigo-50/70", t.border, !notification.is_read && "bg-indigo-50/40")}
                      >
                        <span className={cx("mt-1.5 h-2 w-2 shrink-0 rounded-full", notification.is_read ? "bg-transparent" : "bg-indigo-600")} />
                        <span className="min-w-0 flex-1">
                          <span className={cx("block text-sm font-semibold", t.textPrimary)}>{notification.title}</span>
                          {notification.body && <span className={cx("mt-0.5 line-clamp-2 block text-xs", t.textMuted)}>{notification.body}</span>}
                          <span className={cx("mt-1 block text-[10px]", t.textMuted)}>{new Date(notification.created_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                <Link
                  to="/notifications"
                  onClick={() => setNotificationsOpen(false)}
                  className={cx("block border-t px-4 py-3 text-center text-xs font-semibold text-indigo-600 hover:bg-indigo-50", t.border)}
                >
                  Voir toutes les notifications
                </Link>
              </div>
            )}
          </div>
        )}

        <button aria-label="Changer de thème" onClick={toggleTheme} className={cx("rounded-full border p-2 hover:border-indigo-400", t.border)}>
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        <div className="hidden sm:block"><AuthArea t={t} /></div>

        <button className="ml-1 xl:hidden" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Menu">
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {mobileOpen && (
        <div className={cx("border-t px-4 py-4 xl:hidden", t.border)}>
          <form onSubmit={submitSearch} className={cx("mb-4 flex items-center gap-2 rounded-full border px-4 py-2", t.border)}>
            <Search className={cx("h-4 w-4", t.textMuted)} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher…"
              className={cx("w-full bg-transparent text-sm outline-none", t.textPrimary)}
            />
          </form>
          <div className="flex flex-col gap-3">
            {navLinks.map((link) => (
              <Link key={link.label} to={link.to} className={cx("text-sm font-medium", t.textMuted)} onClick={() => setMobileOpen(false)}>
                {link.label}
              </Link>
            ))}
            <div className="mt-2"><AuthArea t={t} mobile /></div>
          </div>
        </div>
      )}
    </header>
  );
}
