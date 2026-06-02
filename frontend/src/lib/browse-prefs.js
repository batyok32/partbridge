/** Shared with browse flows: saved buyer ZIP for shipping estimates. */
export const BROWSE_PREFS_KEY = "partbridge_browse_prefs_v2";

export function readSavedBuyerZip() {
  if (typeof window === "undefined") return "";
  try {
    const raw = localStorage.getItem(BROWSE_PREFS_KEY);
    if (!raw) return "";
    const j = JSON.parse(raw);
    return typeof j.buyerZip === "string" ? j.buyerZip : "";
  } catch {
    return "";
  }
}

export function writeSavedBuyerZip(zip) {
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(BROWSE_PREFS_KEY);
    const j = raw ? JSON.parse(raw) : {};
    j.buyerZip = zip;
    localStorage.setItem(BROWSE_PREFS_KEY, JSON.stringify(j));
  } catch {
    /* ignore */
  }
}
