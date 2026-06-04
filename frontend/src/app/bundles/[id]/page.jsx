"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, addBundleToCart, getBundle } from "@/lib/api";
import { formatShippingEstimate } from "@/lib/shipping-rates";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

export default function BundleDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    const n = Number(id);
    if (!Number.isFinite(n) || n < 1) { setNotFound(true); setLoading(false); return; }
    let cancelled = false;
    getBundle(n)
      .then((data) => { if (!cancelled) setBundle(data); })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else toast.error(e?.message || "Could not load bundle.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id, toast]);

  async function handleAddAll() {
    if (!user) { window.location.href = `/login?next=/bundles/${id}`; return; }
    setAdding(true);
    try {
      const result = await addBundleToCart(Number(id));
      toast.success(`${result.added} item${result.added !== 1 ? "s" : ""} added to cart.`);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setAdding(false);
    }
  }

  if (loading) {
    return <div className="mx-auto max-w-2xl px-6 py-16"><p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</p></div>;
  }

  if (notFound || !bundle) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16 text-center">
        <p style={{ fontSize: 32, marginBottom: 8 }}>📦</p>
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Bundle not found.</p>
        <Link href="/search" style={{ color: "var(--primary)", fontSize: 13, marginTop: 12, display: "inline-block" }}>← Browse parts</Link>
      </div>
    );
  }

  const vehicleName = [bundle.vehicle_year, bundle.vehicle_make, bundle.vehicle_model].filter(Boolean).join(" ");
  const hasDiscount = bundle.discount_pct && Number(bundle.discount_pct) > 0;
  const isAssembly = bundle.bundle_type === "assembly";
  const items = (bundle.items || []).map((bi) => bi.item_detail).filter(Boolean);

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-10">
      <Link href="/search" style={{ color: "var(--text-muted)", fontSize: 12, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 20 }}>
        ← Back to search
      </Link>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="space-y-5">

        {/* Hero photo */}
        {bundle.primary_photo_url && (
          <div className="rounded-2xl overflow-hidden" style={{ border: "1px solid var(--border)", aspectRatio: "16/9" }}>
            <img src={bundle.primary_photo_url} alt={bundle.name} className="w-full h-full object-cover" />
          </div>
        )}

        {/* Title */}
        <div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
            <span style={{
              fontSize: 10, fontWeight: 700, fontFamily: "var(--ff-display)",
              background: isAssembly ? "rgba(139,92,246,0.15)" : "rgba(255,92,26,0.12)",
              color: isAssembly ? "#a78bfa" : "var(--primary)",
              border: isAssembly ? "1px solid rgba(139,92,246,0.3)" : "1px solid rgba(255,92,26,0.25)",
              borderRadius: 5, padding: "2px 8px",
            }}>
              {isAssembly ? "Assembly" : "Kit"}
            </span>
            {bundle.bundle_category_name && (
              <span style={{ fontSize: 10, fontWeight: 600, color: "var(--text-muted)", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 5, padding: "2px 8px" }}>
                {bundle.bundle_category_name}
              </span>
            )}
          </div>

          <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.25 }}>
            {bundle.name}
          </h1>
          {vehicleName && <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>From: {vehicleName}</p>}
          {bundle.vehicle_generation_label && (
            <p style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--ff-mono)" }}>{bundle.vehicle_generation_label}</p>
          )}

          {/* Pricing */}
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 10 }}>
            <span style={{ fontSize: 26, fontWeight: 700, color: "var(--primary)", fontFamily: "var(--ff-display)" }}>
              {formatMoney(bundle.discounted_price)}
            </span>
            {hasDiscount && (
              <>
                <span style={{ fontSize: 15, color: "var(--text-muted)", textDecoration: "line-through" }}>
                  {formatMoney(bundle.total_price)}
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 700, background: "rgba(74,222,128,0.12)",
                  color: "#4ade80", border: "1px solid rgba(74,222,128,0.3)",
                  borderRadius: 5, padding: "2px 8px",
                }}>
                  {Number(bundle.discount_pct)}% off
                </span>
              </>
            )}
          </div>
        </div>

        {/* Add to cart */}
        <button
          type="button"
          onClick={handleAddAll}
          disabled={adding}
          style={{
            width: "100%", padding: "13px 0", fontSize: 14, fontWeight: 700,
            fontFamily: "var(--ff-display)", borderRadius: 10, border: "none",
            background: "var(--primary)", color: "#fff", cursor: "pointer",
            opacity: adding ? 0.6 : 1,
          }}
        >
          {adding ? "Adding…" : `Add all ${bundle.item_count} parts to cart`}
        </button>

        {/* Parts list */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}>
          <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 10 }}>
            {bundle.item_count} part{bundle.item_count !== 1 ? "s" : ""} in this bundle
          </p>
          <div className="space-y-2">
            {items.map((item) => {
              const ship = formatShippingEstimate(item.shipping_size, null);
              return (
                <div key={item.id} style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  {/* Thumbnail */}
                  <div style={{ width: 48, height: 48, borderRadius: 6, overflow: "hidden", flexShrink: 0, background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                    {item.primary_photo_url ? (
                      <img src={item.primary_photo_url} alt={item.title} className="w-full h-full object-cover" />
                    ) : (
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 18 }}>📦</div>
                    )}
                  </div>
                  {/* Info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Link
                      href={`/browse/parts/${item.id}`}
                      style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", textDecoration: "none", fontFamily: "var(--ff-display)", display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                    >
                      {item.title}
                    </Link>
                    <div style={{ display: "flex", gap: 6, marginTop: 2, flexWrap: "wrap" }}>
                      {item.condition && (
                        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{item.condition.replace(/_/g, " ")}</span>
                      )}
                      {item.shipping_size && (
                        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>📦 {item.shipping_size}</span>
                      )}
                      {ship && (
                        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{ship}</span>
                      )}
                    </div>
                  </div>
                  {/* Price */}
                  <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", flexShrink: 0 }}>
                    {formatMoney(item.price)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Savings summary */}
        {hasDiscount && (
          <div style={{ background: "rgba(74,222,128,0.06)", border: "1px solid rgba(74,222,128,0.2)", borderRadius: "var(--radius-xl)", padding: "12px 16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--text-secondary)", marginBottom: 4 }}>
              <span>List total</span><span>{formatMoney(bundle.total_price)}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#4ade80" }}>
              <span>Bundle discount ({Number(bundle.discount_pct)}%)</span>
              <span>−{formatMoney(Number(bundle.total_price) - Number(bundle.discounted_price))}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 15, fontWeight: 700, color: "var(--text-primary)", marginTop: 8, paddingTop: 8, borderTop: "1px solid rgba(74,222,128,0.2)" }}>
              <span>Bundle price</span><span style={{ color: "var(--primary)" }}>{formatMoney(bundle.discounted_price)}</span>
            </div>
          </div>
        )}

      </motion.div>
    </div>
  );
}
