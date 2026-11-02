import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Mail } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { SectionHeading } from "../components/ui/StatusBlocks";
import { TextField, PasswordField, Button, Alert } from "../components/ui/FormControls";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { updateProfile, changePassword } from "../features/profile/api";
import { fetchCountries, fetchAreas } from "../features/localization/api";
import { uploadToCloudinary } from "../lib/cloudinary";
import { cx } from "../styles/theme";

export default function SettingsPage() {
  const { t } = useTheme();
  const { user, isAuthenticated, updateUser, resendEmailVerification, authLoading } = useAuth();
  const navigate = useNavigate();
  const [resendNotice, setResendNotice] = useState(null);
  const [resendError, setResendError] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) navigate("/auth");
  }, [isAuthenticated, navigate]);

  async function handleResend() {
    setResendNotice(null);
    setResendError(null);
    try {
      await resendEmailVerification();
      setResendNotice("Code de vérification renvoyé.");
    } catch (err) {
      setResendError(err.message);
    }
  }

  const [form, setForm] = useState({
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    bio: user?.bio || "",
    avatar_url: user?.avatar_url || "",
    city: user?.city || "",
    country: user?.country || "",
    seller_type: user?.seller_type || "individual",
    shop_name: user?.shop_name || "",
    shop_description: user?.shop_description || "",
    shop_logo_url: user?.shop_logo_url || "",
    shop_cover_url: user?.shop_cover_url || "",
  });
  const [profileError, setProfileError] = useState(null);
  const [profileNotice, setProfileNotice] = useState(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [countries, setCountries] = useState([]);
  const [areas, setAreas] = useState([]);
  const [selectedCountryId, setSelectedCountryId] = useState("");
  const [selectedAreaId, setSelectedAreaId] = useState("");
  const update = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  useEffect(() => {
    fetchCountries().then((data) => {
      setCountries(data);
      if (!data.length) return;
      const userCountry = (user?.country || "").trim();
      const match = data.find((country) => country.name.toLowerCase() === userCountry.toLowerCase()
        || country.code.toLowerCase() === userCountry.toLowerCase());
      if (match) {
        setSelectedCountryId(match.id);
      } else {
        setSelectedCountryId(data[0].id);
        update("country")(data[0].name);
      }
    }).catch(() => {});
  }, [user?.country]);

  useEffect(() => {
    if (!selectedCountryId) {
      setAreas([]);
      setSelectedAreaId("");
      return;
    }

    fetchAreas({ country: selectedCountryId, level: "province" })
      .then((data) => {
        setAreas(data);
        const userCity = (user?.city || "").trim();
        const match = data.find((area) => area.name.toLowerCase() === userCity.toLowerCase());
        if (match) {
          setSelectedAreaId(match.id);
          update("city")(match.name);
        } else {
          setSelectedAreaId("");
        }
      })
      .catch(() => setAreas([]));
  }, [selectedCountryId, user?.city]);

  const selectedCountry = countries.find((country) => country.id === selectedCountryId) || null;
  const selectedArea = areas.find((area) => area.id === selectedAreaId) || null;

  function handleCountryChange(countryId) {
    const targetCountry = countries.find((country) => country.id === countryId);
    setSelectedCountryId(countryId);
    setSelectedAreaId("");
    setAreas([]);
    update("country")(targetCountry ? targetCountry.name : "");
    update("city")("");
  }

  function handleAreaChange(areaId) {
    const targetArea = areas.find((area) => area.id === areaId);
    setSelectedAreaId(areaId);
    update("city")(targetArea ? targetArea.name : "");
  }

  async function handleAvatarChange(file) {
    if (!file) return;
    setUploadingAvatar(true);
    setProfileError(null);
    try {
      update("avatar_url")(await uploadToCloudinary(file));
    } catch (error) {
      setProfileError(error.message || "Le téléchargement de la photo a échoué.");
    } finally {
      setUploadingAvatar(false);
    }
  }

  async function handleProfileSubmit(e) {
    e.preventDefault();
    setSavingProfile(true);
    setProfileError(null);
    setProfileNotice(null);
    try {
      const updated = await updateProfile(form);
      updateUser(updated);
      setProfileNotice("Profil mis à jour.");
    } catch (err) {
      setProfileError(err.message);
    } finally {
      setSavingProfile(false);
    }
  }

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState(null);
  const [passwordNotice, setPasswordNotice] = useState(null);
  const [savingPassword, setSavingPassword] = useState(false);

  async function handlePasswordSubmit(e) {
    e.preventDefault();
    setSavingPassword(true);
    setPasswordError(null);
    setPasswordNotice(null);
    try {
      await changePassword({ old_password: oldPassword, new_password: newPassword });
      setPasswordNotice("Mot de passe modifié.");
      setOldPassword("");
      setNewPassword("");
    } catch (err) {
      setPasswordError(err.message);
    } finally {
      setSavingPassword(false);
    }
  }

  const inputClass = cx(
    "w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:border-indigo-500",
    t.inputBg, t.border, t.textPrimary
  );

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto max-w-xl px-4 py-10 sm:px-6">
        <SectionHeading title="Paramètres du compte" t={t} />

        <div className={cx("mb-8 flex items-center justify-between gap-4 rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
          {user?.is_email_verified ? (
            <span className="flex items-center gap-2 text-sm font-medium text-emerald-600">
              <CheckCircle2 className="h-4 w-4" /> E-mail vérifié
            </span>
          ) : (
            <>
              <span className={cx("flex items-center gap-2 text-sm font-medium", t.textMuted)}>
                <Mail className="h-4 w-4" /> E-mail non vérifié
              </span>
              <button
                onClick={handleResend}
                disabled={authLoading}
                className="text-sm font-semibold text-indigo-600 hover:underline disabled:opacity-60"
              >
                Renvoyer le code
              </button>
            </>
          )}
        </div>
        {(resendNotice || resendError) && (
          <div className="mb-6">
            <Alert type={resendError ? "error" : "success"}>{resendError || resendNotice}</Alert>
          </div>
        )}

        <form onSubmit={handleProfileSubmit} className="flex flex-col gap-4">
          {profileError && <Alert type="error">{profileError}</Alert>}
          {profileNotice && !profileError && <Alert type="success">{profileNotice}</Alert>}
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Prénom" value={form.first_name} onChange={update("first_name")} t={t} />
            <TextField label="Nom" value={form.last_name} onChange={update("last_name")} t={t} />
          </div>
          <label className="block">
            <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Biographie</span>
            <textarea value={form.bio} onChange={(e) => update("bio")(e.target.value)} rows={3} className={inputClass} />
          </label>
          <label className="block">
            <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Photo de profil</span>
            <input
              type="file"
              accept="image/*"
              onChange={(event) => handleAvatarChange(event.target.files?.[0])}
              className={cx("w-full rounded-xl border px-3 py-2 text-sm", t.border, t.inputBg, t.textPrimary)}
            />
            {uploadingAvatar && <span className={cx("mt-1 block text-xs", t.textMuted)}>Téléchargement de la photo…</span>}
            {form.avatar_url && <img src={form.avatar_url} alt="Aperçu de la photo de profil" className="mt-2 h-20 w-20 rounded-full object-cover" />}
          </label>
          <div className={cx("grid grid-cols-2 gap-3 rounded-xl border p-2", t.border)}>
            {[
              ["individual", "Particulier"],
              ["professional", "Commerçant professionnel"],
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
          {form.seller_type === "professional" && (
            <>
              <TextField label="Nom de la boutique" value={form.shop_name} onChange={update("shop_name")} t={t} />
              <label className="block">
                <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Description de la boutique</span>
                <textarea value={form.shop_description} onChange={(e) => update("shop_description")(e.target.value)} rows={3} className={inputClass} />
              </label>
            </>
          )}
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Pays</span>
              <select value={selectedCountryId} onChange={(event) => handleCountryChange(event.target.value)} className={inputClass}>
                <option value="">Sélectionner un pays</option>
                {countries.map((country) => (
                  <option key={country.id} value={country.id}>{country.name}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Province / ville</span>
              <select value={selectedAreaId} onChange={(event) => handleAreaChange(event.target.value)} className={inputClass} disabled={!selectedCountryId}>
                <option value="">Sélectionner</option>
                {areas.map((area) => (
                  <option key={area.id} value={area.id}>{area.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Ville affichée" value={form.city} onChange={update("city")} t={t} />
            <TextField label="Pays affiché" value={form.country} onChange={update("country")} t={t} />
          </div>
          <Button type="submit" loading={savingProfile || uploadingAvatar} disabled={uploadingAvatar}>Enregistrer le profil</Button>
        </form>

        <div className={cx("my-10 border-t", t.border)} />

        <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-4">
          <SectionHeading title="Changer de mot de passe" t={t} />
          {passwordError && <Alert type="error">{passwordError}</Alert>}
          {passwordNotice && !passwordError && <Alert type="success">{passwordNotice}</Alert>}
          <PasswordField label="Mot de passe actuel" value={oldPassword} onChange={setOldPassword} autoComplete="current-password" t={t} />
          <PasswordField label="Nouveau mot de passe" value={newPassword} onChange={setNewPassword} autoComplete="new-password" t={t} />
          <Button type="submit" loading={savingPassword}>Modifier le mot de passe</Button>
        </form>
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
