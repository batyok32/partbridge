"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { readSavedBuyerZip, writeSavedBuyerZip } from "@/lib/browse-prefs";
import { lookupUsZip } from "@/lib/us-zip-lookup";

const LABELS = { standard: "Standard", next_day: "Next day", pickup: "Pickup" };

const inputStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "7px 10px",
  fontSize: 13,
  outline: "none",
  fontFamily: "var(--ff-body)",
  width: "100%",
};

function formatVehicleLine(item) {
  const y = item.vehicle_year;
  const mk = (item.vehicle_make || "").trim();
  const md = (item.vehicle_model || "").trim();
  const ymm = [y, mk, md].filter(Boolean).join(" ");
  return ymm || "Vehicle";
}

export default function CartPage() {
  const { user, loading } = useAuth();
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [deliveryZip, setDeliveryZip] = useState("");
  const [deliveryZipHint, setDeliveryZipHint] = useState("");
  const [zipInitialized, setZipInitialized] = useState(false);
  const coercingPickupRef = useRef(false);

  const { partsTotal, shipTotal, grandTotal } = useMemo(() => {
    let p = 0, s = 0;
    for (const i of items) {
      const q = Number(i.quantity || 1);
      p += Number(i.vehicle_part_price || 0) * q;
      s += Number(i.shipping_quoted_usd || 0);
    }
    return { partsTotal: p, shipTotal: s, grandTotal: p + s };
  }, [items]);

  const hasUnavailableLine = useMemo(
    () => items.some((i) => (i.listing_state_effective || i.listing_state) !== "buy_now"),
    [items],
  );

  /** True when any line uses shipped delivery (not local pickup). */
  const needsDeliveryZip = useMemo(
    () => items.some((i) => i.shipping_mode !== "pickup"),
    [items],
  );

  async function load() {
    const data = await apiFetch("/cart/");
    setItems(Array.isArray(data) ? data : []);
  }

  useEffect(() => {
    if (loading || !user) return;
    void (async () => {
      try {
        await load();
      } catch (e) {
        if (e instanceof ApiError) toast.error(e.message);
      }
    })();
  }, [loading, user, toast]);

  useEffect(() => {
    if (items.length === 0) {
      setZipInitialized(false);
      return;
    }
    if (zipInitialized) return;
    if (!needsDeliveryZip) {
      setZipInitialized(true);
      return;
    }
    const lineZip = items.find((i) => i.shipping_mode !== "pickup" && i.buyer_zip_snapshot)?.buyer_zip_snapshot?.trim();
    const saved = readSavedBuyerZip();
    setDeliveryZip(lineZip || saved || "");
    setZipInitialized(true);
  }, [items, needsDeliveryZip, zipInitialized]);

  useEffect(() => {
    if (!items.length || coercingPickupRef.current) return;
    const bad = items.find((i) => i.shipping_mode === "pickup" && !i.pickup_allowed);
    if (!bad) return;
    coercingPickupRef.current = true;
    void (async () => {
      setBusy(true);
      try {
        const z = (bad.buyer_zip_snapshot || deliveryZip || readSavedBuyerZip() || "").trim();
        await apiFetch(`/cart/${bad.id}/`, {
          method: "PATCH",
          body: JSON.stringify({ shipping_mode: "standard", buyer_zip: z }),
        });
        await load();
        setZipInitialized(false);
      } catch (e) {
        if (e instanceof ApiError) toast.error(e.message);
      } finally {
        coercingPickupRef.current = false;
        setBusy(false);
      }
    })();
  }, [items, toast, deliveryZip]);

  async function removeItem(id) {
    setBusy(true);
    try {
      await apiFetch(`/cart/${id}/`, { method: "DELETE" });
      await load();
    } finally {
      setBusy(false);
    }
  }

  const updateLine = useCallback(
    async (id, patch) => {
      setBusy(true);
      try {
        await apiFetch(`/cart/${id}/`, { method: "PATCH", body: JSON.stringify(patch) });
        await load();
      } catch (e) {
        if (e instanceof ApiError) toast.error(e.message);
      } finally {
        setBusy(false);
      }
    },
    [toast],
  );

  async function applyDeliveryZipToLines() {
    const z = deliveryZip.trim();
    writeSavedBuyerZip(z);
    if (!items.length) return;
    for (const i of items) {
      if (i.pickup_allowed) continue;
      if ((i.buyer_zip_snapshot || "").trim() === z) continue;
      await updateLine(i.id, { shipping_mode: i.shipping_mode, buyer_zip: z });
    }
  }

  async function refreshDeliveryZipHint() {
    const digits = deliveryZip.replace(/\D/g, "").slice(0, 5);
    if (digits.length !== 5) {
      setDeliveryZipHint("");
      return;
    }
    try {
      const d = await lookupUsZip(digits);
      if (d?.city && d?.state) setDeliveryZipHint(`${d.city}, ${d.state}`);
      else setDeliveryZipHint("");
    } catch {
      setDeliveryZipHint("");
    }
  }

  async function onDeliveryZipBlur() {
    await applyDeliveryZipToLines();
    await refreshDeliveryZipHint();
  }

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading cart…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />

      <div className="relative z-10">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="section-label mb-1">Shopping</p>
            <h1 className="heading-display text-2xl">Your Cart</h1>
          </div>
          <Link
            href="/browse"
            style={{ fontSize: 13, fontWeight: 500, color: "var(--primary)", fontFamily: "var(--ff-body)", textDecoration: "none" }}
            onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
            onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}
          >
            ← Continue browsing
          </Link>
        </div>

        {items.length === 0 ? (
          <div className="mt-8 text-center py-16"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)" }}>
            <p style={{ fontSize: 32, marginBottom: 12 }}>🛒</p>
            <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Your cart is empty.</p>
            <Link href="/browse" className="btn-forge inline-flex mt-4" style={{ padding: "10px 24px", fontSize: 14 }}>
              Browse parts
            </Link>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {items.map((i) => {
                const pickupOffered = Boolean(i.pickup_allowed);
                const shipModes = pickupOffered
                  ? ["standard", "next_day", "pickup"]
                  : ["standard", "next_day"];
                return (
                  <div
                    key={i.id}
                    style={{
                      background: "var(--bg-surface)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-lg)",
                      padding: "14px",
                    }}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                          {i.vehicle_part_label}
                        </p>
                        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                          {formatVehicleLine(i)}
                          {i.vehicle_vin ? (
                            <>
                              <span className="hidden sm:inline"> · </span>
                              <span className="block sm:inline">VIN {i.vehicle_vin}</span>
                            </>
                          ) : null}
                        </p>
                        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                          <span className="price-mono" style={{ color: "var(--primary-bright)", fontSize: 13 }}>
                            ${i.vehicle_part_price}
                          </span>
                          {" × "}{i.quantity}
                          {(i.listing_state_effective || i.listing_state) !== "buy_now" && (
                            <span style={{ color: "#f87171", fontWeight: 600 }}> · not available</span>
                          )}
                        </p>
                        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                          Shipping ({LABELS[i.shipping_mode] || i.shipping_mode}):{" "}
                          {Number(i.shipping_quoted_usd) === 0 ? "Free" : `$${Number(i.shipping_quoted_usd).toFixed(2)}`}
                        </p>
                        {pickupOffered && i.pickup_zip ? (
                          <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
                            Pickup offered near ZIP {i.pickup_zip}
                          </p>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void removeItem(i.id)}
                        style={{
                          borderRadius: "var(--radius-sm)",
                          padding: "4px 10px",
                          fontSize: 12,
                          fontWeight: 500,
                          fontFamily: "var(--ff-display)",
                          background: "transparent",
                          border: "1px solid rgba(239,68,68,0.25)",
                          color: "#f87171",
                          cursor: "pointer",
                          transition: "all 0.12s",
                          opacity: busy ? 0.5 : 1,
                        }}
                        onMouseEnter={e => { if (!busy) e.currentTarget.style.background = "rgba(239,68,68,0.08)"; }}
                        onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
                      >
                        Remove
                      </button>
                    </div>

                    <div className="mt-2 flex flex-wrap gap-2">
                      {shipModes.map((mode) => (
                        <label
                          key={mode}
                          style={{
                            display: "flex", alignItems: "center", gap: 6,
                            borderRadius: "var(--radius-md)", padding: "4px 10px",
                            fontSize: 11, fontWeight: 600, fontFamily: "var(--ff-display)",
                            cursor: "pointer", transition: "all 0.12s",
                            border: i.shipping_mode === mode ? "1px solid rgba(255,92,26,0.4)" : "1px solid var(--border)",
                            background: i.shipping_mode === mode ? "rgba(255,92,26,0.08)" : "var(--bg-elevated)",
                            color: i.shipping_mode === mode ? "var(--primary-bright)" : "var(--text-secondary)",
                          }}
                        >
                          <input
                            type="radio"
                            name={`ship-${i.id}`}
                            className="sr-only"
                            checked={i.shipping_mode === mode}
                            onChange={() => void updateLine(i.id, {
                              shipping_mode: mode,
                              buyer_zip: mode === "pickup"
                                ? ""
                                : (i.buyer_zip_snapshot || deliveryZip || "").trim(),
                            })}
                          />
                          {LABELS[mode]}
                        </label>
                      ))}
                    </div>

                    {i.shipping_mode === "pickup" && (
                      <p className="mt-2 text-xs font-semibold" style={{ color: "var(--text-secondary)", fontFamily: "var(--ff-display)" }}>
                        Local pickup — coordinate with the seller after purchase.
                      </p>
                    )}

                    <textarea
                      key={`notes-${i.id}-${i.buyer_notes ?? ""}`}
                      defaultValue={i.buyer_notes || ""}
                      onBlur={(e) => void updateLine(i.id, { buyer_notes: e.target.value.trim() })}
                      rows={2}
                      placeholder="Note for seller (side, trim, etc.)"
                      style={{
                        marginTop: 8, width: "100%", resize: "none",
                        background: "var(--bg-elevated)", border: "1px solid var(--border)",
                        borderRadius: "var(--radius-md)", padding: "7px 10px",
                        fontSize: 12, color: "var(--text-primary)", outline: "none",
                        fontFamily: "var(--ff-body)",
                      }}
                    />
                  </div>
                );
              })}
            </div>

            {needsDeliveryZip && (
              <div
                className="mt-4 rounded-xl px-4 py-3"
                style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
              >
                <label className="block text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                  Delivery ZIP (shipping estimates)
                </label>
                <div className="flex flex-wrap items-end gap-2">
                  <input
                    value={deliveryZip}
                    onChange={(e) => {
                      setDeliveryZip(e.target.value);
                      if (e.target.value.replace(/\D/g, "").length < 5) setDeliveryZipHint("");
                    }}
                    onBlur={() => void onDeliveryZipBlur()}
                    placeholder="ZIP code"
                    disabled={busy}
                    style={{ ...inputStyle, maxWidth: 140 }}
                  />
                  <button
                    type="button"
                    disabled={busy}
                    className="rounded-lg px-3 py-2 text-xs font-semibold"
                    style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", color: "var(--text-primary)" }}
                    onClick={() => void onDeliveryZipBlur()}
                  >
                    Update shipping
                  </button>
                </div>
                {deliveryZipHint ? (
                  <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
                    Typical area for this ZIP: {deliveryZipHint}
                  </p>
                ) : null}
              </div>
            )}

            {hasUnavailableLine && (
              <p className="mt-3 text-xs font-medium" style={{ color: "#fbbf24" }}>
                Remove lines that are sold or unavailable before checkout.
              </p>
            )}

            <motion.div
              className="mt-6"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-xl)",
                padding: "20px",
              }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <p className="section-label mb-3">Estimated total</p>
              <div className="space-y-1 mb-4">
                <div className="flex justify-between text-sm">
                  <span style={{ color: "var(--text-muted)" }}>Parts</span>
                  <span className="price-mono">${partsTotal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: "var(--text-muted)" }}>Shipping</span>
                  <span className="price-mono">${shipTotal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between pt-2 text-base font-bold" style={{ borderTop: "1px solid var(--border)" }}>
                  <span style={{ fontFamily: "var(--ff-display)" }}>Subtotal</span>
                  <span className="price-mono" style={{ color: "var(--primary-bright)" }}>${grandTotal.toFixed(2)}</span>
                </div>
              </div>
              <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
                Next: confirm your ship-to address at checkout.
              </p>
              {hasUnavailableLine ? (
                <span
                  className="flex w-full justify-center rounded-lg py-3 text-sm font-semibold"
                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)" }}
                >
                  Fix cart issues to continue
                </span>
              ) : (
                <Link href="/cart/checkout" className="btn-forge flex w-full justify-center py-3 text-sm">
                  Continue to checkout →
                </Link>
              )}
            </motion.div>
          </>
        )}
      </div>
    </div>
  );
}
