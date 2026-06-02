/** Buy-now price for buyers: time-limited offer from seller quote, else list price. */
export function effectivePartBuyPrice(part) {
  if (!part) return null;
  const o = part.effective_buy_price;
  if (o != null && o !== "") {
    const n = Number(o);
    return Number.isFinite(n) ? n : null;
  }
  if (part.price != null && part.price !== "") {
    const n = Number(part.price);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}
