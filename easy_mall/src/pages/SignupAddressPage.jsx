import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { AreaField, Button, TextField } from "../components/ui/FormControls";
import { SectionHeading } from "../components/ui/StatusBlocks";
import { useAuth } from "../features/auth/AuthContext";
import { useTheme } from "../features/theme/ThemeContext";
import { createPrivateAddress, fetchAreas, fetchCountries } from "../features/localization/api";
import { getCountryAlpha2, WORLD_COUNTRIES } from "../features/localization/countries";
import { cx } from "../styles/theme";

const EMPTY_ADDRESS = {
  label: "",
  countryId: "",
  countryCode: "",
  countryName: "",
  areaName: "",
  streetAddress: "",
  landmark: "",
  phoneNumber: "",
};

export default function SignupAddressPage() {
  const { t } = useTheme();
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const [address, setAddress] = useState(EMPTY_ADDRESS);
  const [countries, setCountries] = useState([]);
  const [areas, setAreas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const inputClass = cx("w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:border-indigo-500", t.inputBg, t.border, t.textPrimary);

  useEffect(() => {
    if (!isAuthenticated || !user?.is_email_verified) {
      navigate("/auth", { replace: true });
    }
  }, [isAuthenticated, navigate, user?.is_email_verified]);

  useEffect(() => {
    fetchCountries().then(setCountries).catch(() => setCountries([]));
  }, []);

  useEffect(() => {
    if (!address.countryId) {
      setAreas([]);
      return;
    }
    fetchAreas({ country: address.countryId, level: "province" })
      .then(setAreas)
      .catch(() => setAreas([]));
  }, [address.countryId]);

  function update(field, value) {
    setAddress((current) => ({ ...current, [field]: value }));
  }

  function handleCountryChange(countryCode) {
    const country = WORLD_COUNTRIES.find((item) => item.code === countryCode);
    const savedCountry = countries.find((item) => getCountryAlpha2(item.code) === countryCode);
    setAddress((current) => ({
      ...current,
      countryId: savedCountry?.id || "",
      countryCode: country?.code || "",
      countryName: country?.name || "",
      areaName: "",
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await createPrivateAddress({
        label: address.label,
        ...(address.countryId
          ? { country_id: address.countryId }
          : { country_code: address.countryCode, country_name: address.countryName }),
        administrative_area_id: null,
        administrative_area_name: address.areaName,
        street_address: address.streetAddress,
        landmark: address.landmark,
        phone_number: address.phoneNumber,
        is_default: true,
      });
      navigate("/", { replace: true });
    } catch (requestError) {
      setError(requestError.message || "Impossible d’enregistrer cette adresse.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={cx("min-h-screen transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />
      <main className="mx-auto max-w-xl px-4 py-10 sm:px-6">
        <SectionHeading
          title="Votre adresse de livraison"
          subtitle="Ajoutez une adresse pour qu’elle soit proposée par défaut lors de vos commandes. Elle restera privée."
          t={t}
        />
        <form onSubmit={handleSubmit} className={cx("flex flex-col gap-4 rounded-2xl border p-5", t.cardBorder, t.cardBg)}>
          {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
          <TextField label="Nom de l’adresse (facultatif)" value={address.label} onChange={(value) => update("label", value)} placeholder="Maison, travail" t={t} />
          <label className="block">
            <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Pays</span>
            <select value={address.countryCode} onChange={(event) => handleCountryChange(event.target.value)} required className={inputClass}>
              <option value="">Sélectionner un pays</option>
              {WORLD_COUNTRIES.map((country) => <option key={country.code} value={country.code}>{country.name}</option>)}
            </select>
          </label>
          <AreaField
            label="Province / région (facultatif)"
            value={address.areaName}
            onChange={(value) => update("areaName", value)}
            areas={areas}
            placeholder="Choisir une suggestion ou saisir une région"
            maxLength={150}
            t={t}
          />
          <TextField label="Adresse détaillée" value={address.streetAddress} onChange={(value) => update("streetAddress", value)} placeholder="Avenue, numéro ou repère" required maxLength={255} t={t} />
          <TextField label="Repère (facultatif)" value={address.landmark} onChange={(value) => update("landmark", value)} placeholder="Près du marché" maxLength={255} t={t} />
          <TextField label="Téléphone (facultatif)" value={address.phoneNumber} onChange={(value) => update("phoneNumber", value)} type="tel" autoComplete="tel" t={t} />
          <Button type="submit" loading={loading} disabled={loading || !address.countryCode || !address.streetAddress.trim()}>
            Enregistrer mon adresse
          </Button>
          <button type="button" onClick={() => navigate("/", { replace: true })} className={cx("py-2 text-sm font-medium", t.textMuted)}>
            Je le ferai plus tard
          </button>
        </form>
      </main>
      <SiteFooter t={t} />
    </div>
  );
}