import { getData } from "country-list";

const COUNTRY_NAMES = new Intl.DisplayNames(["fr"], { type: "region" });

export const WORLD_COUNTRIES = getData()
  .filter(({ code }) => /^[A-Z]{2}$/.test(code))
  .map(({ code, name }) => ({ code, name: COUNTRY_NAMES.of(code) || name }))
  .sort((a, b) => a.name.localeCompare(b.name, "fr"));

export function getCountryAlpha2(code) {
  return code === "COD" ? "CD" : code;
}