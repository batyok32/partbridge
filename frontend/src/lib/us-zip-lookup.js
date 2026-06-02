import { ApiError, apiFetch } from "@/lib/api";

/**
 * Looks up US city/state for a 5-digit ZIP via the API (Zippopotam-backed).
 * @param {string} zip
 * @returns {Promise<{ postal_code: string, city: string, state: string, places?: { city: string, state: string }[] } | null>}
 */
export async function lookupUsZip(zip) {
  const digits = String(zip || "").replace(/\D/g, "").slice(0, 5);
  if (digits.length !== 5) return null;
  try {
    return await apiFetch(`/us-zip-lookup/?zip=${encodeURIComponent(digits)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}
