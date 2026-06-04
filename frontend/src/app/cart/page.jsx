"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { useCart } from "@/context/cart-context";
import { ApiError, apiFetch, removeCartBundle, setCartBundleShippingMode, setCartItemShippingMode } from "@/lib/api";
import { STATE_TAX_RATES, deliveryTime, estimateShipping, estimateTax, isFreight } from "@/lib/shipping";

// ─── Formatting ────────────────────────────────────────────────────────────

function fmt(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

// ─── Item card ─────────────────────────────────────────────────────────────

function ItemCard({ ci, buyerState, removing, togglingMode, onRemove, onToggleMode }) {
  const item = ci.item_detail || {};
  const size = item.shipping_size || "medium";
  const mode = ci.shipping_mode || "standard";
  const isUnavailable = item.status && item.status !== "active";

  const shippingCost = buyerState
    ? estimateShipping(size, buyerState, mode)
    : null;
  const eta = deliveryTime(size, mode);

  const carLine = [item.vehicle_year, item.vehicle_make, item.vehicle_model]
    .filter(Boolean).join(" ");
  const genLabel = item.vehicle_generation_label;
  const options = Array.isArray(item.options) ? item.options : [];

  const isLarge = size === "large";
  const isXl = size === "xl";
  const isSmallMed = !isLarge && !isXl;

  return (
    <div style={{
      background: "var(--bg-surface)",
      border: isUnavailable ? "1px solid rgba(239,68,68,0.4)" : "1px solid var(--border)",
      borderRadius: "var(--radius-xl)",
      overflow: "hidden",
      opacity: isUnavailable ? 0.75 : 1,
    }}>
      {isUnavailable && (
        <div style={{ padding: "6px 14px", background: "rgba(239,68,68,0.1)", borderBottom: "1px solid rgba(239,68,68,0.2)", display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "#f87171" }}>
            No longer available — will be removed at checkout
          </span>
        </div>
      )}
      {/* Main row */}
      <div style={{ display: "flex", gap: 12, padding: "14px" }}>
        {/* Photo */}
        <Link href={`/browse/parts/${item.id}`} style={{ flexShrink: 0 }}>
          <div style={{ width: 72, height: 72, borderRadius: 10, overflow: "hidden", background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
            {item.primary_photo_url ? (
              <img src={item.primary_photo_url} alt={item.category_name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            ) : (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 22 }}>📦</div>
            )}
          </div>
        </Link>

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Category */}
          <Link href={`/browse/parts/${item.id}`} style={{ textDecoration: "none" }}>
            <p style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.2 }}>
              {item.category_name || "Part"}
            </p>
          </Link>

          {/* Car */}
          {carLine && (
            <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
              {carLine}{genLabel ? ` · ${genLabel}` : ""}
            </p>
          )}

          {/* Options */}
          {options.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 5 }}>
              {options.map((o) => (
                <span
                  key={o.id}
                  style={{
                    fontSize: 10, fontWeight: 600, padding: "2px 7px",
                    background: "var(--bg-elevated)", border: "1px solid var(--border)",
                    borderRadius: 4, color: "var(--text-secondary)",
                  }}
                >
                  {o.option_category_name}: {o.value}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Price + remove */}
        <div style={{ textAlign: "right", flexShrink: 0, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
            {fmt(item.price)}
          </p>
          <button
            type="button"
            onClick={() => onRemove(ci.id)}
            disabled={removing === ci.id}
            style={{ fontSize: 11, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline", padding: 0 }}
          >
            {removing === ci.id ? "Removing…" : "Remove"}
          </button>
        </div>
      </div>

      {/* Shipping section */}
      <div style={{ borderTop: "1px solid var(--border)", padding: "10px 14px", background: "var(--bg-elevated)" }}>
        {isSmallMed && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" }}>
                Carrier shipping
              </span>
              <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 6 }}>
                {eta}
              </span>
            </div>
            <div style={{ textAlign: "right" }}>
              {buyerState ? (
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
                  ~{fmt(shippingCost)}
                </span>
              ) : (
                <span style={{ fontSize: 11, color: "var(--text-muted)" }}>enter state →</span>
              )}
            </div>
          </div>
        )}

        {isSmallMed && (
          <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4, lineHeight: 1.4 }}>
            Approximate carrier rate. Any difference is refunded or invoiced after shipment.
          </p>
        )}

        {isLarge && (
          <div>
            <p style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>Shipping method</p>
            <div style={{ display: "flex", gap: 6 }}>
              {/* Standard */}
              <button
                type="button"
                onClick={() => mode !== "standard" && onToggleMode(ci.id, "standard")}
                disabled={togglingMode === ci.id}
                style={{
                  flex: 1, padding: "7px 8px", borderRadius: 8, cursor: "pointer",
                  border: mode === "standard" ? "2px solid var(--primary)" : "1px solid var(--border)",
                  background: mode === "standard" ? "var(--primary-muted)" : "var(--bg-surface)",
                  textAlign: "left",
                }}
              >
                <p style={{ fontSize: 11, fontWeight: 700, color: mode === "standard" ? "var(--primary)" : "var(--text-primary)" }}>
                  Fast freight
                </p>
                <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 1 }}>5–14 days</p>
                {buyerState ? (
                  <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)", marginTop: 2 }}>
                    {fmt(estimateShipping(size, buyerState, "standard"))}
                  </p>
                ) : (
                  <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>enter state</p>
                )}
              </button>

              {/* Economy */}
              <button
                type="button"
                onClick={() => mode !== "economy" && onToggleMode(ci.id, "economy")}
                disabled={togglingMode === ci.id}
                style={{
                  flex: 1, padding: "7px 8px", borderRadius: 8, cursor: "pointer",
                  border: mode === "economy" ? "2px solid var(--primary)" : "1px solid var(--border)",
                  background: mode === "economy" ? "var(--primary-muted)" : "var(--bg-surface)",
                  textAlign: "left",
                }}
              >
                <p style={{ fontSize: 11, fontWeight: 700, color: mode === "economy" ? "var(--primary)" : "var(--text-primary)" }}>
                  Economy
                </p>
                <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 1 }}>~30 days</p>
                <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)", marginTop: 2 }}>{fmt(100)}</p>
              </button>
            </div>
          </div>
        )}

        {isXl && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" }}>Economy freight</span>
              <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 6 }}>~30 days</span>
            </div>
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>{fmt(150)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Bundle card ───────────────────────────────────────────────────────────

function BundleCard({ cb, buyerState, removing, togglingMode, onRemove, onToggleMode }) {
  const bundle = cb.bundle_detail || {};
  const items = bundle.items || [];
  // Use ?? so a fixed_price of 0 is respected (not treated as falsy)
  const discountedPrice = bundle.fixed_price ?? bundle.discounted_price;
  const mode = cb.shipping_mode || "standard";
  const hasLarge = items.some((bi) => (bi.item_detail?.shipping_size) === "large");

  return (
    <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", overflow: "hidden" }}>
      <div style={{ padding: "12px 14px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid var(--border)", background: "var(--bg-elevated)" }}>
        <div>
          <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{bundle.name}</p>
          <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
            {bundle.bundle_type === "discount" ? `${bundle.discount_pct || 0}% bundle discount` : "Assembly bundle"} · {items.length} item{items.length !== 1 ? "s" : ""}
          </p>
        </div>
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          {bundle.total_price && bundle.discounted_price && bundle.total_price !== bundle.discounted_price && (
            <p style={{ fontSize: 11, color: "var(--text-muted)", textDecoration: "line-through" }}>{fmt(bundle.total_price)}</p>
          )}
          <p style={{ fontSize: 15, fontWeight: 700, color: "var(--primary-bright)", fontFamily: "var(--ff-display)" }}>
            {fmt(discountedPrice ?? bundle.total_price ?? 0)}
          </p>
          <button
            type="button"
            onClick={() => onRemove(cb.bundle)}
            disabled={removing === cb.bundle}
            style={{ marginTop: 4, fontSize: 11, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}
          >
            {removing === cb.bundle ? "Removing…" : "Remove bundle"}
          </button>
        </div>
      </div>
      <div style={{ padding: "8px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((bi) => {
          const it = bi.item_detail || {};
          return (
            <div key={bi.id} style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <div style={{ width: 40, height: 40, borderRadius: 6, overflow: "hidden", flexShrink: 0, background: "var(--bg-elevated)" }}>
                {it.primary_photo_url ? (
                  <img src={it.primary_photo_url} alt={it.category_name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                ) : (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 14 }}>📦</div>
                )}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {it.category_name || it.title}
                </p>
                {(it.options || []).map((o) => (
                  <span key={o.id} style={{ fontSize: 10, color: "var(--text-muted)", marginRight: 6 }}>
                    {o.option_category_name}: {o.value}
                  </span>
                ))}
              </div>
              <p style={{ fontSize: 12, color: "var(--text-muted)", flexShrink: 0 }}>{fmt(it.price)}</p>
            </div>
          );
        })}
      </div>

      {hasLarge && (
        <div style={{ borderTop: "1px solid var(--border)", padding: "10px 14px", background: "var(--bg-elevated)" }}>
          <p style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>Freight shipping method</p>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              type="button"
              onClick={() => mode !== "standard" && onToggleMode(cb.bundle, "standard")}
              disabled={togglingMode === cb.bundle}
              style={{
                flex: 1, padding: "7px 8px", borderRadius: 8, cursor: "pointer",
                border: mode === "standard" ? "2px solid var(--primary)" : "1px solid var(--border)",
                background: mode === "standard" ? "var(--primary-muted)" : "var(--bg-surface)",
                textAlign: "left",
              }}
            >
              <p style={{ fontSize: 11, fontWeight: 700, color: mode === "standard" ? "var(--primary)" : "var(--text-primary)" }}>Fast freight</p>
              <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 1 }}>5–14 days</p>
              {buyerState ? (
                <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)", marginTop: 2 }}>
                  {fmt(items.reduce((s, bi) => s + estimateShipping(bi.item_detail?.shipping_size || "medium", buyerState, "standard"), 0))}
                </p>
              ) : (
                <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>enter state</p>
              )}
            </button>
            <button
              type="button"
              onClick={() => mode !== "economy" && onToggleMode(cb.bundle, "economy")}
              disabled={togglingMode === cb.bundle}
              style={{
                flex: 1, padding: "7px 8px", borderRadius: 8, cursor: "pointer",
                border: mode === "economy" ? "2px solid var(--primary)" : "1px solid var(--border)",
                background: mode === "economy" ? "var(--primary-muted)" : "var(--bg-surface)",
                textAlign: "left",
              }}
            >
              <p style={{ fontSize: 11, fontWeight: 700, color: mode === "economy" ? "var(--primary)" : "var(--text-primary)" }}>Economy</p>
              <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 1 }}>~30 days</p>
              {buyerState ? (
                <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)", marginTop: 2 }}>
                  {fmt(items.reduce((s, bi) => s + estimateShipping(bi.item_detail?.shipping_size || "medium", buyerState, "economy"), 0))}
                </p>
              ) : (
                <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>enter state</p>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────

export default function CartPage() {
  const { user, loading } = useAuth();
  const toast = useToast();
  const cart = useCart();

  const [buyerState, setBuyerState] = useState("");
  const [removing, setRemoving] = useState(null);
  const [togglingMode, setTogglingMode] = useState(null);

  // Load saved state from localStorage, then try default address
  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("cart_buyer_state") : null;
    if (saved) { setBuyerState(saved); return; }
    if (!user) return;
    apiFetch("/shipping-addresses/")
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        const def = list.find((a) => a.is_default) || list[0];
        if (def?.state) setBuyerState(def.state.toUpperCase().slice(0, 2));
      })
      .catch(() => {});
  }, [user]);

  function handleStateChange(val) {
    const s = val.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 2);
    setBuyerState(s);
    if (typeof window !== "undefined") localStorage.setItem("cart_buyer_state", s);
  }

  useEffect(() => {
    if (!loading && user) void cart.refresh();
  }, [loading, user]);

  async function removeItem(cartItemId) {
    setRemoving(cartItemId);
    try {
      await apiFetch(`/cart/${cartItemId}/`, { method: "DELETE" });
      await cart.refresh();
      toast.success("Removed from cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setRemoving(null);
    }
  }

  async function removeBundle(bundleId) {
    setRemoving(bundleId);
    try {
      await removeCartBundle(bundleId);
      await cart.refresh();
      toast.success("Bundle removed from cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setRemoving(null);
    }
  }

  async function removeSoldItems() {
    const sold = cartItems.filter((ci) => ci.item_detail?.status && ci.item_detail?.status !== "active");
    if (!sold.length) return;
    setRemoving("__sold__");
    try {
      await Promise.all(sold.map((ci) => apiFetch(`/cart/${ci.id}/`, { method: "DELETE" }).catch(() => {})));
      await cart.refresh();
      toast.success(`Removed ${sold.length} unavailable item${sold.length !== 1 ? "s" : ""} from your cart.`);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setRemoving(null);
    }
  }

  async function toggleMode(cartItemId, mode) {
    setTogglingMode(cartItemId);
    try {
      await setCartItemShippingMode(cartItemId, mode);
      await cart.refresh();
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setTogglingMode(null);
    }
  }

  async function toggleBundleMode(bundleId, mode) {
    setTogglingMode(bundleId);
    try {
      await setCartBundleShippingMode(bundleId, mode);
      await cart.refresh();
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setTogglingMode(null);
    }
  }

  const { items: cartItems, bundles: cartBundles } = cart.cartData;

  const subtotal = useMemo(() => {
    const itemsTotal = cartItems
      .filter((ci) => !ci.item_detail?.status || ci.item_detail?.status === "active")
      .reduce((s, ci) => s + Number(ci.item_detail?.price || 0), 0);
    const bundlesTotal = cartBundles.reduce((s, cb) => {
      const b = cb.bundle_detail || {};
      // Use ?? so a bundle with fixed_price 0 isn't treated as falsy
      return s + Number(b.fixed_price ?? b.discounted_price ?? b.total_price ?? 0);
    }, 0);
    return itemsTotal + bundlesTotal;
  }, [cartItems, cartBundles]);

  const shippingEstimate = useMemo(() => {
    if (!buyerState) return null;
    const itemsShipping = cartItems
      .filter((ci) => !ci.item_detail?.status || ci.item_detail?.status === "active")
      .reduce((s, ci) => {
        const size = ci.item_detail?.shipping_size || "medium";
        return s + estimateShipping(size, buyerState, ci.shipping_mode || "standard");
      }, 0);
    const bundlesShipping = cartBundles.reduce((s, cb) => {
      const items = cb.bundle_detail?.items || [];
      const mode = cb.shipping_mode || "standard";
      return s + items.reduce((bs, bi) => bs + estimateShipping(bi.item_detail?.shipping_size || "medium", buyerState, mode), 0);
    }, 0);
    return itemsShipping + bundlesShipping;
  }, [cartItems, cartBundles, buyerState]);

  const taxEstimate = useMemo(() => {
    if (!buyerState || buyerState.length !== 2) return null;
    return estimateTax(subtotal, buyerState);
  }, [subtotal, buyerState]);

  const isEmpty = cartItems.length === 0 && cartBundles.length === 0;

  if (loading) {
    return <div className="mx-auto max-w-2xl px-6 py-16"><p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</p></div>;
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16 text-center">
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Sign in to view your cart.</p>
        <Link href="/login" style={{ color: "var(--primary)", fontSize: 13, marginTop: 8, display: "inline-block" }}>Sign in →</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-10">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="relative z-10">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <p className="section-label mb-1">Shopping</p>
            <h1 className="heading-display text-2xl">Cart</h1>
          </div>

          {/* State input for shipping estimates */}
          {!isEmpty && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
              <label style={{ fontSize: 11, color: "var(--text-muted)", whiteSpace: "nowrap" }}>State (for estimates)</label>
              <input
                value={buyerState}
                onChange={(e) => handleStateChange(e.target.value)}
                maxLength={2}
                placeholder="WA"
                style={{
                  width: 44, padding: "5px 7px", fontSize: 12, fontWeight: 700,
                  textTransform: "uppercase", textAlign: "center",
                  background: "var(--bg-elevated)", border: "1px solid var(--border)",
                  borderRadius: 6, color: "var(--text-primary)", outline: "none",
                  fontFamily: "var(--ff-body)",
                }}
              />
            </div>
          )}
        </div>

        {isEmpty ? (
          <div style={{ textAlign: "center", padding: "48px 0", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)" }}>
            <p style={{ fontSize: 32, marginBottom: 10 }}>🛒</p>
            <p style={{ color: "var(--text-muted)", fontSize: 14, marginBottom: 16 }}>Your cart is empty.</p>
            <Link href="/browse" className="btn-forge inline-flex" style={{ padding: "10px 24px", fontSize: 14 }}>Browse parts</Link>
          </div>
        ) : (
          <>
            {(() => {
              const soldCount = cartItems.filter((ci) => ci.item_detail?.status && ci.item_detail?.status !== "active").length;
              return soldCount > 0 ? (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12, padding: "10px 14px", borderRadius: 10, background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)" }}>
                  <p style={{ fontSize: 13, color: "#f87171", fontWeight: 600 }}>
                    {soldCount} item{soldCount !== 1 ? "s are" : " is"} no longer available
                  </p>
                  <button
                    type="button"
                    disabled={removing === "__sold__"}
                    onClick={removeSoldItems}
                    style={{ fontSize: 12, fontWeight: 700, padding: "5px 12px", borderRadius: 7, border: "1px solid rgba(239,68,68,0.4)", background: "rgba(239,68,68,0.1)", color: "#f87171", cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0 }}
                  >
                    {removing === "__sold__" ? "Removing…" : "Remove all"}
                  </button>
                </div>
              ) : null;
            })()}
            <div className="space-y-3 mb-6">
              {cartBundles.map((cb) => (
                <BundleCard
                  key={`bundle-${cb.id}`}
                  cb={cb}
                  buyerState={buyerState.length === 2 ? buyerState : null}
                  removing={removing}
                  togglingMode={togglingMode}
                  onRemove={removeBundle}
                  onToggleMode={toggleBundleMode}
                />
              ))}
              {cartItems.map((ci) => (
                <ItemCard
                  key={`item-${ci.id}`}
                  ci={ci}
                  buyerState={buyerState.length === 2 ? buyerState : null}
                  removing={removing}
                  togglingMode={togglingMode}
                  onRemove={removeItem}
                  onToggleMode={toggleMode}
                />
              ))}
            </div>

            {/* Summary */}
            <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 13, color: "var(--text-secondary)" }}>
                <span>Parts subtotal</span>
                <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>{fmt(subtotal)}</span>
              </div>
              {shippingEstimate !== null && (
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 13, color: "var(--text-secondary)" }}>
                  <span>Shipping estimate</span>
                  <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>~{fmt(shippingEstimate)}</span>
                </div>
              )}
              {taxEstimate !== null && taxEstimate > 0 && (
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 13, color: "var(--text-secondary)" }}>
                  <span>Tax estimate ({((STATE_TAX_RATES[buyerState] || 0) * 100).toFixed(2).replace(/\.?0+$/, "")}%)</span>
                  <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>~{fmt(taxEstimate)}</span>
                </div>
              )}
              <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6, marginBottom: 14 }}>
                {buyerState.length === 2
                  ? "Estimates based on destination state. Final totals confirmed at checkout."
                  : "Enter your state above to see shipping and tax estimates."}
              </p>
              <Link
                href="/cart/checkout"
                className="btn-forge w-full"
                style={{ display: "flex", justifyContent: "center", padding: "12px 0", fontSize: 14 }}
              >
                Proceed to checkout →
              </Link>
            </div>
          </>
        )}
      </motion.div>
    </div>
  );
}
