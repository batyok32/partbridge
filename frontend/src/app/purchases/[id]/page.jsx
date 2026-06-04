"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

function capitalize(s) {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " ");
}

const STATUS_STYLES = {
  pending:   { background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.3)",   color: "#fbbf24" },
  confirmed: { background: "rgba(255,92,26,0.12)",  border: "1px solid rgba(255,92,26,0.25)",   color: "var(--primary)" },
  shipped:   { background: "rgba(52,211,153,0.10)", border: "1px solid rgba(52,211,153,0.3)",   color: "#34d399" },
  delivered: { background: "rgba(167,139,250,0.12)",border: "1px solid rgba(167,139,250,0.25)", color: "#a78bfa" },
  cancelled: { background: "rgba(239,68,68,0.12)",  border: "1px solid rgba(239,68,68,0.25)",   color: "#f87171" },
};

const DISPUTE_STYLES = {
  open:                { background: "rgba(251,191,36,0.1)", border: "1px solid rgba(251,191,36,0.3)", color: "#fbbf24" },
  under_review:        { background: "rgba(56,189,248,0.1)", border: "1px solid rgba(56,189,248,0.3)", color: "#38bdf8" },
  resolved_refund:     { background: "rgba(34,197,94,0.1)",  border: "1px solid rgba(34,197,94,0.3)",  color: "#4ade80" },
  resolved_return:     { background: "rgba(167,139,250,0.1)",border: "1px solid rgba(167,139,250,0.25)",color: "#a78bfa" },
  resolved_no_action:  { background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)" },
  closed:              { background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)" },
};

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || { background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)" };
  return (
    <span style={{ ...style, borderRadius: 999, padding: "3px 12px", fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)" }}>
      {capitalize(status)}
    </span>
  );
}

function Stars({ value, size = 16 }) {
  const n = Math.round(Number(value) || 0);
  return (
    <span style={{ display: "inline-flex", gap: 2 }}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ fontSize: size, color: i < n ? "#fbbf24" : "var(--border)", lineHeight: 1 }}>★</span>
      ))}
    </span>
  );
}

function StarRating({ value, onChange }) {
  const [hover, setHover] = useState(0);
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          onMouseEnter={() => setHover(n)}
          onMouseLeave={() => setHover(0)}
          style={{ background: "none", border: "none", cursor: "pointer", padding: 0, lineHeight: 1 }}
        >
          <span style={{ fontSize: 28, color: n <= (hover || value || 0) ? "#fbbf24" : "var(--border)" }}>★</span>
        </button>
      ))}
    </div>
  );
}

function trackingUrl(carrier, number) {
  if (!number) return null;
  const c = (carrier || "").toLowerCase();
  if (c.includes("ups"))   return `https://www.ups.com/track?tracknum=${number}`;
  if (c.includes("fedex")) return `https://www.fedex.com/fedextrack/?tracknumbers=${number}`;
  if (c.includes("usps"))  return `https://tools.usps.com/go/TrackConfirmAction?tLabels=${number}`;
  if (c.includes("dhl"))   return `https://www.dhl.com/us-en/home/tracking.html?tracking-id=${number}`;
  return null;
}

function generateReceiptHtml(order) {
  const addr = order.shipping_address_details;
  const addrLines = addr
    ? [addr.full_name, addr.line1, addr.line2, [addr.city, addr.state, addr.zip].filter(Boolean).join(" ")].filter(Boolean)
    : [];

  const itemRows = (order.order_items || []).map((oi) => {
    const title = oi.item_title || oi.item_snapshot?.title || `Item #${oi.item_id}`;
    return `<tr><td style="padding:8px 0;border-bottom:1px solid #eee;font-size:13px">${title}</td><td style="padding:8px 0;border-bottom:1px solid #eee;font-size:13px;text-align:right;white-space:nowrap">${formatMoney(oi.price_at_purchase)}</td></tr>`;
  }).join("");

  const taxRow = Number(order.tax) > 0
    ? `<tr><td style="padding:4px 0;font-size:13px;color:#666">Tax</td><td style="padding:4px 0;font-size:13px;color:#666;text-align:right">${formatMoney(order.tax)}</td></tr>`
    : "";

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Receipt – Order #${order.id} – Partbridge</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#111;max-width:520px;margin:0 auto;padding:40px 24px}
  .label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#888;margin-bottom:4px}
  @media print{body{padding:0}}
</style>
</head>
<body>
<div style="display:flex;align-items:center;gap:12px;margin-bottom:28px;padding-bottom:20px;border-bottom:2px solid #111">
  <div style="width:32px;height:32px;background:#ff5c1a;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:15px;flex-shrink:0">P</div>
  <div>
    <div style="font-weight:700;font-size:16px">Partbridge</div>
    <div style="font-size:11px;color:#888">Order Receipt</div>
  </div>
</div>

<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px">
  <div>
    <div class="label">Order number</div>
    <div style="font-size:20px;font-weight:700">#${order.id}</div>
    <div style="font-size:12px;color:#666;margin-top:3px">${order.placed_at ? new Date(order.placed_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }) : ""}</div>
  </div>
  <div style="text-align:right">
    <div class="label">Status</div>
    <div style="font-size:13px;font-weight:600;text-transform:capitalize">${(order.status || "").replace(/_/g, " ")}</div>
    ${order.payment ? `<div style="font-size:12px;color:#888;margin-top:2px">Payment: ${capitalize(order.payment.status)}</div>` : ""}
  </div>
</div>

${addrLines.length ? `<div style="margin-bottom:20px;padding:12px;background:#f8f8f8;border-radius:8px"><div class="label" style="margin-bottom:6px">Shipped to</div>${addrLines.map(l => `<div style="font-size:13px;line-height:1.7">${l}</div>`).join("")}</div>` : ""}

<table style="width:100%;border-collapse:collapse;margin-bottom:16px">
  <thead><tr><th style="text-align:left;padding:4px 0 8px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#888;border-bottom:2px solid #111">Item</th><th style="text-align:right;padding:4px 0 8px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#888;border-bottom:2px solid #111">Price</th></tr></thead>
  <tbody>${itemRows}</tbody>
</table>

<table style="width:100%;border-collapse:collapse">
  <tr><td style="padding:4px 0;font-size:13px;color:#666">Parts subtotal</td><td style="padding:4px 0;font-size:13px;color:#666;text-align:right">${formatMoney(order.subtotal)}</td></tr>
  <tr><td style="padding:4px 0;font-size:13px;color:#666">Shipping</td><td style="padding:4px 0;font-size:13px;color:#666;text-align:right">${formatMoney(order.shipping_cost)}</td></tr>
  ${taxRow}
  <tr style="border-top:2px solid #111"><td style="padding:10px 0 4px;font-size:15px;font-weight:700">Total</td><td style="padding:10px 0 4px;font-size:15px;font-weight:700;text-align:right">${formatMoney(order.total)}</td></tr>
</table>

<div style="margin-top:32px;padding-top:20px;border-top:1px solid #eee;font-size:11px;color:#888;text-align:center">
  <p>Thank you for your purchase on Partbridge.</p>
  <p style="margin-top:4px">For questions, open a dispute in your account at partbridge.com.</p>
</div>
</body>
</html>`;
}

export default function PurchaseDetailPage() {
  const { id: rawId } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reviewState, setReviewState] = useState({});
  const [reviewBusy, setReviewBusy] = useState(null);

  const id = Number(rawId);

  const load = useCallback(async () => {
    if (!Number.isFinite(id) || id < 1) return;
    const data = await apiFetch(`/orders/${id}/`);
    setOrder(data);
  }, [id]);

  useEffect(() => {
    if (authLoading || !user) return;
    void (async () => {
      setLoading(true);
      try {
        await load();
      } catch (e) {
        if (e instanceof ApiError) {
          toast.error(e.message);
          if (e.status === 403 || e.status === 404) router.replace("/purchases");
        }
        setOrder(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, user, load, router, toast, id]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=%2Fpurchases");
  }, [authLoading, user, router]);

  async function submitReview(orderItemId) {
    const state = reviewState[orderItemId] || {};
    const rating = state.rating ?? 5;
    setReviewBusy(orderItemId);
    try {
      await apiFetch(`/order-items/${orderItemId}/review/`, {
        method: "POST",
        body: JSON.stringify({ rating, body: state.body || "" }),
      });
      toast.success("Review saved — thank you.");
      await load();
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setReviewBusy(null);
    }
  }

  function handlePrintReceipt() {
    if (!order) return;
    const win = window.open("", "_blank", "width=620,height=820");
    if (!win) { toast.error("Pop-up blocked — please allow pop-ups and try again."); return; }
    win.document.write(generateReceiptHtml(order));
    win.document.close();
    win.focus();
    win.print();
  }

  if (authLoading || !user || loading) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Order not found.</p>
        <Link href="/purchases" className="btn-forge inline-flex mt-4">Back</Link>
      </div>
    );
  }

  const isDelivered = order.status === "delivered";
  const canDispute = ["confirmed", "shipped", "delivered"].includes(order.status);
  const addr = order.shipping_address_details;
  const addrText = addr
    ? [addr.line1, addr.city, `${addr.state} ${addr.zip}`].filter(Boolean).join(", ")
    : null;

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-12 space-y-4">
      <Link href="/purchases" className="text-sm" style={{ color: "var(--primary)" }}>← Purchases</Link>

      {/* Order header card */}
      <div className="rounded-xl p-5 space-y-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="section-label mb-0.5">Order #{order.id}</p>
            <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {order.placed_at ? new Date(order.placed_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }) : "—"}
            </p>
          </div>
          <StatusBadge status={order.status} />
        </div>

        {/* Financials */}
        <div className="grid sm:grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Parts</p>
            <p style={{ color: "var(--text-secondary)" }}>{formatMoney(order.subtotal)}</p>
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Shipping</p>
            <p style={{ color: "var(--text-secondary)" }}>{formatMoney(order.shipping_cost)}</p>
          </div>
          {Number(order.tax) > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Tax</p>
              <p style={{ color: "var(--text-secondary)" }}>{formatMoney(order.tax)}</p>
            </div>
          )}
          <div>
            <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Total</p>
            <p style={{ fontWeight: 700, color: "var(--text-primary)" }}>{formatMoney(order.total)}</p>
          </div>
          {order.payment && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Payment</p>
              <p style={{ color: "var(--text-secondary)" }}>{capitalize(order.payment.status)}</p>
            </div>
          )}
        </div>

        {/* Address */}
        {addrText && (
          <div>
            <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Ship to</p>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              {addr.full_name && <><strong style={{ color: "var(--text-primary)" }}>{addr.full_name}</strong><br /></>}
              {addrText}
            </p>
          </div>
        )}

        {/* Actions row */}
        <div className="flex flex-wrap gap-2 pt-1">
          <button
            type="button"
            onClick={handlePrintReceipt}
            style={{
              fontSize: 12, fontWeight: 600, padding: "7px 16px", borderRadius: 8,
              border: "1px solid var(--border)", background: "var(--bg-elevated)",
              color: "var(--text-secondary)", cursor: "pointer",
            }}
          >
            Download receipt
          </button>
        </div>
      </div>

      {/* Order items */}
      {(order.order_items || []).map((oi) => {
        const title = oi.item_title || oi.item_snapshot?.title || `Item #${oi.item_id}`;
        const snap = oi.item_snapshot || {};
        const shipping = oi.shipping;
        const review = oi.review;
        const revState = reviewState[oi.id] || {};
        const disputeStatus = oi.dispute_status;
        const hasActiveDispute = disputeStatus && !["resolved_refund", "resolved_return", "resolved_no_action", "closed"].includes(disputeStatus);
        const tUrl = trackingUrl(shipping?.carrier, shipping?.tracking_number);
        const conditionMap = { excellent: "Excellent", good: "Good", fair: "Fair", for_parts: "For parts" };
        const shippingModeMap = { standard: "Standard shipping", economy: "Economy shipping", pickup: "Local pickup" };

        return (
          <div key={oi.id} className="rounded-xl p-5 space-y-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            {/* Item row */}
            <div className="flex gap-3">
              <div style={{ width: 72, height: 72, borderRadius: 8, overflow: "hidden", flexShrink: 0, background: "var(--bg-elevated)" }}>
                {oi.item_photo_url ? (
                  <img src={oi.item_photo_url} alt={title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center" style={{ fontSize: 24 }}>📦</div>
                )}
              </div>
              <div className="flex-1 min-w-0">
                {oi.item_id ? (
                  <Link
                    href={`/browse/parts/${oi.item_id}`}
                    style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.3, textDecoration: "none", display: "block", marginBottom: 4 }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "var(--primary)")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
                  >
                    {title} ↗
                  </Link>
                ) : (
                  <p style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.3, marginBottom: 4 }}>
                    {title}
                  </p>
                )}

                {/* Badges row */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 }}>
                  {snap.condition && (
                    <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
                      {conditionMap[snap.condition] || snap.condition}
                    </span>
                  )}
                  {snap.category_name && (
                    <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
                      {snap.category_name}
                    </span>
                  )}
                  {snap.shipping_size && (
                    <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
                      {snap.shipping_size.toUpperCase()}
                    </span>
                  )}
                  {snap.shipping_mode && (
                    <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
                      {shippingModeMap[snap.shipping_mode] || snap.shipping_mode}
                    </span>
                  )}
                  {snap.bundle_name && (
                    <span style={{ fontSize: 10, fontWeight: 700, background: "var(--primary-muted)", border: "1px solid var(--primary-border-soft, var(--border))", borderRadius: 4, padding: "1px 6px", color: "var(--primary)" }}>
                      Bundle: {snap.bundle_name}
                    </span>
                  )}
                </div>

                <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)" }}>
                  {formatMoney(oi.price_at_purchase)}
                </p>
              </div>
            </div>

            {/* Selected options */}
            {oi.selected_options && Object.keys(oi.selected_options).length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {Object.entries(oi.selected_options).map(([k, v]) => (
                  <span key={k} style={{ fontSize: 11, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 5, padding: "2px 8px", color: "var(--text-secondary)" }}>
                    {k}: {v}
                  </span>
                ))}
              </div>
            )}

            {/* Seller */}
            {oi.seller_name && (
              <div>
                <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Seller</p>
                <Link
                  href={oi.seller_id ? `/sellers/${oi.seller_id}` : "#"}
                  style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", textDecoration: "none" }}
                >
                  {oi.seller_name}
                </Link>
              </div>
            )}

            {/* Shipping / tracking */}
            <div>
              <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Shipping</p>
              {shipping ? (
                <div className="space-y-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                  {shipping.method && <p>Method: {capitalize(shipping.method)}</p>}
                  {shipping.tracking_number ? (
                    <p>
                      Tracking:{" "}
                      <strong style={{ color: "var(--text-primary)" }}>{shipping.carrier && `${shipping.carrier} `}</strong>
                      {tUrl ? (
                        <a href={tUrl} target="_blank" rel="noopener noreferrer" style={{ color: "var(--primary)", fontWeight: 700 }}>
                          {shipping.tracking_number} ↗
                        </a>
                      ) : (
                        <strong style={{ color: "var(--text-primary)" }}>{shipping.tracking_number}</strong>
                      )}
                    </p>
                  ) : (
                    <p style={{ color: "var(--text-muted)" }}>Tracking will appear when the seller ships.</p>
                  )}
                  {shipping.estimated_days && <p style={{ color: "var(--text-muted)" }}>Est. {shipping.estimated_days} day{shipping.estimated_days !== 1 ? "s" : ""}</p>}
                  {shipping.is_delivered && (
                    <p style={{ color: "#4ade80", fontWeight: 600 }}>✓ Delivered</p>
                  )}
                </div>
              ) : (
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>Shipping details will appear once confirmed.</p>
              )}
            </div>

            {/* Dispute status indicator */}
            {disputeStatus && (
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ ...DISPUTE_STYLES[disputeStatus], borderRadius: 999, padding: "3px 10px", fontSize: 11, fontWeight: 600 }}>
                  Dispute: {capitalize(disputeStatus)}
                </span>
                <Link href={`/purchases/${order.id}/issue?item=${oi.id}`} style={{ fontSize: 12, color: "var(--primary)" }}>
                  View dispute →
                </Link>
              </div>
            )}

            {/* Open dispute link */}
            {canDispute && !disputeStatus && (
              <Link
                href={`/purchases/${order.id}/issue?item=${oi.id}`}
                style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textDecoration: "none", display: "inline-block" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "#f87171")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
              >
                Open dispute
              </Link>
            )}

            {/* Review — only for delivered orders */}
            {isDelivered && (
              <div className="rounded-lg p-3" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                  {review ? "Your review" : "Leave a review"}
                </p>
                {review ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <Stars value={review.rating} size={18} />
                    {review.body && (
                      <p className="text-sm" style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>"{review.body}"</p>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <StarRating
                      value={revState.rating ?? 5}
                      onChange={(r) => setReviewState((prev) => ({ ...prev, [oi.id]: { ...prev[oi.id], rating: r } }))}
                    />
                    <textarea
                      value={revState.body || ""}
                      onChange={(e) => setReviewState((prev) => ({ ...prev, [oi.id]: { ...prev[oi.id], body: e.target.value } }))}
                      rows={2}
                      placeholder="Optional comment…"
                      className="w-full rounded-md px-2 py-2 text-sm"
                      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)", resize: "vertical" }}
                    />
                    <button
                      type="button"
                      disabled={reviewBusy === oi.id}
                      className="btn-forge text-xs py-1.5 px-3"
                      onClick={() => void submitReview(oi.id)}
                    >
                      {reviewBusy === oi.id ? "Saving…" : "Submit review"}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
