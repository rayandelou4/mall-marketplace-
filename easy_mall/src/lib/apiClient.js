export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

const REFRESH_STORAGE_KEY = "mall_refresh_token";
const GET_CACHE_TTL_MS = 30_000;
const GET_CACHE_MAX_ENTRIES = 100;
const getResponseCache = new Map();
const inFlightGets = new Map();

// L'access token ne vit qu'en mémoire (jamais persisté) ; seul le refresh
// token est stocké, pour pouvoir restaurer la session après un rechargement.
// Compromis assumé : localStorage reste lisible par du JS malveillant en cas
// de faille XSS. La version plus sûre (cookie httpOnly posé par le backend)
// est une évolution possible mais demande un changement côté serveur.
let accessToken = null;
let refreshToken = typeof window !== "undefined" ? localStorage.getItem(REFRESH_STORAGE_KEY) : null;

export function setTokens({ access, refresh } = {}) {
  if (access !== undefined) accessToken = access;
  if (refresh !== undefined) {
    if (refreshToken !== refresh) clearReadCache();
    refreshToken = refresh;
    if (typeof window !== "undefined") {
      if (refresh) localStorage.setItem(REFRESH_STORAGE_KEY, refresh);
      else localStorage.removeItem(REFRESH_STORAGE_KEY);
    }
  }
}

export function clearTokens() {
  setTokens({ access: null, refresh: null });
  clearReadCache();
}

function clearReadCache() {
  getResponseCache.clear();
  inFlightGets.clear();
}

export function getRefreshToken() {
  return refreshToken;
}

// Le WebSocket (chat temps réel) en a besoin : un navigateur ne peut pas
// poser d'en-tête Authorization personnalisé à l'ouverture d'une connexion
// WebSocket, le token doit donc voyager dans l'URL de connexion.
export function getAccessToken() {
  return accessToken;
}

function rawFetch(path, { method = "GET", body } = {}) {
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  return fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      ...(!isFormData ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
  });
}

async function parseOrThrow(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const firstFieldError = Object.values(data)[0];
    const message = data.detail || (Array.isArray(firstFieldError) ? firstFieldError[0] : firstFieldError);
    throw new Error(message || "Une erreur est survenue. Réessayez.");
  }
  return data;
}

// Déduplique les refresh concurrents : si 3 requêtes échouent en même temps
// avec un token expiré, une seule requête de refresh part réellement.
let refreshing = null;

function refreshAccessToken() {
  if (!refreshToken) return Promise.reject(new Error("Session expirée, reconnectez-vous."));
  if (!refreshing) {
    refreshing = fetch(`${API_BASE_URL}/accounts/login/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken }),
    })
      .then(parseOrThrow)
      .then((data) => {
        setTokens({ access: data.access });
        return data.access;
      })
      .catch((err) => {
        clearTokens();
        throw err;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function requestAndParse(path, options) {
  let response = await rawFetch(path, options);

  if (response.status === 401 && refreshToken) {
    try {
      await refreshAccessToken();
      response = await rawFetch(path, options); // un seul essai après refresh
    } catch {
      // Le refresh a échoué : on laisse tomber sur la réponse 401 d'origine.
    }
  }

  return parseOrThrow(response);
}

function cloneData(data) {
  return data == null ? data : JSON.parse(JSON.stringify(data));
}

export async function apiRequest(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET") {
    clearReadCache();
    return requestAndParse(path, options);
  }

  const isCatalogRead = path.startsWith("/catalog/categories/")
    || path.startsWith("/catalog/products/");
  if (!isCatalogRead) return requestAndParse(path, options);

  const cacheKey = `${refreshToken || "guest"}:${path}`;
  const cached = getResponseCache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) return cloneData(cached.data);
  if (cached) getResponseCache.delete(cacheKey);

  if (inFlightGets.has(cacheKey)) return cloneData(await inFlightGets.get(cacheKey));

  const request = requestAndParse(path, options)
    .then((data) => {
      getResponseCache.set(cacheKey, { data, expiresAt: Date.now() + GET_CACHE_TTL_MS });
      if (getResponseCache.size > GET_CACHE_MAX_ENTRIES) {
        getResponseCache.delete(getResponseCache.keys().next().value);
      }
      return data;
    })
    .finally(() => inFlightGets.delete(cacheKey));
  inFlightGets.set(cacheKey, request);
  return cloneData(await request);
}

export async function apiDownload(path) {
  let response = await rawFetch(path);

  if (response.status === 401 && refreshToken) {
    try {
      await refreshAccessToken();
      response = await rawFetch(path);
    } catch {
      // Keep the original response so callers receive the API error.
    }
  }

  if (!response.ok) await parseOrThrow(response);
  return response.blob();
}

// Le backend DRF pagine par défaut ({count, next, previous, results}).
export const unwrap = (payload) => (Array.isArray(payload) ? payload : payload?.results ?? []);
