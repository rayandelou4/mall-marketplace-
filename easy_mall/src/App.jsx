import React, { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider, useAuth } from "./features/auth/AuthContext";
import { ThemeProvider } from "./features/theme/ThemeContext";
import { CartProvider } from "./features/cart/CartContext";

const HomePage = lazy(() => import("./pages/HomePage"));
const AuthPage = lazy(() => import("./pages/AuthPage"));
const CatalogPage = lazy(() => import("./pages/CatalogPage"));
const ProductPage = lazy(() => import("./pages/ProductPage"));
const CartPage = lazy(() => import("./pages/CartPage"));
const CheckoutPage = lazy(() => import("./pages/CheckoutPage"));
const SellerDashboardPage = lazy(() => import("./pages/SellerDashboardPage"));
const ListingFormPage = lazy(() => import("./pages/ListingFormPage"));
const OrdersPage = lazy(() => import("./pages/OrdersPage"));
const MessagesPage = lazy(() => import("./pages/MessagesPage"));
const AdminStatsPage = lazy(() => import("./pages/AdminStatsPage"));
const AdminModerationPage = lazy(() => import("./pages/AdminModerationPage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const FavoritesPage = lazy(() => import("./pages/FavoritesPage"));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage"));
const SignupAddressPage = lazy(() => import("./pages/SignupAddressPage"));
const HelpPage = lazy(() => import("./pages/HelpPage"));
const TermsPage = lazy(() => import("./pages/TermsPage"));

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
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-sm text-zinc-500">Chargement…</div>}>
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/inscription/adresse" element={<SignupAddressPage />} />
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
      <Route path="/aide" element={<HelpPage />} />
      <Route path="/conditions" element={<TermsPage />} />
    </Routes>
    </Suspense>
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
