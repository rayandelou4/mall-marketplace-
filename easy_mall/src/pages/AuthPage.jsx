import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Sun, Moon, Loader2 } from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { useTheme } from "../features/theme/ThemeContext";
import { API_BASE_URL } from "../lib/apiClient";
import { uploadToCloudinary } from "../lib/cloudinary";
import { TextField, PasswordField, Button, Alert } from "../components/ui/FormControls";
import { cx } from "../styles/theme";
import { ProfilePhotoViewer } from "../components/ui/ProfilePhotoViewer";

function GoogleButton({ t }) {
  return (
    <div>
      <button
        type="button"
        disabled
        className={cx(
          "flex w-full cursor-not-allowed items-center justify-center rounded-full border px-5 py-2.5 text-sm font-medium opacity-50",
          t.border,
          t.textMuted
        )}
      >
        Continuer avec Google
      </button>
      <p className={cx("mt-1 text-center text-[11px]", t.textMuted)}>Bientôt disponible</p>
    </div>
  );
}

/* -------------------------------- Forms ---------------------------------- */

function LoginForm({ t, loading, onSubmit, onForgot, onSwitch }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit({ email, password }); }} className="flex flex-col gap-4">
      <TextField label="E-mail" type="email" value={email} onChange={setEmail} placeholder="vous@exemple.com" required t={t} />
      <PasswordField label="Mot de passe" value={password} onChange={setPassword} autoComplete="current-password" t={t} />
      <button type="button" onClick={onForgot} className="self-end text-xs font-medium text-indigo-600 hover:underline">
        Mot de passe oublié ?
      </button>
      <Button type="submit" loading={loading}>Se connecter</Button>
      <GoogleButton t={t} />
      <p className={cx("text-center text-sm", t.textMuted)}>
        Pas encore de compte ?{" "}
        <button type="button" onClick={onSwitch} className="font-semibold text-indigo-600 hover:underline">Inscrivez-vous</button>
      </p>
    </form>
  );
}

function RegisterForm({ t, loading, onSubmit, onSwitch }) {
  const [form, setForm] = useState({
    username: "",
    email: "",
    phone_number: "",
    first_name: "",
    last_name: "",
    avatar_url: "",
    seller_type: "individual",
    shop_name: "",
    shop_description: "",
    shop_logo_url: "",
    shop_cover_url: "",
    password: "",
    password_confirm: "",
  });
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [localError, setLocalError] = useState(null);
  const update = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  async function handleAvatarChange(file) {
    if (!file) return;
    setUploadingAvatar(true);
    setLocalError(null);
    try {
      update("avatar_url")(await uploadToCloudinary(file));
    } catch (error) {
      setLocalError(error.message || "Le téléchargement de la photo a échoué.");
    } finally {
      setUploadingAvatar(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (form.password !== form.password_confirm) {
      setLocalError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setLocalError(null);
    onSubmit(form);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col items-center">
        <label className="group relative cursor-pointer" aria-label="Choisir une photo de profil">
          {form.avatar_url ? (
            <img src={form.avatar_url} alt="Aperçu de la photo de profil" className="h-24 w-24 rounded-full object-cover ring-4 ring-indigo-100" />
          ) : (
            <span className="flex h-24 w-24 items-center justify-center rounded-full border-2 border-dashed border-indigo-300 bg-indigo-50 text-center text-xs font-semibold text-indigo-600 transition group-hover:border-indigo-500">
              Ajouter une photo
            </span>
          )}
          <input
            type="file"
            accept="image/*"
            onChange={(event) => handleAvatarChange(event.target.files?.[0])}
            className="sr-only"
          />
        </label>
        <span className={cx("mt-2 text-xs", t.textMuted)}>
          {uploadingAvatar ? "Téléchargement…" : "Photo de profil (optionnelle)"}
        </span>
        {form.avatar_url && (
          <ProfilePhotoViewer
            src={form.avatar_url}
            alt="Photo de profil choisie pour le compte"
            title="Votre photo de profil"
            className="mt-2 rounded-full border border-indigo-200 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 shadow-sm transition hover:border-indigo-400 hover:bg-indigo-50"
          >
            Voir la photo en grand
          </ProfilePhotoViewer>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <TextField label="Prénom" value={form.first_name} onChange={update("first_name")} required t={t} />
        <TextField label="Nom" value={form.last_name} onChange={update("last_name")} required t={t} />
      </div>
      <div className={cx("grid grid-cols-2 gap-3 rounded-xl border p-2", t.border)}>
        {[
          ["individual", "Particulier"],
          ["professional", "Commerçant"],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => update("seller_type")(value)}
            className={cx(
              "rounded-lg px-3 py-2 text-sm font-semibold transition",
              form.seller_type === value ? "bg-indigo-600 text-white" : t.textMuted
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <TextField label="Nom d'utilisateur" value={form.username} onChange={update("username")} hint="Lettres, chiffres et tirets uniquement." required t={t} />
      <TextField label="E-mail" type="email" value={form.email} onChange={update("email")} required t={t} />
      <TextField label="Téléphone" type="tel" value={form.phone_number} onChange={update("phone_number")} placeholder="+243 8xx xxx xxx" required t={t} />
      {form.seller_type === "professional" && (
        <>
          <TextField label="Nom de la boutique" value={form.shop_name} onChange={update("shop_name")} t={t} />
          <label className="block">
            <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Description de la boutique</span>
            <textarea value={form.shop_description} onChange={(e) => update("shop_description")(e.target.value)} rows={3} className={cx("w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:border-indigo-500", t.inputBg, t.border, t.textPrimary)} />
          </label>
        </>
      )}
      <PasswordField label="Mot de passe" value={form.password} onChange={update("password")} autoComplete="new-password" t={t} />
      <PasswordField label="Confirmer le mot de passe" value={form.password_confirm} onChange={update("password_confirm")} autoComplete="new-password" t={t} />
      {localError && <Alert type="error">{localError}</Alert>}
      <Button type="submit" loading={loading || uploadingAvatar} disabled={uploadingAvatar}>Créer mon compte</Button>
      <GoogleButton t={t} />
      <p className={cx("text-center text-sm", t.textMuted)}>
        Déjà un compte ?{" "}
        <button type="button" onClick={onSwitch} className="font-semibold text-indigo-600 hover:underline">Connectez-vous</button>
      </p>
    </form>
  );
}

function ForgotPasswordForm({ t, loading, onSubmit, onSwitch, onHaveToken }) {
  const [email, setEmail] = useState("");
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(email); }} className="flex flex-col gap-4">
      <p className={cx("text-sm", t.textMuted)}>Entrez votre e-mail : si un compte existe, vous recevrez un code de vérification à 6 chiffres.</p>
      <TextField label="E-mail" type="email" value={email} onChange={setEmail} required t={t} />
      <Button type="submit" loading={loading}>Envoyer le code</Button>
      <div className="flex flex-col items-center gap-1 text-xs font-medium">
        <button type="button" onClick={onHaveToken} className="text-indigo-600 hover:underline">J'ai déjà reçu un code</button>
        <button type="button" onClick={onSwitch} className={cx("hover:underline", t.textMuted)}>Retour à la connexion</button>
      </div>
    </form>
  );
}

function PasswordResetCodeForm({ t, loading, onSubmit, onSwitch, initialEmail = "" }) {
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState("");

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit({ email, code }); }} className="flex flex-col gap-4">
      <p className={cx("text-sm", t.textMuted)}>Saisissez le code reçu par e-mail pour continuer.</p>
      <TextField label="E-mail" type="email" value={email} onChange={setEmail} required t={t} />
      <TextField
        label="Code de vérification"
        value={code}
        onChange={(value) => setCode(value.replace(/\D/g, "").slice(0, 6))}
        placeholder="123456"
        maxLength={6}
        inputMode="numeric"
        required
        t={t}
      />
      <Button type="submit" loading={loading}>Vérifier le code</Button>
      <button type="button" onClick={onSwitch} className="text-center text-xs font-medium text-indigo-600 hover:underline">
        Retour à la connexion
      </button>
    </form>
  );
}

function ResetPasswordForm({ t, loading, onSubmit, onSwitch, initialEmail = "", initialCode = "" }) {
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState(initialCode);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [localError, setLocalError] = useState(null);

  function handleSubmit(e) {
    e.preventDefault();
    if (password !== confirm) {
      setLocalError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setLocalError(null);
    onSubmit({ email, code, newPassword: password });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <TextField label="E-mail" type="email" value={email} onChange={setEmail} required t={t} />
      <TextField
        label="Code de vérification"
        value={code}
        onChange={(value) => setCode(value.replace(/\D/g, "").slice(0, 6))}
        maxLength={6}
        inputMode="numeric"
        required
        t={t}
      />
      <PasswordField label="Nouveau mot de passe" value={password} onChange={setPassword} autoComplete="new-password" t={t} />
      <PasswordField label="Confirmer le mot de passe" value={confirm} onChange={setConfirm} autoComplete="new-password" t={t} />
      {localError && <Alert type="error">{localError}</Alert>}
      <Button type="submit" loading={loading}>Changer le mot de passe</Button>
      <button type="button" onClick={onSwitch} className="text-center text-xs font-medium text-indigo-600 hover:underline">
        Retour à la connexion
      </button>
    </form>
  );
}

function VerifyEmailForm({ t, loading, onSubmit, initialEmail = "", initialPassword = "", onResend, resendCooldown = 30, expirySeconds = 600 }) {
  const [code, setCode] = useState("");
  const [resendCountdown, setResendCountdown] = useState(resendCooldown);
  const [expiryCountdown, setExpiryCountdown] = useState(expirySeconds);

  useEffect(() => {
    if (resendCountdown <= 0) return;
    const timer = window.setTimeout(() => setResendCountdown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendCountdown]);

  useEffect(() => {
    if (expiryCountdown <= 0) return;
    const timer = window.setTimeout(() => setExpiryCountdown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [expiryCountdown]);

  const expiryText = `${String(Math.floor(expiryCountdown / 60)).padStart(2, "0")}:${String(expiryCountdown % 60).padStart(2, "0")}`;

  function handleResendClick() {
    if (!onResend || resendCountdown > 0 || loading) return;
    onResend();
    setResendCountdown(resendCooldown);
  }

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit({ email: initialEmail, code, password: initialPassword });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-center text-xs font-medium text-amber-700">
        Code expire dans {expiryText}
      </div>

      <p className={cx("text-sm", t.textMuted)}>Entrez le code à 6 chiffres reçu par e-mail pour valider votre compte.</p>
      <TextField
        label="Code de vérification"
        type="text"
        value={code}
        onChange={(value) => setCode(value.replace(/\D/g, "").slice(0, 6))}
        placeholder="123456"
        maxLength={6}
        inputMode="numeric"
        required
        t={t}
      />
      <Button type="submit" loading={loading}>Vérifier mon e-mail</Button>

      <button
        type="button"
        onClick={handleResendClick}
        disabled={resendCountdown > 0 || loading}
        className="inline-flex items-center justify-center rounded-full border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {resendCountdown > 0 ? `Renvoyer le code (${resendCountdown}s)` : "Renvoyer le code"}
      </button>
    </form>
  );
}

function RegisteredPanel({ onContinue, onVerifyEmail }) {
  return (
    <div className="flex flex-col items-center gap-4">
      <Button type="button" onClick={onVerifyEmail}>Vérifier mon e-mail</Button>
      <Button type="button" variant="secondary" onClick={onContinue}>Accéder à Mall</Button>
    </div>
  );
}

/* -------------------------------- Shell ---------------------------------- */

function AuthShell({ t, isDark, onToggleTheme, title, subtitle, children }) {
  return (
    <div className={cx("flex min-h-screen items-center justify-center px-4 py-10 transition-colors", t.pageBg)}>
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-between">
          <span className="text-2xl font-semibold text-indigo-600">Mall</span>
          <button onClick={onToggleTheme} aria-label="Changer de thème" className={cx("rounded-full border p-2", t.border)}>
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
        <div className={cx("rounded-3xl border p-6 sm:p-8", t.cardBorder, t.cardBg)}>
          <h1 className={cx("text-2xl font-semibold", t.textPrimary)}>{title}</h1>
          {subtitle && <p className={cx("mt-1 text-sm", t.textMuted)}>{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
        <p className={cx("mt-4 text-center text-[11px]", t.textMuted)}>API : {API_BASE_URL}</p>
      </div>
    </div>
  );
}

/* --------------------------------- Page ----------------------------------- */

const SCREENS = {
  login: { title: "Content de vous revoir", subtitle: "Connectez-vous pour acheter et vendre en toute sécurité." },
  register: { title: "Créez votre compte", subtitle: "Rejoignez des vendeurs et acheteurs à travers l'Afrique." },
  registered: { title: "Compte créé !", subtitle: "Vous pouvez dès à présent utiliser votre compte." },
  forgot: { title: "Mot de passe oublié ?", subtitle: null },
  "reset-code": { title: "Vérifier votre code", subtitle: "Un code à 6 chiffres a été envoyé par e-mail." },
  reset: { title: "Nouveau mot de passe", subtitle: "Choisissez un nouveau mot de passe." },
  "verify-email": { title: "Vérification de l'e-mail", subtitle: null },
};

export default function AuthPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isDark, toggleTheme, t } = useTheme();
  const {
    isAuthenticated, authLoading, authError, authNotice, clearAuthMessages,
    login, register, forgotPassword, verifyPasswordResetCode, resetPassword, confirmEmail, resendEmailVerification,
  } = useAuth();

  const [mode, setMode] = useState(searchParams.get("mode") === "register" ? "register" : "login");
  const [resetEmail, setResetEmail] = useState(searchParams.get("email") || "");
  const [resetCode, setResetCode] = useState("");
  const [pendingVerification, setPendingVerification] = useState(null);

  // Déjà connecté → retour à l'accueil. Exception : juste après l'inscription
  // (mode "registered"), on laisse le message "compte créé" s'afficher avant
  // que la personne ne continue elle-même — pas de vérification bloquante
  // avant d'accéder à l'app (email seulement désormais, pas de code à saisir).
  useEffect(() => {
    if (isAuthenticated && mode !== "registered") navigate("/", { replace: true });
  }, [isAuthenticated, mode, navigate]);

  // Compatibilité avec l'ancien lien d'inscription : si un code est passé via un paramètre legacy,
  // on ouvre aussi l'écran de vérification, mais le flux actuel demande une saisie manuelle.
  useEffect(() => {
    if (searchParams.get("email_token")) setMode("verify-email");
  }, [searchParams]);

  function switchMode(next) {
    setMode(next);
    clearAuthMessages();
  }

  async function handleLogin(values) {
    try {
      await login(values); // redirection gérée par le useEffect une fois isAuthenticated = true
    } catch {
      /* authError déjà affiché */
    }
  }

  async function handleRegister(form) {
    try {
      await register(form);
      setPendingVerification({ email: form.email, password: form.password });
      switchMode("verify-email");
    } catch {
      /* authError déjà affiché */
    }
  }

  async function handleResendVerification() {
    if (!pendingVerification?.email) return;
    try {
      await resendEmailVerification(pendingVerification.email);
      setPendingVerification((current) => ({
        ...current,
        resendNotice: "Nouveau code envoyé. Vérifiez votre boîte mail.",
      }));
    } catch {
      /* authError déjà affiché */
    }
  }

  async function handleForgotPassword(email) {
    try {
      await forgotPassword(email);
      setResetEmail(email);
      setMode("reset-code");
    } catch {
      /* authError déjà affiché */
    }
  }

  async function handleVerifyResetCode(values) {
    try {
      await verifyPasswordResetCode(values);
      setResetEmail(values.email);
      setResetCode(values.code);
      setMode("reset");
    } catch {
      /* authError déjà affiché */
    }
  }

  async function handleResetPassword(payload) {
    try {
      await resetPassword(payload);
      setMode("login");
    } catch {
      /* authError déjà affiché */
    }
  }

  return (
    <AuthShell t={t} isDark={isDark} onToggleTheme={toggleTheme} title={SCREENS[mode].title} subtitle={SCREENS[mode].subtitle}>
      {authError && <Alert type="error">{authError}</Alert>}
      {pendingVerification?.resendNotice && !authError && (
        <Alert type="success">{pendingVerification.resendNotice}</Alert>
      )}
      {authNotice && !authError && !pendingVerification?.resendNotice && <Alert type="success">{authNotice}</Alert>}

      {mode === "login" && (
        <LoginForm t={t} loading={authLoading} onSubmit={handleLogin} onForgot={() => switchMode("forgot")} onSwitch={() => switchMode("register")} />
      )}
      {mode === "register" && (
        <RegisterForm t={t} loading={authLoading} onSubmit={handleRegister} onSwitch={() => switchMode("login")} />
      )}
      {mode === "registered" && <RegisteredPanel onContinue={() => navigate("/")} onVerifyEmail={() => switchMode("verify-email")} />}
      {mode === "forgot" && (
        <ForgotPasswordForm t={t} loading={authLoading} onSubmit={handleForgotPassword} onSwitch={() => switchMode("login")} onHaveToken={() => switchMode("reset-code")} />
      )}
      {mode === "reset-code" && (
        <PasswordResetCodeForm
          t={t}
          loading={authLoading}
          initialEmail={resetEmail}
          onSubmit={handleVerifyResetCode}
          onSwitch={() => switchMode("login")}
        />
      )}
      {mode === "reset" && (
        <ResetPasswordForm
          t={t}
          loading={authLoading}
          onSubmit={handleResetPassword}
          onSwitch={() => switchMode("login")}
          initialEmail={resetEmail}
          initialCode={resetCode}
        />
      )}
      {mode === "verify-email" && (
        <VerifyEmailForm
          t={t}
          loading={authLoading}
          initialEmail={pendingVerification?.email || ""}
          initialPassword={pendingVerification?.password || ""}
          onSubmit={confirmEmail}
          onResend={handleResendVerification}
          resendCooldown={30}
        />
      )}
    </AuthShell>
  );
}
