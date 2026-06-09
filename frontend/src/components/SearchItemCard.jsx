"use client";

import Link from "next/link";
import { useState, useCallback, useRef, useEffect } from "react";

import FitmentBadge from "@/components/FitmentBadge";
import { formatShippingEstimate } from "@/lib/shipping-rates";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(v));
}

function partNumberMatchType(item, normalizedQuery) {
  if (!normalizedQuery) return null;
  if (item.oem_part_number_normalized === normalizedQuery) return "oem";
  if (item.alt_part_numbers?.some((p) => p.number_normalized === normalizedQuery))
    return "cross_ref";
  if (item.oem_part_number_normalized?.includes(normalizedQuery)) return "oem";
  if (item.alt_part_numbers?.some((p) => p.number_normalized?.includes(normalizedQuery)))
    return "cross_ref";
  return null;
}

function buildSlides(item) {
  const seen = new Set();
  const out = [];
  const push = (url) => {
    if (url && !seen.has(url)) {
      seen.add(url);
      out.push(url);
    }
  };
  (item.photo_urls || []).forEach(push);
  push(item.category_image_url);
  push(item.vehicle_image_url);
  return out;
}

function NoImagePlaceholder({ size = 40 }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        color: "var(--text-muted)",
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ opacity: 0.35 }}
      >
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
        <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
        <line x1="12" y1="22.08" x2="12" y2="12" />
      </svg>
    </div>
  );
}

function ImageSlider({ slides, alt, compact = false }) {
  const [idx, setIdx] = useState(0);
  const [failed, setFailed] = useState(() => new Set());
  const [hovered, setHovered] = useState(false);
  const containerRef = useRef(null);

  const validSlides = slides.filter((_, i) => !failed.has(i));
  const validIdx = validSlides.length ? Math.min(idx, validSlides.length - 1) : 0;

  const handleError = useCallback((originalIdx) => {
    setFailed((prev) => {
      const next = new Set(prev);
      next.add(originalIdx);
      return next;
    });
  }, []);

  // Touch swipe via addEventListener so it fires reliably on iOS/Android
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let startX = 0;
    let startY = 0;

    function onTouchStart(e) {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
    }

    function onTouchEnd(e) {
      const dx = e.changedTouches[0].clientX - startX;
      const dy = e.changedTouches[0].clientY - startY;
      if (Math.abs(dx) > Math.abs(dy) * 1.2 && Math.abs(dx) > 30) {
        setIdx((prev) => {
          const len = validSlides.length;
          if (len <= 1) return prev;
          return dx < 0 ? (prev + 1) % len : (prev - 1 + len) % len;
        });
      }
    }

    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchend", onTouchEnd, { passive: true });
    return () => {
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchend", onTouchEnd);
    };
  }, [validSlides.length]);

  function prev(e) {
    e.preventDefault();
    e.stopPropagation();
    setIdx((i) => (i - 1 + validSlides.length) % validSlides.length);
  }

  function next(e) {
    e.preventDefault();
    e.stopPropagation();
    setIdx((i) => (i + 1) % validSlides.length);
  }

  if (validSlides.length === 0) return <NoImagePlaceholder size={compact ? 24 : 40} />;

  return (
    <div
      ref={containerRef}
      style={{ position: "relative", width: "100%", height: "100%" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {slides.map((url, i) => {
        if (failed.has(i)) return null;
        const validPosition =
          slides.slice(0, i + 1).filter((_, j) => !failed.has(j)).length - 1;
        const isCurrent = validPosition === validIdx;
        return (
          <img
            key={i}
            src={url}
            alt={alt}
            loading="lazy"
            onError={() => handleError(i)}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              opacity: isCurrent ? 1 : 0,
              transition: "opacity 0.2s",
              pointerEvents: "none",
            }}
          />
        );
      })}

      {/* Arrows — desktop hover only */}
      {validSlides.length > 1 && hovered && !compact && (
        <>
          <button
            type="button"
            onClick={prev}
            style={{
              position: "absolute",
              left: 6,
              top: "50%",
              transform: "translateY(-50%)",
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: "rgba(0,0,0,0.55)",
              border: "none",
              color: "#fff",
              fontSize: 14,
              lineHeight: 1,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 10,
            }}
          >
            ‹
          </button>
          <button
            type="button"
            onClick={next}
            style={{
              position: "absolute",
              right: 6,
              top: "50%",
              transform: "translateY(-50%)",
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: "rgba(0,0,0,0.55)",
              border: "none",
              color: "#fff",
              fontSize: 14,
              lineHeight: 1,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 10,
            }}
          >
            ›
          </button>
        </>
      )}

      {/* Dot indicators */}
      {validSlides.length > 1 && (
        <div
          style={{
            position: "absolute",
            bottom: compact ? 3 : 6,
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            gap: compact ? 3 : 4,
            zIndex: 10,
            pointerEvents: "none",
          }}
        >
          {validSlides.map((_, i) => (
            <span
              key={i}
              style={{
                width: i === validIdx ? (compact ? 8 : 14) : (compact ? 3 : 5),
                height: compact ? 3 : 5,
                borderRadius: 3,
                background: i === validIdx ? "#fff" : "rgba(255,255,255,0.5)",
                transition: "width 0.2s",
                display: "inline-block",
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function NavLink({ href, onClick, children, style }) {
  return (
    <span
      role="link"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick(e)}
      style={{ cursor: "pointer", ...style }}
    >
      {children}
    </span>
  );
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
  variant = "card",
}) {
  const [adding, setAdding] = useState(false);
  const [cardHovered, setCardHovered] = useState(false);

  const vehicleName = [item.vehicle_year, item.vehicle_make, item.vehicle_model]
    .filter(Boolean)
    .join(" ");
  const pnMatch = partNumberMatchType(item, partNumberQuery);
  const shippingEst = formatShippingEstimate(item.shipping_size, destinationState);
  const slides = buildSlides(item);

  async function handleCart(e) {
    e.preventDefault();
    e.stopPropagation();
    if (!user) {
      window.location.href = `/login?next=/search`;
      return;
    }
    setAdding(true);
    try {
      if (inCart) await onRemoveFromCart(item.id);
      else await onAddToCart(item.id);
    } finally {
      setAdding(false);
    }
  }

  function handleVehicleClick(e) {
    e.preventDefault();
    e.stopPropagation();
    if (item.vehicle) window.location.href = `/browse/vehicles/${item.vehicle}`;
  }

  function handleSellerClick(e) {
    e.preventDefault();
    e.stopPropagation();
    if (item.seller_id) window.location.href = `/sellers/${item.seller_id}`;
  }

  const isSold = item.status && item.status !== "active";

  const cartBtn = isSold ? (
    <span
      style={{
        fontSize: 12,
        fontWeight: 700,
        padding: "5px 10px",
        borderRadius: 7,
        background: "rgba(239,68,68,0.08)",
        border: "1px solid rgba(239,68,68,0.25)",
        color: "#dc2626",
        whiteSpace: "nowrap",
      }}
    >
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
        padding: "7px 12px",
        borderRadius: 7,
        background: inCart ? "var(--bg-elevated)" : "var(--primary)",
        color: inCart ? "var(--text-secondary)" : "#fff",
        border: inCart ? "1px solid var(--border)" : "none",
        cursor: "pointer",
        opacity: adding ? 0.6 : 1,
        whiteSpace: "nowrap",
        flexShrink: 0,
      }}
    >
      {adding ? "…" : inCart ? "Remove" : "Add to cart"}
    </button>
  );

  const baseCardStyle = {
    background: "var(--bg-surface)",
    border: `1px solid ${cardHovered ? "var(--border-strong)" : "var(--border)"}`,
    overflow: "hidden",
    display: "flex",
    textDecoration: "none",
    color: "inherit",
    boxShadow: cardHovered ? "var(--shadow-md)" : "var(--shadow-sm)",
    transform: cardHovered ? "translateY(-1px)" : "translateY(0)",
    transition: "box-shadow 0.15s, transform 0.15s, border-color 0.15s",
  };

  // ── Row variant (mobile list) ─────────────────────────────────────────────
  if (variant === "row") {
    return (
      <Link
        href={`/browse/parts/${item.id}`}
        style={{ ...baseCardStyle, flexDirection: "row", borderRadius: "var(--radius-lg)" }}
        onMouseEnter={() => setCardHovered(true)}
        onMouseLeave={() => setCardHovered(false)}
      >
        {/* Thumbnail — swipeable ImageSlider */}
        <div
          style={{
            width: 110,
            alignSelf: "stretch",
            flexShrink: 0,
            background: "var(--bg-elevated)",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <ImageSlider slides={slides} alt={item.category_name} compact />
          {item.fitment?.status === "fits" && (
            <span
              style={{
                position: "absolute",
                bottom: 4,
                left: 4,
                fontSize: 8,
                fontWeight: 700,
                background: "color-mix(in srgb, var(--success) 18%, transparent)",
                color: "var(--success)",
                border: "1px solid color-mix(in srgb, var(--success) 35%, transparent)",
                borderRadius: 3,
                padding: "1px 4px",
                zIndex: 5,
              }}
            >
              Fits
            </span>
          )}
        </div>

        {/* Content */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            padding: "10px 12px",
            display: "flex",
            flexDirection: "column",
            gap: 3,
          }}
        >
          {/* Category */}
          <p
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: "var(--text-primary)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {item.category_name}
          </p>

          {/* Vehicle + first option */}
          <div style={{ display: "flex", gap: 5, alignItems: "center", overflow: "hidden" }}>
            {vehicleName && (
              <NavLink
                onClick={handleVehicleClick}
                style={{
                  fontSize: 11,
                  color: "var(--accent)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  flex: 1,
                  textDecoration: "underline",
                  textDecorationColor: "transparent",
                }}
              >
                {vehicleName}
              </NavLink>
            )}
            {(item.options || []).slice(0, 1).map((o) => (
              <span
                key={o.id}
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  background: "var(--primary-muted)",
                  border: "1px solid var(--primary-border-soft, var(--border))",
                  borderRadius: 4,
                  padding: "1px 5px",
                  color: "var(--primary)",
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }}
              >
                {o.value}
              </span>
            ))}
          </div>

          {/* OEM part number */}
          {item.oem_part_number && (
            <p
              style={{
                fontSize: 10,
                color: "var(--text-muted)",
                fontFamily: "var(--font-mono)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              #{item.oem_part_number}
              {pnMatch && (
                <span
                  style={{
                    marginLeft: 5,
                    fontSize: 9,
                    fontWeight: 700,
                    padding: "1px 4px",
                    borderRadius: 3,
                    background: pnMatch === "oem" ? "#166534" : "#1e3a5f",
                    color: "#fff",
                    textTransform: "uppercase",
                    letterSpacing: "0.03em",
                  }}
                >
                  {pnMatch === "oem" ? "OEM" : "X-ref"}
                </span>
              )}
            </p>
          )}

          {/* Shipping */}
          {shippingEst && (
            <p style={{ fontSize: 10, color: "var(--text-muted)" }}>{shippingEst}</p>
          )}

          {/* Price + cart button */}
          <div
            style={{
              marginTop: "auto",
              paddingTop: 5,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <span
              style={{
                fontSize: 15,
                fontWeight: 700,
                color: "var(--text-primary)",
                fontFamily: "var(--ff-display)",
              }}
            >
              {formatMoney(item.price)}
            </span>
            {cartBtn}
          </div>
        </div>
      </Link>
    );
  }

  // ── Card variant (default, desktop grid) ─────────────────────────────────
  return (
    <Link
      href={`/browse/parts/${item.id}`}
      style={{ ...baseCardStyle, flexDirection: "column", borderRadius: "var(--radius-xl)" }}
      onMouseEnter={() => setCardHovered(true)}
      onMouseLeave={() => setCardHovered(false)}
    >
      <div
        style={{
          aspectRatio: "16/10",
          background: "var(--bg-elevated)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <ImageSlider slides={slides} alt={item.category_name} />

        <div
          style={{
            position: "absolute",
            top: 8,
            left: 8,
            display: "flex",
            flexDirection: "column",
            gap: 4,
            alignItems: "flex-start",
            zIndex: 5,
            pointerEvents: "none",
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

        {vehicleName && (
          <NavLink
            onClick={handleVehicleClick}
            style={{ fontSize: 11, color: "var(--accent)", textDecoration: "underline" }}
          >
            From: {vehicleName}
          </NavLink>
        )}

        {(item.options || []).length > 0 && (
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
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
        )}

        {item.oem_part_number && (
          <p
            style={{
              fontSize: 10,
              color: "var(--text-muted)",
              fontFamily: "var(--font-mono)",
            }}
          >
            #{item.oem_part_number}
          </p>
        )}

        {shippingEst && (
          <p style={{ fontSize: 10, color: "var(--text-muted)" }}>{shippingEst}</p>
        )}

        {(item.seller_name || item.seller_rating_avg != null) && (
          <NavLink
            onClick={handleSellerClick}
            style={{ fontSize: 10, color: "var(--accent)", textDecoration: "underline" }}
          >
            {item.seller_name}
            {item.seller_rating_avg != null &&
              ` · ★ ${item.seller_rating_avg} (${item.seller_review_count || 0})`}
          </NavLink>
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
          {isSold ? (
            <span
              style={{
                fontSize: 12,
                fontWeight: 700,
                padding: "6px 12px",
                borderRadius: 8,
                background: "rgba(239,68,68,0.08)",
                border: "1px solid rgba(239,68,68,0.25)",
                color: "#dc2626",
              }}
            >
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
                padding: "8px 14px",
                minHeight: 40,
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
