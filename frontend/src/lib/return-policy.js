/**
 * Human-readable return policy for buyers (avoid raw codes like "green").
 */
export function returnPolicyBrief(policy) {
  const p = (policy || "").toLowerCase();
  if (p === "green") return "30-day buyer protection — full refund if the part isn’t as described";
  if (p === "yellow") return "Partial returns — restocking fee may apply";
  if (p === "red") return "Final sale — no returns";
  return "See listing for return terms";
}

/** Short label for compact badges (cards, chips). */
export function returnPolicyBadgeLabel(policy) {
  const p = (policy || "").toLowerCase();
  if (p === "green") return "30-day protection";
  if (p === "yellow") return "Partial returns";
  if (p === "red") return "Final sale";
  return "Returns";
}
