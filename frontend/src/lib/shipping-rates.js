/** Estimated shipping by size tier and destination state (USD). */
export const SHIPPING_RATES = {
  small: { min: 7, max: 15, label: "Small ($7–15)" },
  medium: { min: 20, max: 50, label: "Medium ($20–50)" },
  large: { min: 450, max: 650, label: "Large ($450–650)" },
  xl: { min: 675, max: 975, label: "XL / Freight" },
};

const STATE_ZONE = {
  CA: 1, OR: 1, WA: 1, NV: 1, AZ: 1,
  TX: 2, FL: 2, GA: 2, NC: 2, SC: 2, VA: 2, TN: 2, LA: 2, AL: 2, MS: 2,
};

function zoneForState(state) {
  const s = (state || "").toUpperCase().slice(0, 2);
  return STATE_ZONE[s] ?? 3;
}

/** Midpoint estimate for display on listing cards. */
export function estimateShipping(shippingSize, destinationState) {
  const tier = SHIPPING_RATES[shippingSize];
  if (!tier) return null;
  if (tier.min == null) return null;
  const zone = zoneForState(destinationState);
  const factor = zone === 1 ? 1 : zone === 2 ? 1.15 : 1.3;
  const mid = ((tier.min + tier.max) / 2) * factor;
  return {
    label: tier.label,
    amount: Math.round(mid),
    range: `$${Math.round(tier.min * factor)}–$${Math.round(tier.max * factor)}`,
  };
}

export function formatShippingEstimate(shippingSize, destinationState) {
  const est = estimateShipping(shippingSize, destinationState);
  if (!est) return null;
  if (est.amount == null) return est.range;
  return `~$${est.amount} shipping`;
}
