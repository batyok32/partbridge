export const STATE_ZONE = {
  CA: 1, OR: 1, WA: 1, NV: 1, AZ: 1,
  TX: 2, FL: 2, GA: 2, NC: 2, SC: 2, VA: 2, TN: 2, LA: 2, AL: 2, MS: 2,
};

export const SHIPPING_MID = { small: 11, medium: 35, large: 550 };
export const SHIPPING_ECONOMY = { large: 100, xl: 150 };

export const STATE_TAX_RATES = {
  AL: 0.04,   AK: 0.00,  AZ: 0.056,  AR: 0.065,
  CA: 0.0725, CO: 0.029, CT: 0.0635, DE: 0.00,
  FL: 0.06,   GA: 0.04,  HI: 0.04,   ID: 0.06,
  IL: 0.0625, IN: 0.07,  IA: 0.06,   KS: 0.065,
  KY: 0.06,   LA: 0.0445,ME: 0.055,  MD: 0.06,
  MA: 0.0625, MI: 0.06,  MN: 0.06875,MS: 0.07,
  MO: 0.04225,MT: 0.00,  NE: 0.055,  NV: 0.0685,
  NH: 0.00,   NJ: 0.06625,NM: 0.05,  NY: 0.04,
  NC: 0.0475, ND: 0.05,  OH: 0.0575, OK: 0.045,
  OR: 0.00,   PA: 0.06,  RI: 0.07,   SC: 0.06,
  SD: 0.045,  TN: 0.07,  TX: 0.0625, UT: 0.0485,
  VT: 0.06,   VA: 0.043, WA: 0.065,  WV: 0.06,
  WI: 0.05,   WY: 0.04,  DC: 0.06,
};

export function estimateShipping(shippingSize, buyerState, mode = "standard") {
  if (shippingSize === "xl") return SHIPPING_ECONOMY.xl;
  if (mode === "economy" && shippingSize === "large") return SHIPPING_ECONOMY.large;
  const zone = STATE_ZONE[(buyerState || "").toUpperCase()] || 3;
  const factor = zone === 1 ? 1.0 : zone === 2 ? 1.15 : 1.3;
  return Math.round((SHIPPING_MID[shippingSize] || 35) * factor * 100) / 100;
}

export function estimateTax(partsSubtotal, buyerState) {
  const rate = STATE_TAX_RATES[(buyerState || "").toUpperCase()] || 0;
  return Math.round(partsSubtotal * rate * 100) / 100;
}

export function deliveryTime(shippingSize, mode) {
  if (shippingSize === "small") return "3–7 days";
  if (shippingSize === "medium") return "5–10 days";
  if (shippingSize === "large" && mode !== "economy") return "5–14 days";
  return "~30 days";
}

export function isFreight(size) {
  return size === "large" || size === "xl";
}
