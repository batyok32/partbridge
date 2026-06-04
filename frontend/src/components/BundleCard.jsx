"use client";

import Link from "next/link";
import { useState } from "react";

import { formatShippingEstimate } from "@/lib/shipping-rates";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

export default function BundleCard({ bundle, user, destinationState, onAddAllToCart }) {
  const [adding, setAdding] = useState(false);

  const vehicleName = [bundle.vehicle_year, bundle.vehicle_make, bundle.vehicle_model]
    .filter(Boolean)
    .join(" ");

  const hasDiscount = bundle.discount_pct && Number(bundle.discount_pct) > 0;
  const isAssembly = bundle.bundle_type === "assembly";

  async function handleAddAll(e) {
    e.preventDefault();
    e.stopPropagation();
    if (!user) { window.location.href = "/login?next=/search"; return; }
    setAdding(true);
    try {
      await onAddAllToCart(bundle.id);
    } finally {
      setAdding(false);
    }
  }

  return (
    <div
      style={{
        background: "var(--bg-surface)",
        border: "2px solid var(--border)",
        borderRadius: "var(--radius-xl)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        position: "relative",
      }}
    >
      {/* Kit / Assembly badge */}
      <div style={{ position: "absolute", top: 10, right: 10, zIndex: 10, display: "flex", gap: 4 }}>
        <span style={{
          fontSize: 10, fontWeight: 700, fontFamily: "var(--ff-display)",
          background: isAssembly ? "rgba(139,92,246,0.85)" : "rgba(255,92,26,0.85)",
          color: "#fff", borderRadius: 4, padding: "2px 8px", letterSpacing: "0.06em",
        }}>
          {isAssembly ? "Assembly" : "Kit"}
        </span>
        {hasDiscount && (
          <span style={{
            fontSize: 10, fontWeight: 700, fontFamily: "var(--ff-display)",
            background: "rgba(74,222,128,0.85)", color: "#000",
            borderRadius: 4, padding: "2px 8px",
          }}>
            {Number(bundle.discount_pct)}% off
          </span>
        )}
      </div>

      {/* Photo */}
      <div style={{ aspectRatio: "16/9", background: "var(--bg-elevated)", overflow: "hidden", position: "relative" }}>
        {bundle.primary_photo_url ? (
          <img src={bundle.primary_photo_url} alt={bundle.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 40, color: "var(--text-muted)" }}>📦</div>
        )}
      </div>

      <div style={{ padding: "14px 16px", flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
        {/* Title + vehicle */}
        <div>
          <p style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.3 }}>
            {bundle.name}
          </p>
          {vehicleName && (
            <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 3 }}>From: {vehicleName}</p>
          )}
          {bundle.vehicle_generation_label && (
            <p style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--ff-mono)" }}>
              {bundle.vehicle_generation_label}
            </p>
          )}
        </div>

        {/* Item list preview */}
        <div style={{ background: "var(--bg-elevated)", borderRadius: 8, padding: "8px 10px" }}>
          <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 6 }}>
            {bundle.item_count} part{bundle.item_count !== 1 ? "s" : ""} included
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {(bundle.items || []).slice(0, 4).map((bi) => {
              const it = bi.item_detail || {};
              const ship = formatShippingEstimate(it.shipping_size, destinationState);
              return (
                <div key={bi.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <p style={{ fontSize: 11, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                    {it.title || "Part"}
                  </p>
                  <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
                    {ship && <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{ship}</span>}
                    <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-primary)" }}>
                      {it.price ? formatMoney(it.price) : ""}
                    </span>
                  </div>
                </div>
              );
            })}
            {bundle.item_count > 4 && (
              <p style={{ fontSize: 11, color: "var(--text-muted)" }}>+{bundle.item_count - 4} more</p>
            )}
          </div>
        </div>

        {/* Pricing */}
        <div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ fontSize: 18, fontWeight: 700, color: "var(--primary)", fontFamily: "var(--ff-display)" }}>
              {formatMoney(bundle.discounted_price)}
            </span>
            {hasDiscount && (
              <span style={{ fontSize: 12, color: "var(--text-muted)", textDecoration: "line-through" }}>
                {formatMoney(bundle.total_price)}
              </span>
            )}
          </div>
          {hasDiscount && (
            <span style={{
              fontSize: 11, fontWeight: 700, color: "#16a34a",
              background: "rgba(22,163,74,0.10)", borderRadius: 4,
              padding: "2px 7px", display: "inline-block", marginTop: 4,
            }}>
              Save {formatMoney(Number(bundle.total_price) - Number(bundle.discounted_price))} · {Number(bundle.discount_pct)}% off
            </span>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
          <button
            type="button"
            onClick={handleAddAll}
            disabled={adding}
            style={{
              flex: 1, fontSize: 13, fontWeight: 700, padding: "9px 0",
              borderRadius: 8, background: "var(--primary)", color: "#fff",
              border: "none", cursor: "pointer", opacity: adding ? 0.6 : 1,
              fontFamily: "var(--ff-display)",
            }}
          >
            {adding ? "Adding…" : "Add kit to cart"}
          </button>
          <Link
            href={`/bundles/${bundle.id}`}
            style={{
              fontSize: 12, fontWeight: 600, padding: "9px 14px", borderRadius: 8,
              border: "1px solid var(--border)", color: "var(--text-secondary)",
              textDecoration: "none", whiteSpace: "nowrap",
            }}
          >
            Details
          </Link>
        </div>
      </div>
    </div>
  );
}
