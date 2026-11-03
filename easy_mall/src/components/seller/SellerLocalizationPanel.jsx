import React, { useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { Alert, Button, TextField } from "../ui/FormControls";
import { SectionHeading } from "../ui/StatusBlocks";
import {
  createDeliveryOption,
  createPickupLocation,
  deleteDeliveryOption,
  deletePickupLocation,
  fetchAreas,
  fetchCountries,
  fetchDeliveryOptions,
  fetchLocationPreferences,
  fetchPickupLocations,
  fetchSellerLocation,
  saveLocationPreferences,
  saveSellerLocation,
  updateDeliveryOption,
  updatePickupLocation,
} from "../../features/localization/api";
import { cx } from "../../styles/theme";

const MODES = [
  ["pickup", "Remise en main propre"],
  ["in_city", "Livraison dans la ville"],
  ["in_area", "Livraison dans certaines zones"],
  ["in_province", "Livraison dans la province / région"],
  ["national", "Livraison nationale"],
  ["international", "Livraison internationale"],
];
const EMPTY_DELIVERY = { mode: "pickup", conditions: "", fees: "0", estimated_delivery_days: "0" };
const EMPTY_PICKUP = { name: "", location_type: "public", description: "", instructions: "" };

export function SellerLocalizationPanel({ t }) {
  const [countries, setCountries] = useState([]);
  const [areas, setAreas] = useState([]);
  const [children, setChildren] = useState([]);
  const [location, setLocation] = useState({ country_id: "", administrative_area_id: "", locality_id: "", precision: "city", public_note: "" });
  const [preferences, setPreferences] = useState({ show_country: true, show_admin_area: true, show_locality: false, show_public_note: false });
  const [deliveryOptions, setDeliveryOptions] = useState([]);
  const [pickupLocations, setPickupLocations] = useState([]);
  const [deliveryForm, setDeliveryForm] = useState(EMPTY_DELIVERY);
  const [pickupForm, setPickupForm] = useState(EMPTY_PICKUP);
  const [editingDelivery, setEditingDelivery] = useState(null);
  const [editingPickup, setEditingPickup] = useState(null);
  const [areaSearch, setAreaSearch] = useState("");
  const [searchedArea, setSearchedArea] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const inputClass = cx("w-full rounded-xl border px-4 py-2.5 text-sm", t.inputBg, t.border, t.textPrimary);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetchCountries(),
      fetchSellerLocation().catch(() => null),
      fetchLocationPreferences(),
      fetchDeliveryOptions(),
      fetchPickupLocations(),
    ]).then(([countryList, savedLocation, savedPreferences, deliveryList, pickupList]) => {
      if (!active) return;
      setCountries(countryList);
      if (savedLocation) {
        setLocation({
          country_id: savedLocation.country?.id || "",
          administrative_area_id: savedLocation.administrative_area?.id || "",
          locality_id: savedLocation.locality?.id || "",
          precision: savedLocation.precision || "city",
          public_note: savedLocation.public_note || "",
        });
        setAreaSearch(savedLocation.administrative_area?.name || "");
        setSearchedArea(savedLocation.administrative_area?.name || "");
      }
      setPreferences(savedPreferences);
      setDeliveryOptions(deliveryList);
      setPickupLocations(pickupList);
    }).catch((loadError) => {
      if (active) setError(loadError.message || "Impossible de charger les réglages.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    if (!location.country_id || !searchedArea.trim()) {
      setAreas([]);
      return () => { active = false; };
    }
    fetchAreas({ country: location.country_id, search: searchedArea.trim() })
      .then((items) => { if (active) setAreas(items); })
      .catch(() => { if (active) setAreas([]); });
    return () => { active = false; };
  }, [location.country_id, searchedArea]);

  useEffect(() => {
    let active = true;
    if (!location.administrative_area_id || !location.country_id) {
      setChildren([]);
      return () => { active = false; };
    }
    fetchAreas({ country: location.country_id, parent: location.administrative_area_id })
      .then((items) => { if (active) setChildren(items); })
      .catch(() => { if (active) setChildren([]); });
    return () => { active = false; };
  }, [location.country_id, location.administrative_area_id]);

  const country = countries.find((item) => item.id === location.country_id);
  const area = areas.find((item) => item.id === location.administrative_area_id);
  const locality = children.find((item) => item.id === location.locality_id);
  const preview = [
    preferences.show_country ? country?.name : "",
    preferences.show_admin_area ? area?.name : "",
    preferences.show_locality ? locality?.name : "",
    preferences.show_public_note ? location.public_note : "",
  ].filter(Boolean).join(", ");

  async function saveLocation(event) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try {
      await saveSellerLocation(location);
      await saveLocationPreferences(preferences);
      setNotice("Localisation publique enregistrée.");
    } catch (saveError) { setError(saveError.message || "La localisation n’a pas pu être enregistrée."); }
    finally { setSaving(false); }
  }

  async function saveDelivery(event) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    const payload = { ...deliveryForm, country_id: location.country_id || null };
    try {
      const saved = editingDelivery
        ? await updateDeliveryOption(editingDelivery, payload)
        : await createDeliveryOption(payload);
      setDeliveryOptions((items) => editingDelivery ? items.map((item) => item.id === saved.id ? saved : item) : [...items, saved]);
      setDeliveryForm(EMPTY_DELIVERY); setEditingDelivery(null); setNotice("Mode de livraison enregistré.");
    } catch (saveError) { setError(saveError.message || "Le mode n’a pas pu être enregistré."); }
    finally { setSaving(false); }
  }

  async function savePickup(event) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    const payload = { ...pickupForm, country_id: location.country_id, administrative_area_id: location.administrative_area_id || null, locality_id: location.locality_id || null };
    try {
      const saved = editingPickup
        ? await updatePickupLocation(editingPickup, payload)
        : await createPickupLocation(payload);
      setPickupLocations((items) => editingPickup ? items.map((item) => item.id === saved.id ? saved : item) : [...items, saved]);
      setPickupForm(EMPTY_PICKUP); setEditingPickup(null); setNotice("Lieu de remise enregistré.");
    } catch (saveError) { setError(saveError.message || "Le lieu n’a pas pu être enregistré."); }
    finally { setSaving(false); }
  }

  async function toggleActive(item, isPickup) {
    const update = isPickup ? updatePickupLocation : updateDeliveryOption;
    const setter = isPickup ? setPickupLocations : setDeliveryOptions;
    try {
      const saved = await update(item.id, { is_active: !item.is_active });
      setter((items) => items.map((entry) => entry.id === saved.id ? saved : entry));
    } catch (toggleError) { setError(toggleError.message); }
  }

  async function removeItem(item, isPickup) {
    const remove = isPickup ? deletePickupLocation : deleteDeliveryOption;
    const setter = isPickup ? setPickupLocations : setDeliveryOptions;
    try {
      await remove(item.id);
      setter((items) => items.filter((entry) => entry.id !== item.id));
    } catch (removeError) { setError(removeError.message); }
  }

  function editDelivery(item) {
    setEditingDelivery(item.id);
    setDeliveryForm({ mode: item.mode, conditions: item.conditions || "", fees: item.fees, estimated_delivery_days: item.estimated_delivery_days });
  }

  function editPickup(item) {
    setEditingPickup(item.id);
    setPickupForm({ name: item.name, location_type: item.location_type, description: item.description || "", instructions: item.instructions || "" });
  }

  if (loading) return <p className={cx("py-6 text-sm", t.textMuted)}>Chargement des réglages…</p>;

  return (
    <div className="space-y-10">
      {error && <Alert>{error}</Alert>}{notice && <Alert type="success">{notice}</Alert>}
      <form onSubmit={saveLocation} className="space-y-4">
        <SectionHeading title="Localisation publique" t={t} />
        <p className={cx("text-sm", t.textMuted)}>Votre adresse complète et vos coordonnées précises restent privées. Choisissez ce qui peut apparaître sur votre profil et vos annonces.</p>
        <label className="block"><span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Pays</span><select required value={location.country_id} onChange={(event) => setLocation({ ...location, country_id: event.target.value, administrative_area_id: "", locality_id: "" })} className={inputClass}><option value="">Sélectionner un pays</option>{countries.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]"><TextField label="Rechercher une région, ville ou zone" value={areaSearch} onChange={setAreaSearch} placeholder="Saisir quelques lettres" t={t} /><Button type="button" variant="secondary" className="self-end sm:w-auto" disabled={!location.country_id || !areaSearch.trim()} onClick={() => setSearchedArea(areaSearch)}>Rechercher</Button></div>
        <label className="block"><span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Zone administrative</span><select value={location.administrative_area_id} onChange={(event) => setLocation({ ...location, administrative_area_id: event.target.value, locality_id: "" })} className={inputClass} disabled={!areas.length}><option value="">Choisir dans les résultats</option>{areas.map((item) => <option key={item.id} value={item.id}>{item.name}{item.level_label ? ` · ${item.level_label}` : ` · ${item.level}`}</option>)}</select></label>
        {children.length > 0 && <label className="block"><span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Localité ou quartier (facultatif)</span><select value={location.locality_id} onChange={(event) => setLocation({ ...location, locality_id: event.target.value })} className={inputClass}><option value="">Ne pas préciser</option>{children.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
        <label className="block"><span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Précision publique maximale</span><select value={location.precision} onChange={(event) => setLocation({ ...location, precision: event.target.value })} className={inputClass}><option value="country">Pays uniquement</option><option value="province">Région / province</option><option value="city">Ville / commune</option><option value="locality">Inclure la localité</option></select></label>
        <TextField label="Indication publique facultative" value={location.public_note} onChange={(value) => setLocation({ ...location, public_note: value })} maxLength={200} hint="N’indiquez pas votre adresse de domicile ni un repère permettant de vous retrouver." t={t} />
        <fieldset className={cx("space-y-2 rounded-xl border p-4", t.border)}><legend className={cx("px-1 text-sm font-semibold", t.textPrimary)}>Informations visibles par les acheteurs</legend>{[["show_country", "Pays"], ["show_admin_area", "Région / zone administrative"], ["show_locality", "Localité ou quartier"], ["show_public_note", "Indication complémentaire"]].map(([key, label]) => <label key={key} className={cx("flex items-center gap-3 text-sm", t.textPrimary)}><input type="checkbox" checked={preferences[key]} onChange={(event) => setPreferences({ ...preferences, [key]: event.target.checked })} />{label}</label>)}<p className={cx("border-t pt-3 text-sm", t.border, t.textMuted)}>Aperçu public : <strong className={t.textPrimary}>{preview || "Aucune localisation affichée"}</strong></p></fieldset>
        <Button type="submit" loading={saving}>Enregistrer la localisation</Button>
      </form>

      <section className="space-y-4"><SectionHeading title="Modes de livraison" t={t} />
        <form onSubmit={saveDelivery} className={cx("space-y-3 rounded-xl border p-4", t.border)}>
          <label className="block"><span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Mode proposé</span><select value={deliveryForm.mode} onChange={(event) => setDeliveryForm({ ...deliveryForm, mode: event.target.value })} className={inputClass}>{MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <div className="grid gap-3 sm:grid-cols-2"><TextField label="Frais annoncés" type="number" value={deliveryForm.fees} onChange={(value) => setDeliveryForm({ ...deliveryForm, fees: value })} t={t} /><TextField label="Délai estimé (jours)" type="number" value={deliveryForm.estimated_delivery_days} onChange={(value) => setDeliveryForm({ ...deliveryForm, estimated_delivery_days: value })} t={t} /></div>
          <TextField label="Conditions particulières" value={deliveryForm.conditions} onChange={(value) => setDeliveryForm({ ...deliveryForm, conditions: value })} t={t} />
          <Button type="submit" loading={saving}><Plus className="h-4 w-4" />{editingDelivery ? "Enregistrer les modifications" : "Ajouter ce mode"}</Button>
          {editingDelivery && <Button type="button" variant="secondary" onClick={() => { setEditingDelivery(null); setDeliveryForm(EMPTY_DELIVERY); }}>Annuler la modification</Button>}
        </form>
        <div className="space-y-2">{deliveryOptions.map((item) => <div key={item.id} className={cx("flex flex-wrap items-center gap-3 rounded-xl border p-3", t.border)}><span className={cx("min-w-40 flex-1 text-sm font-medium", t.textPrimary)}>{MODES.find(([value]) => value === item.mode)?.[1] || item.mode} · {item.fees}</span><button type="button" onClick={() => toggleActive(item, false)} className="text-sm font-medium text-indigo-600">{item.is_active ? "Désactiver" : "Activer"}</button><button type="button" onClick={() => editDelivery(item)} aria-label="Modifier le mode"><Pencil className="h-4 w-4" /></button><button type="button" onClick={() => removeItem(item, false)} aria-label="Supprimer le mode"><Trash2 className="h-4 w-4 text-rose-600" /></button></div>)}</div>
      </section>

      <section className="space-y-4"><SectionHeading title="Lieux de remise" t={t} /><p className={cx("text-sm", t.textMuted)}>Les lieux privés ne sont pas publiés. Ne communiquez une adresse précise qu’aux personnes concernées, au moment nécessaire.</p>
        <form onSubmit={savePickup} className={cx("space-y-3 rounded-xl border p-4", t.border)}>
          <TextField label="Nom du lieu" value={pickupForm.name} onChange={(value) => setPickupForm({ ...pickupForm, name: value })} required t={t} />
          <label className="block"><span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>Type de lieu</span><select value={pickupForm.location_type} onChange={(event) => setPickupForm({ ...pickupForm, location_type: event.target.value })} className={inputClass}><option value="public">Lieu public et général</option><option value="agreed">Point convenu avec l’acheteur</option><option value="private">Lieu privé communiqué au besoin</option></select></label>
          <TextField label="Description" value={pickupForm.description} onChange={(value) => setPickupForm({ ...pickupForm, description: value })} t={t} /><TextField label="Instructions pratiques" value={pickupForm.instructions} onChange={(value) => setPickupForm({ ...pickupForm, instructions: value })} t={t} />
          <Button type="submit" loading={saving}><Plus className="h-4 w-4" />{editingPickup ? "Enregistrer les modifications" : "Ajouter un lieu"}</Button>
          {editingPickup && <Button type="button" variant="secondary" onClick={() => { setEditingPickup(null); setPickupForm(EMPTY_PICKUP); }}>Annuler la modification</Button>}
        </form>
        <div className="space-y-2">{pickupLocations.map((item) => <div key={item.id} className={cx("flex flex-wrap items-center gap-3 rounded-xl border p-3", t.border)}><span className={cx("min-w-40 flex-1 text-sm font-medium", t.textPrimary)}>{item.name}</span><button type="button" onClick={() => toggleActive(item, true)} className="text-sm font-medium text-indigo-600">{item.is_active ? "Désactiver" : "Activer"}</button><button type="button" onClick={() => editPickup(item)} aria-label="Modifier le lieu"><Pencil className="h-4 w-4" /></button><button type="button" onClick={() => removeItem(item, true)} aria-label="Supprimer le lieu"><Trash2 className="h-4 w-4 text-rose-600" /></button></div>)}</div>
      </section>
    </div>
  );
}