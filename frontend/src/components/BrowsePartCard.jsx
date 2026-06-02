"use client";

import Link from "next/link";
import { useState } from "react";

import { effectivePartBuyPrice } from "@/lib/part-pricing";
import { returnPolicyBadgeLabel } from "@/lib/return-policy";

const ILLUSTRATION_EMOJI = {
  engine: "⚙️",
  drivetrain: "🛞",
  suspension: "🔩",
  brakes: "🛑",
  body_exterior: "🚗",
  body_interior: "🪑",
  electrical: "⚡",
  hvac: "❄️",
  fuel_system: "⛽",
  exhaust: "💨",
};

function categoryEmoji(part) {
  const key = part.part_family?.category?.illustration_key;
  return ILLUSTRATION_EMOJI[key] || "📦";
}

function returnPolicyStyle(p) {
  if (p === "green") {
    return {
      background: "var(--success-muted)",
      border: "1px solid color-mix(in srgb, var(--success) 35%, transparent)",
      color: "var(--success)",
    };
  }
  if (p === "yellow") {
    return {
      background: "var(--warning-muted)",
      border: "1px solid color-mix(in srgb, var(--warning) 40%, transparent)",
      color: "var(--warning)",
    };
  }
  return {
    background: "var(--danger-muted)",
    border: "1px solid color-mix(in srgb, var(--danger) 35%, transparent)",
    color: "var(--danger)",
  };
}

const TIER_STYLES = {
  small: {
    background: "color-mix(in srgb, var(--accent) 10%, var(--bg-surface))",
    border: "1px solid color-mix(in srgb, var(--accent) 28%, transparent)",
    color: "var(--accent)",
  },
  medium: {
    background: "color-mix(in srgb, var(--accent) 8%, var(--bg-surface))",
    border: "1px solid color-mix(in srgb, var(--accent) 22%, transparent)",
    color: "var(--accent-dim)",
  },
  large: {
    background: "var(--primary-muted)",
    border: "1px solid var(--primary-border-soft)",
    color: "var(--primary)",
  },
};

export function BrowsePartCard({
  part,
  messageHref,
  selectable = false,
  selected = false,
  onToggleSelect,
  onAddToCart,
  shippingMode = "standard",
  onShippingModeChange,
  buyerZipPresent = false,
  onCardClick,
}) {
  const [cartOpen, setCartOpen] = useState(false);
  const [cartNotes, setCartNotes] = useState("");

  const img = part.card_image_url || (part.image_urls && part.image_urls[0]);
  const vp = part.vehicle_public || {};
  const eff = part.listing_state_effective || part.listing_state;
  const buyPrice = effectivePartBuyPrice(part);
  const listNum = part.price != null && part.price !== "" ? Number(part.price) : null;
  const showOffer =
    buyPrice != null &&
    listNum != null &&
    Number.isFinite(listNum) &&
    Math.abs(buyPrice - listNum) > 0.005;
  const ship = part.shipping_preview || {};
  const tier = ship.size_tier || "small";
  const tierLabel = ship.size_tier_label || tier;
  const options = Array.isArray(ship.shipping_options) ? ship.shipping_options : [];

  return (
    <article
      onClick={onCardClick}
      style={{
        background: "var(--bg-surface)",
        border: `1px solid var(--border)`,
        borderRadius: "var(--radius-lg)",
        padding: "10px 12px",
        cursor: onCardClick ? "pointer" : "default",
        transition: "border-color 0.15s, box-shadow 0.15s",
      }}
      onMouseEnter={e => {
        if (onCardClick) {
          e.currentTarget.style.borderColor = "var(--primary-border-strong)";
          e.currentTarget.style.boxShadow = "var(--shadow-sm)";
        }
      }}
      onMouseLeave={e => {
        if (onCardClick) {
          e.currentTarget.style.borderColor = "var(--border)";
          e.currentTarget.style.boxShadow = "none";
        }
      }}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        {/* Image */}
        <div className="h-16 w-full overflow-hidden lg:w-20 lg:flex-none"
          style={{ borderRadius: "var(--radius-md)", background: "var(--bg-elevated)" }}>
          {img ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={img} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-3xl" style={{ opacity: 0.7 }}>
              {categoryEmoji(part)}
            </div>
          )}
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <h3 className="min-w-0 truncate text-sm font-semibold" style={{ color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
              <Link
                href={`/browse/parts/${part.id}`}
                onClick={(e) => e.stopPropagation()}
                className="hover:underline"
                style={{ color: "inherit", textDecoration: "none" }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--primary)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "inherit"; }}
              >
                {part.label}
              </Link>
            </h3>
            <span style={{ ...TIER_STYLES[tier] || TIER_STYLES.small, borderRadius: "999px", padding: "1px 8px", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", fontFamily: "var(--ff-display)" }}>
              {tierLabel}
            </span>
            {eff === "buy_now" && (
              <span style={{ background: "var(--primary)", borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 700, color: "#fff", fontFamily: "var(--ff-display)" }}>
                Buy now
              </span>
            )}
            {eff === "sold" && (
              <span style={{ background: "rgba(148,163,184,0.2)", border: "1px solid rgba(148,163,184,0.35)", borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 700, color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                Sold
              </span>
            )}
            {(eff === "unavailable" || eff === "sold_elsewhere") && (
              <span style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                {eff === "sold_elsewhere" ? "Sold elsewhere" : "Unavailable"}
              </span>
            )}
            {eff === "message_only" && (
              <span style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                Message seller
              </span>
            )}
            {eff === "draft" && (
              <span style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                Draft
              </span>
            )}
            <span style={{ ...returnPolicyStyle(part.return_policy), borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 500, fontFamily: "var(--ff-body)" }}>
              {returnPolicyBadgeLabel(part.return_policy)}
            </span>
          </div>

          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
            <span>
              {vp.year} {vp.make} {vp.model}
              {vp.trim ? ` · ${vp.trim}` : ""}
            </span>
            <span>
              From {vp.location_state || "—"} {vp.location_zip_masked || ""}
            </span>
            <span>
              {ship.available ? ship.estimate : ship.note || "Add your ZIP for transit estimate."}
            </span>
          </div>

          {ship.available && options.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {options.map((opt) => (
                <label
                  key={opt.code}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    borderRadius: "var(--radius-md)",
                    padding: "4px 10px",
                    fontSize: 11,
                    cursor: "pointer",
                    border: shippingMode === opt.code
                      ? "1px solid var(--primary-border-strong)"
                      : "1px solid var(--border)",
                    background: shippingMode === opt.code
                      ? "var(--primary-muted)"
                      : "var(--bg-elevated)",
                    color: shippingMode === opt.code
                      ? "var(--primary)"
                      : "var(--text-secondary)",
                    transition: "all 0.12s",
                  }}
                >
                  <input
                    type="radio"
                    name={`ship-${part.id}`}
                    className="sr-only"
                    checked={shippingMode === opt.code}
                    onChange={() => onShippingModeChange?.(part.id, opt.code)}
                  />
                  <span style={{ fontWeight: 600, fontFamily: "var(--ff-display)" }}>{opt.label}</span>
                  <span style={{ color: "var(--text-muted)" }}>
                    {Number(opt.usd) === 0 ? "Free" : `$${opt.usd}`}
                  </span>
                </label>
              ))}
            </div>
          )}

          {!buyerZipPresent && eff === "buy_now" && (
            <p className="mt-1" style={{ fontSize: 11, color: "var(--warning)" }}>Enter ZIP above to load shipping prices.</p>
          )}
          {part.is_damaged && (
            <p className="mt-1 text-xs font-medium" style={{ color: "var(--warning)" }}>May have damage</p>
          )}
        </div>

        {/* Actions */}
        <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:flex-none lg:justify-end" onClick={(e) => e.stopPropagation()}>
          {buyPrice != null && eff === "buy_now" ? (
            <p className="price-mono mr-1 text-sm" style={{ color: "var(--primary)" }}>
              {showOffer && (
                <span className="mr-1 line-through opacity-60" style={{ color: "var(--text-muted)", fontSize: 11 }}>
                  {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(listNum)}
                </span>
              )}
              {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(buyPrice)}
            </p>
          ) : eff === "sold" ? (
            <p className="mr-1 text-xs font-semibold" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Sold</p>
          ) : (
            <p className="mr-1 text-xs" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}>Not for sale</p>
          )}

          <Link
            href={messageHref}
            style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              borderRadius: "var(--radius-md)", padding: "6px 12px",
              fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)",
              background: "var(--bg-elevated)", border: "1px solid var(--border)",
              color: "var(--text-secondary)", transition: "all 0.12s",
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--border-strong)"; e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-secondary)"; }}
          >
            Message
          </Link>

          {eff === "buy_now" && buyPrice != null && (
            <Link
              href={`/checkout?part=${encodeURIComponent(String(part.id))}`}
              style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                borderRadius: "var(--radius-md)", padding: "6px 12px",
                fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)",
                background: "var(--primary)", color: "#fff", transition: "all 0.12s",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = "var(--primary-dim)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "var(--primary)"; }}
            >
              Checkout
            </Link>
          )}

          {eff === "buy_now" && buyPrice != null && onAddToCart && (
            <button
              type="button"
              onClick={() => { setCartNotes(""); setCartOpen(true); }}
              style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                borderRadius: "var(--radius-md)", padding: "6px 12px",
                fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)",
                background: "var(--bg-elevated)", border: "1px solid var(--border)",
                color: "var(--text-secondary)", cursor: "pointer", transition: "all 0.12s",
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--border-strong)"; e.currentTarget.style.color = "var(--text-primary)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-secondary)"; }}
            >
              + Cart
            </button>
          )}

          {selectable && (
            <button
              type="button"
              onClick={() => onToggleSelect?.(part.id)}
              style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                borderRadius: "var(--radius-md)", padding: "6px 12px",
                fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)",
                cursor: "pointer", transition: "all 0.12s",
                background: selected ? "var(--primary-muted)" : "var(--bg-elevated)",
                border: selected ? "1px solid var(--primary-border-strong)" : "1px solid var(--border)",
                color: selected ? "var(--primary)" : "var(--text-secondary)",
              }}
            >
              {selected ? "Selected ✓" : "Select"}
            </button>
          )}
        </div>
      </div>

      {/* Cart modal */}
      {cartOpen && onAddToCart && (
        <div className="fixed inset-0 z-[100] flex items-end justify-center p-4 sm:items-center" role="dialog" aria-modal>
          <div className="absolute inset-0 bg-black/60" onClick={() => setCartOpen(false)} />
          <div className="relative z-10 w-full max-w-md p-5"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", boxShadow: "var(--shadow-xl)" }}>
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>Add to cart</p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>{part.label}</p>
            <label className="mt-3 block">
              <span className="text-xs font-medium" style={{ color: "var(--text-secondary)", fontFamily: "var(--ff-display)" }}>
                Note for the seller <span style={{ fontWeight: 400, color: "var(--text-muted)" }}>(optional)</span>
              </span>
              <textarea
                value={cartNotes}
                onChange={(e) => setCartNotes(e.target.value)}
                rows={3}
                placeholder="e.g. Driver side (LH), color, VIN last 8…"
                className="input-forge mt-1 w-full resize-none"
                style={{ minHeight: 80 }}
              />
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCartOpen(false)}
                style={{
                  borderRadius: "var(--radius-md)", padding: "8px 16px",
                  fontSize: 13, fontWeight: 500, fontFamily: "var(--ff-display)",
                  background: "var(--bg-elevated)", border: "1px solid var(--border)",
                  color: "var(--text-secondary)", cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => { onAddToCart(part.id, shippingMode, cartNotes.trim()); setCartOpen(false); }}
                className="btn-forge"
                style={{ padding: "8px 20px", fontSize: 13 }}
              >
                Add to cart
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
