export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

const REFRESH_STORAGE_KEY = "mall_refresh_token";

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
    refreshToken = refresh;
    if (typeof window !== "undefined") {
      if (refresh) localStorage.setItem(REFRESH_STORAGE_KEY, refresh);
      else localStorage.removeItem(REFRESH_STORAGE_KEY);
    }
  }
}

export function clearTokens() {
  setTokens({ access: null, refresh: null });
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

export async function apiRequest(path, options = {}) {
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

// Le backend DRF pagine par défaut ({count, next, previous, results}).
export const unwrap = (payload) => (Array.isArray(payload) ? payload : payload?.results ?? []);
