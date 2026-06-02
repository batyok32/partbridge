/** Approved sellers may manage inventory (backend: role seller or both). */

export function isApprovedSeller(user) {
  if (!user) return false;
  if (user.is_approved_seller === true) return true;
  return user.role === "seller" || user.role === "both";
}

/** Buyer-side features (cart, purchases) — excludes seller-only accounts. */

export function isBuyerCapable(user) {
  if (!user) return false;
  return user.role === "buyer" || user.role === "both";
}
