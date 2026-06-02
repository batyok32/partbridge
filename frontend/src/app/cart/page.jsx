"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

function sizeLabel(s) {
  return { small: "Small", medium: "Medium", large: "Large", xl: "Extra Large" }[s] || s || "—";
}

export default function CartPage() {
  const { user, loading } = useAuth();
  const toast = useToast();
  const [cartItems, setCartItems] = useState([]);
  const [removing, setRemoving] = useState(null);

  async function load() {
    const data = await apiFetch("/cart/");
    setCartItems(Array.isArray(data) ? data : []);
  }

  useEffect(() => {
    if (loading || !user) return;
    void (async () => {
      try { await load(); } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    })();
  }, [loading, user, toast]);

  async function removeItem(cartItemId) {
    setRemoving(cartItemId);
    try {
      await apiFetch(`/cart/${cartItemId}/`, { method: "DELETE" });
      setCartItems((prev) => prev.filter((ci) => ci.id !== cartItemId));
      toast.success("Removed from cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setRemoving(null);
    }
  }

  const subtotal = useMemo(() =>
    cartItems.reduce((sum, ci) => sum + Number(ci.item_detail?.price || 0), 0),
    [cartItems]
  );

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
        <div className="mb-6">
          <p className="section-label mb-1">Shopping</p>
          <h1 className="heading-display text-2xl">Cart</h1>
        </div>

        {cartItems.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 0", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)" }}>
            <p style={{ fontSize: 32, marginBottom: 10 }}>🛒</p>
            <p style={{ color: "var(--text-muted)", fontSize: 14, marginBottom: 16 }}>Your cart is empty.</p>
            <Link href="/browse" className="btn-forge inline-flex" style={{ padding: "10px 24px", fontSize: 14 }}>Browse parts</Link>
          </div>
        ) : (
          <>
            <div className="space-y-3 mb-6">
              {cartItems.map((ci) => {
                const item = ci.item_detail || {};
                const vehicleLine = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean).join(" ");
                return (
                  <div
                    key={ci.id}
                    style={{
                      display: "flex", gap: 12, background: "var(--bg-surface)",
                      border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px",
                    }}
                  >
                    {/* Photo */}
                    <div style={{ width: 64, height: 64, borderRadius: 8, overflow: "hidden", flexShrink: 0, background: "var(--bg-elevated)" }}>
                      {item.primary_photo_url ? (
                        <img src={item.primary_photo_url} alt={item.title} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      ) : (
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 20 }}>📦</div>
                      )}
                    </div>

                    {/* Details */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Link
                        href={`/browse/parts/${item.id}`}
                        style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", textDecoration: "none", display: "block", lineHeight: 1.3 }}
                      >
                        {item.title}
                      </Link>
                      {vehicleLine && <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{vehicleLine}</p>}
                      <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                        {item.category_name && (
                          <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-secondary)" }}>
                            {item.category_name}
                          </span>
                        )}
                        {item.shipping_size && (
                          <span style={{ fontSize: 10, color: "var(--text-muted)" }}>📦 {sizeLabel(item.shipping_size)}</span>
                        )}
                      </div>
                    </div>

                    {/* Price + remove */}
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                      <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                        {formatMoney(item.price)}
                      </p>
                      <button
                        type="button"
                        onClick={() => removeItem(ci.id)}
                        disabled={removing === ci.id}
                        style={{ marginTop: 6, fontSize: 11, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}
                      >
                        {removing === ci.id ? "Removing…" : "Remove"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Summary */}
            <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 13, color: "var(--text-secondary)" }}>
                <span>Subtotal ({cartItems.length} item{cartItems.length !== 1 ? "s" : ""})</span>
                <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>{formatMoney(subtotal)}</span>
              </div>
              <p style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 14 }}>
                Shipping cost is calculated at checkout.
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
