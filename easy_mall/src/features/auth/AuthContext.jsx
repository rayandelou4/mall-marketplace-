import React, { createContext, useContext, useEffect, useState } from "react";
import { apiRequest, setTokens, clearTokens, getRefreshToken } from "../../lib/apiClient";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [bootstrapping, setBootstrapping] = useState(true); // restauration de session en cours
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState(null);
  const [authNotice, setAuthNotice] = useState(null);

  // Au premier chargement : s'il reste un refresh token en stockage, on tente
  // de restaurer la session sans repasser par le formulaire de connexion.
  useEffect(() => {
    async function bootstrap() {
      if (!getRefreshToken()) {
        setBootstrapping(false);
        return;
      }
      try {
        const me = await apiRequest("/accounts/me/"); // 401 → apiClient rafraîchit tout seul
        setUser(me);
      } catch {
        clearTokens();
      } finally {
        setBootstrapping(false);
      }
    }
    bootstrap();
  }, []);

  async function run(action) {
    setAuthLoading(true);
    setAuthError(null);
    try {
      return await action();
    } catch (err) {
      setAuthError(err.message);
      throw err;
    } finally {
      setAuthLoading(false);
    }
  }

  const login = ({ email, password }) =>
    run(async () => {
      const data = await apiRequest("/accounts/login/", { method: "POST", body: { email, password } });
      if (!data.user?.is_email_verified) {
        throw new Error("Veuillez vérifier votre adresse e-mail avant de pouvoir vous connecter.");
      }
      setTokens({ access: data.access, refresh: data.refresh });
      setUser(data.user);
      return data.user;
    });

  const register = (form) =>
    run(async () => {
      const data = await apiRequest("/accounts/register/", { method: "POST", body: form });
      setTokens({ access: "", refresh: "" });
      clearTokens();
      setUser(null);
      setAuthNotice(`Compte créé. Un code de vérification à 6 chiffres a été envoyé à ${form.email}. Saisissez-le pour activer votre compte.`);
      return data.user || null;
    });

  const resendEmailVerification = (email = null) =>
    run(async () => {
      await apiRequest("/accounts/email/resend/", {
        method: "POST",
        body: email ? { email } : {},
      });
      setAuthNotice("Code de vérification renvoyé.");
    });

  const forgotPassword = (email) =>
    run(async () => {
      await apiRequest("/accounts/password/reset/request/", { method: "POST", body: { email } });
      setAuthNotice("Si cet e-mail existe, un code de réinitialisation a été envoyé.");
    });

  const verifyPasswordResetCode = ({ email, code }) =>
    run(async () => {
      await apiRequest("/accounts/password/reset/verify/", {
        method: "POST",
        body: { email, code },
      });
    });

  const resetPassword = ({ email, code, newPassword }) =>
    run(async () => {
      await apiRequest("/accounts/password/reset/confirm/", {
        method: "POST",
        body: { email, code, new_password: newPassword },
      });
      setAuthNotice("Mot de passe réinitialisé. Vous pouvez vous connecter.");
    });

  const confirmEmail = ({ email, code, password }) =>
    run(async () => {
      await apiRequest("/accounts/email/verify/", { method: "POST", body: { email, code } });
      // is_fully_verified ne dépend plus que de l'e-mail (SMS retiré du parcours).
      setUser((u) => (u ? { ...u, is_email_verified: true, is_fully_verified: true } : u));
      setAuthNotice("Votre e-mail a été vérifié avec succès. Vous êtes maintenant connecté.");

      if (email && password) {
        const data = await apiRequest("/accounts/login/", { method: "POST", body: { email, password } });
        if (!data.user?.is_email_verified) {
          throw new Error("Veuillez vérifier votre adresse e-mail avant de pouvoir vous connecter.");
        }
        setTokens({ access: data.access, refresh: data.refresh });
        setUser(data.user);
      }
    });

  const logout = () =>
    run(async () => {
      try {
        await apiRequest("/accounts/logout/", { method: "POST", body: { refresh: getRefreshToken() } });
      } finally {
        clearTokens();
        setUser(null);
      }
    });

  const value = {
    user,
    isAuthenticated: Boolean(user),
    bootstrapping,
    authLoading,
    authError,
    authNotice,
    clearAuthMessages: () => {
      setAuthError(null);
      setAuthNotice(null);
    },
    updateUser: (patch) => setUser((u) => (u ? { ...u, ...patch } : u)),
    login,
    register,
    resendEmailVerification,
    forgotPassword,
    verifyPasswordResetCode,
    resetPassword,
    confirmEmail,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth() doit être appelé à l'intérieur d'un <AuthProvider>.");
  return ctx;
}
