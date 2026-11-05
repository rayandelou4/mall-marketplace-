import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider, useAuth } from "./features/auth/AuthContext";
import { ThemeProvider } from "./features/theme/ThemeContext";
import { CartProvider } from "./features/cart/CartContext";
import HomePage from "./pages/HomePage";
import AuthPage from "./pages/AuthPage";
import CatalogPage from "./pages/CatalogPage";
import ProductPage from "./pages/ProductPage";
import CartPage from "./pages/CartPage";
import CheckoutPage from "./pages/CheckoutPage";
import SellerDashboardPage from "./pages/SellerDashboardPage";
import ListingFormPage from "./pages/ListingFormPage";
import OrdersPage from "./pages/OrdersPage";
import MessagesPage from "./pages/MessagesPage";
import AdminStatsPage from "./pages/AdminStatsPage";
import AdminModerationPage from "./pages/AdminModerationPage";
import ProfilePage from "./pages/ProfilePage";
import SettingsPage from "./pages/SettingsPage";
import FavoritesPage from "./pages/FavoritesPage";
import NotificationsPage from "./pages/NotificationsPage";

function AppRoutes() {
  const { bootstrapping } = useAuth();

  // Évite un flash "déconnecté" pendant la tentative de restauration de
  // session (lecture du refresh token + appel /accounts/me/).
  if (bootstrapping) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-zinc-500">
        Chargement…
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/catalogue" element={<CatalogPage />} />
      <Route path="/produit/:id" element={<ProductPage />} />
      <Route path="/panier" element={<CartPage />} />
      <Route path="/commande" element={<CheckoutPage />} />
      <Route path="/vendeur" element={<SellerDashboardPage />} />
      <Route path="/vendeur/annonces/nouvelle" element={<ListingFormPage />} />
      <Route path="/vendeur/annonces/:id/modifier" element={<ListingFormPage />} />
      <Route path="/mes-commandes" element={<OrdersPage />} />
      <Route path="/favoris" element={<FavoritesPage />} />
      <Route path="/notifications" element={<NotificationsPage />} />
      <Route path="/messages" element={<MessagesPage />} />
      <Route path="/messages/:id" element={<MessagesPage />} />
      <Route path="/statistiques" element={<AdminStatsPage />} />
      <Route path="/moderation" element={<AdminModerationPage />} />
      <Route path="/vendeurs/:username" element={<ProfilePage />} />
      <Route path="/profil/:username" element={<ProfilePage />} />
      <Route path="/parametres" element={<SettingsPage />} />
    </Routes>
  );
}

function AppContent() {
  const { user } = useAuth();

  return (
    <CartProvider key={user?.id || "guest"}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </CartProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}
