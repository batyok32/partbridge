/** Order list tabs: active vs finished. */
export function isOrderCompleted(o) {
  return ["delivered", "cancelled"].includes(o?.status);
}

export function isOrderDelivered(o) {
  return o?.status === "delivered";
}

export function orderTabFilter(orders, tab) {
  const list = Array.isArray(orders) ? orders : [];
  if (tab === "completed") return list.filter(isOrderCompleted);
  return list.filter((o) => !isOrderCompleted(o));
}

export function orderStatusLabel(status) {
  const map = {
    pending: "Awaiting payment",
    confirmed: "Confirmed",
    shipped: "Shipped",
    delivered: "Delivered",
    cancelled: "Cancelled",
  };
  return map[status] || (status?.replace(/_/g, " ") ?? "—");
}
