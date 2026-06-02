const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

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
 * Caller should check res.ok and read res.blob() / res.text().
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

export { API_URL };
