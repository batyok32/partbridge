/** Order list tabs: active vs finished. */
export function isOrderCompleted(o) {
  return ["delivered", "refunded", "cancelled"].includes(o?.state);
}

export function isOrderDelivered(o) {
  return o?.state === "delivered";
}

export function orderTabFilter(orders, tab) {
  const list = Array.isArray(orders) ? orders : [];
  if (tab === "completed") return list.filter(isOrderCompleted);
  return list.filter((o) => !isOrderCompleted(o));
}
