/**
 * Formate un prix selon la devise. CDF s'affiche en entier avec séparateur de
 * milliers ("42 000 CDF" — pas de sous-unité utilisée en pratique), USD avec
 * deux décimales fixes ("$45.00"). Le code devise reste explicite plutôt que
 * de laisser l'API Intl choisir un symbole (ex. "FC" pour CDF) qui ne
 * correspondrait pas à ce qui est affiché ailleurs dans l'app.
 */
export function formatPrice(price, currency = "USD") {
  const numeric = Number(price);
  if (!Number.isFinite(numeric)) return "";

  if (currency === "CDF") {
    return `${numeric.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} CDF`;
  }

  const amount = numeric.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency === "USD" ? `$${amount}` : `${amount} ${currency}`;
}
