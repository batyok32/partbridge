/** Approved sellers may manage inventory (backend: is_seller=true). */

export function isApprovedSeller(user) {
  if (!user) return false;
  if (user.is_approved_seller === true) return true;
  return user.is_seller === true;
}

/** Buyer-side features (cart, purchases) — all authenticated users. */

export function isBuyerCapable(user) {
  return Boolean(user);
}
