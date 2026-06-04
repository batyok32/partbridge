"use client";

import Link from "next/link";
import { useState } from "react";

import FitmentBadge from "@/components/FitmentBadge";
import { formatShippingEstimate } from "@/lib/shipping-rates";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(v));
}

function conditionLabel(c) {
  return (
    {
      excellent: "Excellent",
      good: "Good",
      fair: "Fair",
      for_parts: "For parts",
    }[c] ||
    c ||
    "—"
  );
}

function sizeLabel(s) {
  return (
    { small: "Small", medium: "Medium", large: "Large", xl: "Extra Large" }[
      s
    ] ||
    s ||
    "—"
  );
}

function partNumberMatchType(item, normalizedQuery) {
  if (!normalizedQuery) return null;
  if (item.oem_part_number_normalized === normalizedQuery) return "oem";
  if (
    item.alt_part_numbers?.some((p) => p.number_normalized === normalizedQuery)
  )
    return "cross_ref";
  // fallback: substring match
  if (item.oem_part_number_normalized?.includes(normalizedQuery)) return "oem";
  if (
    item.alt_part_numbers?.some((p) =>
      p.number_normalized?.includes(normalizedQuery),
    )
  )
    return "cross_ref";
  return null;
}

export default function SearchItemCard({
  item,
  user,
  destinationState,
  carGenerationLabel,
  partNumberQuery,
  onAddToCart,
  onRemoveFromCart,
  inCart,
}) {
  const [adding, setAdding] = useState(false);
  const vehicleName = [item.vehicle_year, item.vehicle_make, item.vehicle_model]
    .filter(Boolean)
    .join(" ");
  const pnMatch = partNumberMatchType(item, partNumberQuery);
  const shippingEst = formatShippingEstimate(
    item.shipping_size,
    destinationState,
  );

  async function handleCart(e) {
    e.preventDefault();
    e.stopPropagation();
    if (!user) {
      window.location.href = `/login?next=/search`;
      return;
    }
    setAdding(true);
    try {
      if (inCart) {
        await onRemoveFromCart(item.id);
      } else {
        await onAddToCart(item.id);
      }
    } finally {
      setAdding(false);
    }
  }

  return (
    <Link
      href={`/browse/parts/${item.id}`}
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-xl)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div
        style={{
          aspectRatio: "16/10",
          background: "var(--bg-elevated)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {item.primary_photo_url ? (
          <img
            src={item.primary_photo_url}
            alt={item.title}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              color: "var(--text-muted)",
              fontSize: 32,
            }}
          >
            📦
          </div>
        )}
        <div
          style={{
            position: "absolute",
            top: 8,
            left: 8,
            display: "flex",
            flexDirection: "column",
            gap: 4,
            alignItems: "flex-start",
          }}
        >
          <FitmentBadge
            fitment={item.fitment}
            generationLabel={carGenerationLabel || item.vehicle_generation_name}
          />
          {pnMatch && (
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: "2px 6px",
                borderRadius: 4,
                background: pnMatch === "oem" ? "#166534" : "#1e3a5f",
                color: "#fff",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              {pnMatch === "oem" ? "OEM match" : "Cross-ref"}
            </span>
          )}
        </div>
      </div>

      <div
        style={{
          padding: "12px 14px",
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <p
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: "var(--text-primary)",
            fontFamily: "var(--ff-display)",
            lineHeight: 1.3,
          }}
        >
          {item.category_name}
        </p>
        <p style={{ fontSize: 11, color: "var(--text-muted)" }}>
          From: {vehicleName || "—"}
        </p>

        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: 4,
              padding: "1px 6px",
              color: "var(--text-secondary)",
            }}
          >
            {conditionLabel(item.condition)}
          </span>
          {(item.options || []).map((o) => (
            <span
              key={o.id}
              style={{
                fontSize: 10,
                fontWeight: 700,
                background: "var(--primary-muted)",
                border: "1px solid var(--primary-border-soft, var(--border))",
                borderRadius: 4,
                padding: "1px 6px",
                color: "var(--primary)",
              }}
            >
              {o.option_category_name}: {o.value}
            </span>
          ))}
        </div>

        {shippingEst && (
          <p style={{ fontSize: 10, color: "var(--text-muted)" }}>
            {shippingEst}
          </p>
        )}

        {(item.seller_name || item.seller_rating_avg != null) && (
          <p style={{ fontSize: 10, color: "var(--text-muted)" }}>
            {item.seller_name}
            {item.seller_rating_avg != null &&
              ` · ★ ${item.seller_rating_avg} (${item.seller_review_count || 0})`}
          </p>
        )}

        <div
          style={{
            marginTop: "auto",
            paddingTop: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
          }}
        >
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "var(--text-primary)",
              fontFamily: "var(--ff-display)",
            }}
          >
            {formatMoney(item.price)}
          </span>
          {item.status && item.status !== "active" ? (
            <span style={{
              fontSize: 12, fontWeight: 700, padding: "6px 12px", borderRadius: 8,
              background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
              color: "#f87171",
            }}>
              Sold
            </span>
          ) : (
            <button
              type="button"
              onClick={handleCart}
              disabled={adding}
              style={{
                fontSize: 12,
                fontWeight: 600,
                padding: "6px 12px",
                borderRadius: 8,
                background: inCart ? "var(--bg-elevated)" : "var(--primary)",
                color: inCart ? "var(--text-secondary)" : "#fff",
                border: inCart ? "1px solid var(--border)" : "none",
                cursor: "pointer",
                opacity: adding ? 0.6 : 1,
              }}
            >
              {adding ? "…" : inCart ? "Remove from cart" : "Add to cart"}
            </button>
          )}
        </div>
      </div>
    </Link>
  );
}
