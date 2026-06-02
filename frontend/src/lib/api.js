const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

const CATALOG_URL = (
  process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/v1\/?$/, "")
    : "http://127.0.0.1:8000"
) + "/api/catalog";

const PARTS_URL = (
  process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/v1\/?$/, "")
    : "http://127.0.0.1:8000"
) + "/api/parts";

const BUNDLES_URL = (
  process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/v1\/?$/, "")
    : "http://127.0.0.1:8000"
) + "/api/bundles";

export class ApiError extends Error {
  constructor(status, body) {
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : typeof body.message === "string"
          ? body.message
          : `Request failed (${status})`;
    super(detail);
    this.status = status;
    this.body = body;
  }
}

function getAccessToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("lmp_access");
}

function getRefreshToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("lmp_refresh");
}

export function setTokens(access, refresh) {
  localStorage.setItem("lmp_access", access);
  localStorage.setItem("lmp_refresh", refresh);
}

export function clearTokens() {
  localStorage.removeItem("lmp_access");
  localStorage.removeItem("lmp_refresh");
}

export async function refreshAccessToken() {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const res = await fetch(`${API_URL}/auth/token/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) {
    clearTokens();
    return false;
  }
  const data = await res.json();
  localStorage.setItem("lmp_access", data.access);
  if (data.refresh) localStorage.setItem("lmp_refresh", data.refresh);
  return true;
}

export async function apiFetch(path, init = {}) {
  const { auth = true, retryOn401 = true, headers: initHeaders, ...rest } = init;
  const headers = new Headers(initHeaders);
  const isJsonBody = typeof rest.body === "string";
  const isFormData = typeof FormData !== "undefined" && rest.body instanceof FormData;
  if (!headers.has("Content-Type") && isJsonBody) {
    headers.set("Content-Type", "application/json");
  }
  if (isFormData && headers.has("Content-Type")) {
    headers.delete("Content-Type");
  }
  if (auth) {
    const access = getAccessToken();
    if (access) headers.set("Authorization", `Bearer ${access}`);
  }

  const url = path.startsWith("http") ? path : `${API_URL}${path}`;
  let res = await fetch(url, { ...rest, headers });

  if (res.status === 401 && auth && retryOn401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const retryHeaders = new Headers(initHeaders);
      if (!retryHeaders.has("Content-Type") && typeof rest.body === "string") {
        retryHeaders.set("Content-Type", "application/json");
      }
      if (typeof FormData !== "undefined" && rest.body instanceof FormData && retryHeaders.has("Content-Type")) {
        retryHeaders.delete("Content-Type");
      }
      const access = getAccessToken();
      if (access) retryHeaders.set("Authorization", `Bearer ${access}`);
      res = await fetch(url, { ...rest, headers: retryHeaders });
    }
  }

  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!res.ok) {
    throw new ApiError(res.status, data);
  }

  return data;
}

/**
 * Authenticated fetch returning raw Response (e.g. PDF blob).
 */
export async function apiFetchRaw(path, init = {}) {
  const { auth = true, retryOn401 = true, headers: initHeaders, ...rest } = init;
  const headers = new Headers(initHeaders);
  if (auth) {
    const access = getAccessToken();
    if (access) headers.set("Authorization", `Bearer ${access}`);
  }
  const url = path.startsWith("http") ? path : `${API_URL}${path}`;
  let res = await fetch(url, { ...rest, headers });

  if (res.status === 401 && auth && retryOn401) {
    const ok = await refreshAccessToken();
    if (ok) {
      const retryHeaders = new Headers(initHeaders);
      const access = getAccessToken();
      if (access) retryHeaders.set("Authorization", `Bearer ${access}`);
      res = await fetch(url, { ...rest, headers: retryHeaders });
    }
  }
  return res;
}

// ─── Catalog API ─────────────────────────────────────────────────────────────

export async function getMakes() {
  return apiFetch(`${CATALOG_URL}/makes/`, { auth: false });
}

export async function getModels(makeId) {
  const q = makeId ? `?make_id=${makeId}` : "";
  return apiFetch(`${CATALOG_URL}/models/${q}`, { auth: false });
}

export async function getGenerations(modelId) {
  const q = modelId ? `?model_id=${modelId}` : "";
  return apiFetch(`${CATALOG_URL}/generations/${q}`, { auth: false });
}

export async function getModifications(generationId) {
  const q = generationId ? `?generation_id=${generationId}` : "";
  return apiFetch(`${CATALOG_URL}/modifications/${q}`, { auth: false });
}

// ─── Parts API ────────────────────────────────────────────────────────────────

export async function getItems(filters = {}) {
  const params = new URLSearchParams(filters).toString();
  const q = params ? `?${params}` : "";
  return apiFetch(`${PARTS_URL}/items/${q}`, { auth: false });
}

export async function getItem(id) {
  return apiFetch(`${PARTS_URL}/items/${id}/`, { auth: false });
}

export async function getCategories() {
  return apiFetch(`${PARTS_URL}/categories/`, { auth: false });
}

// ─── UserCar API ──────────────────────────────────────────────────────────────

export async function getUserCars() {
  return apiFetch("/user-cars/");
}

export async function addUserCar(data) {
  return apiFetch("/user-cars/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteUserCar(id) {
  return apiFetch(`/user-cars/${id}/`, { method: "DELETE" });
}

// ─── Orders API ───────────────────────────────────────────────────────────────

export async function getOrders() {
  return apiFetch("/orders/");
}

export async function getOrder(id) {
  return apiFetch(`/orders/${id}/`);
}

export async function createOrder(data) {
  return apiFetch("/orders/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ─── Cart API ─────────────────────────────────────────────────────────────────

export async function getCart() {
  return apiFetch("/cart/");
}

export async function addToCart(itemId) {
  return apiFetch("/cart/", {
    method: "POST",
    body: JSON.stringify({ item: itemId }),
  });
}

export async function removeFromCart(cartItemId) {
  return apiFetch(`/cart/${cartItemId}/`, { method: "DELETE" });
}

// ─── Disputes API ─────────────────────────────────────────────────────────────

export async function getDisputes() {
  return apiFetch("/disputes/");
}

export async function createDispute(orderItemId, data) {
  return apiFetch(`/disputes/order-item/${orderItemId}/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getDispute(id) {
  return apiFetch(`/disputes/${id}/`);
}

// ─── Messaging API ────────────────────────────────────────────────────────────

export async function getThreads() {
  return apiFetch("/messages/threads/");
}

export async function startThread(itemId, body) {
  return apiFetch("/messages/start/", {
    method: "POST",
    body: JSON.stringify({ item_id: itemId, body }),
  });
}

export async function getThread(threadId) {
  return apiFetch(`/messages/threads/${threadId}/`);
}

export async function getThreadMessages(threadId) {
  return apiFetch(`/messages/threads/${threadId}/messages/`);
}

export async function sendMessage(threadId, body) {
  return apiFetch(`/messages/threads/${threadId}/messages/`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export async function markThreadRead(threadId) {
  return apiFetch(`/messages/threads/${threadId}/mark-read/`, { method: "POST" });
}

export { API_URL };
