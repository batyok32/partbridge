"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useToast } from "@/context/toast-context";

const LISTING_STATES = [
  { value: "draft", label: "Draft" },
  { value: "buy_now", label: "Buy now" },
  { value: "sold", label: "Sold" },
  { value: "unavailable", label: "Unavailable" },
  { value: "sold_elsewhere", label: "Sold elsewhere" },
];

const CONDITIONS = [
  { value: "oem_untested", label: "OEM — untested" },
  { value: "oem_tested", label: "OEM — tested" },
  { value: "aftermarket", label: "Aftermarket" },
  { value: "new", label: "New" },
  { value: "used", label: "Used" },
];

const RETURN_POLICIES = [
  { value: "green",  label: "Green — 30-day protection", short: "30-day" },
  { value: "yellow", label: "Yellow — restocking fee",   short: "Restock" },
  { value: "red",    label: "Red — final sale",          short: "Final sale" },
];

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

/** Horizontal scroll-snap gallery: swipe on touch, arrows + dots when multiple images. */
function PartImageSlider({ urls, emptyFallback }) {
  const scrollerRef = useRef(null);
  const [active, setActive] = useState(0);
  const n = urls.length;

  const scrollToIndex = useCallback((i) => {
    const el = scrollerRef.current;
    if (!el || n < 1) return;
    const next = Math.min(Math.max(0, i), n - 1);
    const w = el.clientWidth;
    el.scrollTo({ left: next * w, behavior: "smooth" });
    setActive(next);
  }, [n]);

  const urlFingerprint = urls.join("|");

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollLeft = 0;
    setActive(0);
  }, [urlFingerprint]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || n < 2) return;
    const onScroll = () => {
      const w = el.clientWidth;
      if (w < 1) return;
      const i = Math.round(el.scrollLeft / w);
      setActive(Math.min(Math.max(0, i), n - 1));
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [n, urlFingerprint]);

  if (n === 0) {
    return emptyFallback;
  }

  return (
    <div className="relative h-full w-full select-none">
      <div
        ref={scrollerRef}
        className="flex h-full w-full snap-x snap-mandatory overflow-x-auto overflow-y-hidden [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
        style={{
          touchAction: "pan-x",
          WebkitOverflowScrolling: "touch",
        }}
        aria-roledescription="carousel"
        aria-label="Part photos"
      >
        {urls.map((url, i) => (
          <div
            key={`${url}-${i}`}
            className="h-full w-full shrink-0 snap-center snap-always"
            style={{ minWidth: "100%", maxWidth: "100%" }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={url} alt="" className="h-full w-full object-cover" draggable={false} />
          </div>
        ))}
      </div>
      {n > 1 && (
        <>
          <button
            type="button"
            aria-label="Previous photo"
            className="absolute left-0.5 top-1/2 z-[1] -translate-y-1/2 rounded-md px-1 py-2 text-lg font-bold leading-none text-white opacity-90 transition hover:opacity-100"
            style={{
              background: "linear-gradient(90deg, rgba(0,0,0,0.55) 0%, transparent 100%)",
              textShadow: "0 1px 2px rgba(0,0,0,0.8)",
            }}
            onClick={(e) => {
              e.stopPropagation();
              scrollToIndex(active - 1);
            }}
          >
            ‹
          </button>
          <button
            type="button"
            aria-label="Next photo"
            className="absolute right-0.5 top-1/2 z-[1] -translate-y-1/2 rounded-md px-1 py-2 text-lg font-bold leading-none text-white opacity-90 transition hover:opacity-100"
            style={{
              background: "linear-gradient(270deg, rgba(0,0,0,0.55) 0%, transparent 100%)",
              textShadow: "0 1px 2px rgba(0,0,0,0.8)",
            }}
            onClick={(e) => {
              e.stopPropagation();
              scrollToIndex(active + 1);
            }}
          >
            ›
          </button>
          <div
            className="pointer-events-auto absolute bottom-1 left-0 right-0 z-[1] flex justify-center gap-1.5"
            role="tablist"
            aria-label="Photo indicators"
          >
            {urls.map((_, i) => (
              <button
                key={i}
                type="button"
                role="tab"
                aria-selected={i === active}
                aria-label={`Show photo ${i + 1} of ${n}`}
                className="h-1.5 rounded-full transition-all duration-200"
                style={{
                  width: i === active ? 14 : 5,
                  background: i === active ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.45)",
                  boxShadow: "0 0 0 1px rgba(0,0,0,0.25)",
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  scrollToIndex(i);
                }}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function locationLine(part, vehicle) {
  if (part.use_vehicle_location && vehicle?.location_state && vehicle?.location_zip) {
    return `${vehicle.location_state} ${vehicle.location_zip}`;
  }
  if (part.location_note) return part.location_note;
  return "Location not set";
}

function returnPolicyStyle(policy) {
  if (policy === "green")  return { background: "rgba(34,197,94,0.12)",  border: "1px solid rgba(34,197,94,0.25)",  color: "#4ade80" };
  if (policy === "yellow") return { background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.25)", color: "#fbbf24" };
  return { background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)", color: "#f87171" };
}

const selectStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "6px 10px",
  fontSize: 13,
  width: "100%",
  outline: "none",
  fontFamily: "var(--ff-body)",
};

const inputStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "6px 10px",
  fontSize: 13,
  width: "100%",
  outline: "none",
  fontFamily: "var(--ff-body)",
};

function syncFormFromPart(part, setters) {
  const { setPrice, setCondition, setConditionDesc, setReturnPolicy, setListingState } = setters;
  setPrice(part.price != null && part.price !== "" ? String(part.price) : "");
  setCondition(part.condition_draft || "");
  setConditionDesc(part.condition_description || "");
  setReturnPolicy(part.return_policy || "green");
  setListingState(part.listing_state || "draft");
}

export function PartListingCard({ part, vehicle, disabled, onSave, onDelete, onUploadPhoto, selected, onToggleSelected }) {
  const toast = useToast();
  const [editing, setEditing]           = useState(false);
  const [price, setPrice]               = useState("");
  const [condition, setCondition]       = useState("");
  const [conditionDesc, setConditionDesc] = useState("");
  const [returnPolicy, setReturnPolicy] = useState("green");
  const [listingState, setListingState] = useState("draft");
  const [saving, setSaving]             = useState(false);
  const [uploading, setUploading]       = useState(false);

  useEffect(() => {
    syncFormFromPart(part, { setPrice, setCondition, setConditionDesc, setReturnPolicy, setListingState });
  }, [part.id, part.price, part.condition_draft, part.condition_description, part.return_policy, part.listing_state]);

  const galleryUrls = (Array.isArray(part.image_urls) ? part.image_urls : []).filter(Boolean);
  const effective = part.listing_state_effective || part.listing_state;
  const isExpiredBuyNow = part.listing_state === "buy_now" && effective === "draft";

  const policyShort = RETURN_POLICIES.find((r) => r.value === returnPolicy)?.short || returnPolicy;
  const priceDisplay =
    part.price != null && part.price !== ""
      ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(part.price))
      : "—";

  function cancelEdit() {
    syncFormFromPart(part, { setPrice, setCondition, setConditionDesc, setReturnPolicy, setListingState });
    setEditing(false);
  }

  async function handleSave(e) {
    e.preventDefault();
    if (listingState === "buy_now") {
      const trimmed = price.trim();
      if (!trimmed) {
        toast.error("Buy now requires a price greater than zero.");
        return;
      }
      const n = Number(trimmed);
      if (!Number.isFinite(n) || n <= 0) {
        toast.error("Buy now requires a price greater than zero.");
        return;
      }
      if (!condition) {
        toast.error("Buy now requires a condition.");
        return;
      }
    }
    setSaving(true);
    try {
      const payload = {
        listing_state: listingState,
        price: price.trim() === "" ? null : price,
        condition_draft: condition || null,
        condition_description: conditionDesc,
        return_policy: returnPolicy,
      };
      await onSave(part.id, payload);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  async function handleUploadFile(file) {
    if (!file || typeof onUploadPhoto !== "function") return;
    setUploading(true);
    try { await onUploadPhoto(part.id, file); }
    finally { setUploading(false); }
  }

  return (
    <div
      className="group"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: "12px",
        transition: "border-color 0.15s, box-shadow 0.15s",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = "rgba(255,92,26,0.3)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = "var(--border)";
      }}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
        {/* Image gallery — swipe / scroll-snap; arrows + dots when multiple */}
        <div
          className="relative h-24 w-full overflow-hidden lg:h-[5.75rem] lg:w-28 lg:flex-none"
          style={{ borderRadius: "var(--radius-md)", background: "var(--bg-elevated)" }}
        >
          <PartImageSlider
            urls={galleryUrls}
            emptyFallback={(
              <div className="flex h-full w-full items-center justify-center text-4xl" style={{ opacity: 0.7 }}>
                {categoryEmoji(part)}
              </div>
            )}
          />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {typeof onToggleSelected === "function" && (
              <input
                type="checkbox"
                checked={!!selected}
                onChange={() => onToggleSelected(part.id)}
                aria-label="Select part"
                style={{ width: 15, height: 15, accentColor: "var(--primary)", cursor: "pointer" }}
              />
            )}
            <h3 className="truncate text-sm font-semibold" style={{ color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
              {part.label}
            </h3>

            {listingState === "draft" && (
              <span style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                Draft
              </span>
            )}
            {listingState === "buy_now" && !isExpiredBuyNow && (
              <span style={{ background: "var(--primary)", borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 700, color: "#fff", fontFamily: "var(--ff-display)" }}>
                Buy now
              </span>
            )}
            {isExpiredBuyNow && (
              <span style={{ background: "rgba(245,158,11,0.15)", border: "1px solid rgba(245,158,11,0.3)", borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 600, color: "#fbbf24", fontFamily: "var(--ff-display)" }}>
                Expired
              </span>
            )}
            {["sold", "unavailable", "sold_elsewhere"].includes(listingState) && (
              <span style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                {LISTING_STATES.find((s) => s.value === listingState)?.label || listingState}
              </span>
            )}
            <span style={{ ...returnPolicyStyle(returnPolicy), borderRadius: "999px", padding: "1px 8px", fontSize: 11, fontWeight: 500 }}>
              {policyShort}
            </span>
          </div>

          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5" style={{ fontSize: 11, color: "var(--text-muted)" }}>
            <span>{part.part_family?.category?.name} · {part.part_family?.name}</span>
            <span>
              <span style={{ color: "var(--text-muted)" }}>Ship from:</span>{" "}
              <span style={{ color: "var(--text-secondary)" }}>{locationLine(part, vehicle)}</span>
            </span>
            {!editing && (
              <span className="price-mono" style={{ color: "var(--primary-bright)", fontSize: 12 }}>{priceDisplay}</span>
            )}
            {part.buy_now_expires_at && part.listing_state === "buy_now" && !isExpiredBuyNow && (
              <span>Buy Now ends: {new Date(part.buy_now_expires_at).toLocaleString()}</span>
            )}
          </div>

          {part.condition_description && !editing && (
            <p className="mt-1 line-clamp-2" style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {part.condition_description}
            </p>
          )}

          {isExpiredBuyNow && (
            <p className="mt-2 rounded-lg px-2 py-1.5" style={{ fontSize: 12, background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.2)", color: "#fbbf24" }}>
              Buy Now expired — renew Buy Now or set to Draft.
            </p>
          )}

          {!editing && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={disabled}
                onClick={() => setEditing(true)}
                style={{
                  borderRadius: "var(--radius-md)", padding: "6px 14px",
                  fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)",
                  background: "var(--bg-elevated)", border: "1px solid var(--border)",
                  color: "var(--text-primary)", cursor: "pointer", transition: "all 0.12s",
                  opacity: disabled ? 0.5 : 1,
                }}
                onMouseEnter={e => { if (!disabled) e.currentTarget.style.borderColor = "var(--border-strong)"; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; }}
              >
                Edit listing
              </button>
              {typeof onDelete === "function" && (
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    const ok = window.confirm(`Delete "${part.label}"?`);
                    if (ok) onDelete(part.id);
                  }}
                  style={{
                    borderRadius: "var(--radius-md)", padding: "6px 14px",
                    fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)",
                    background: "transparent", border: "1px solid rgba(239,68,68,0.3)",
                    color: "#f87171", cursor: "pointer", transition: "all 0.12s",
                    opacity: disabled ? 0.5 : 1,
                  }}
                  onMouseEnter={e => { if (!disabled) { e.currentTarget.style.background = "rgba(239,68,68,0.08)"; e.currentTarget.style.borderColor = "rgba(239,68,68,0.5)"; } }}
                  onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = "rgba(239,68,68,0.3)"; }}
                >
                  Delete
                </button>
              )}
            </div>
          )}

          {editing && (
            <form onSubmit={handleSave} className="mt-3">
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
                <label className="xl:col-span-1">
                  <span style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                    Price (USD)
                  </span>
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder="0.00"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    disabled={disabled || saving}
                    style={inputStyle}
                  />
                </label>

                <label className="xl:col-span-1">
                  <span style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                    Condition
                  </span>
                  <select
                    value={condition}
                    onChange={(e) => setCondition(e.target.value)}
                    disabled={disabled || saving}
                    style={selectStyle}
                  >
                    <option value="">—</option>
                    {CONDITIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                  </select>
                </label>

                <label className="xl:col-span-3">
                  <span style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                    Condition notes
                  </span>
                  <input
                    type="text"
                    value={conditionDesc}
                    onChange={(e) => setConditionDesc(e.target.value)}
                    disabled={disabled || saving}
                    placeholder="e.g. Tested working; minor scratches"
                    style={inputStyle}
                  />
                </label>

                <label className="xl:col-span-2">
                  <span style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                    Return policy
                  </span>
                  <select
                    value={returnPolicy}
                    onChange={(e) => setReturnPolicy(e.target.value)}
                    disabled={disabled || saving}
                    style={selectStyle}
                  >
                    {RETURN_POLICIES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                </label>

                <label className="xl:col-span-1">
                  <span style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-muted)", fontFamily: "var(--ff-display)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                    State
                  </span>
                  <select
                    value={listingState}
                    onChange={(e) => setListingState(e.target.value)}
                    disabled={disabled || saving}
                    style={selectStyle}
                  >
                    {LISTING_STATES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </label>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                <label
                  style={{
                    display: "inline-flex", alignItems: "center", gap: 6,
                    borderRadius: "var(--radius-md)", padding: "7px 14px",
                    fontSize: 12, fontWeight: 500, fontFamily: "var(--ff-display)",
                    border: "1px dashed var(--border)", color: "var(--text-muted)",
                    cursor: "pointer", transition: "all 0.12s",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(255,92,26,0.4)"; e.currentTarget.style.color = "var(--primary)"; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-muted)"; }}
                >
                  {uploading ? "Uploading…" : "Upload photo(s)"}
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    disabled={disabled || saving || uploading}
                    className="sr-only"
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []);
                      e.target.value = "";
                      (async () => {
                        for (const f of files) {
                          // eslint-disable-next-line no-await-in-loop
                          await handleUploadFile(f);
                        }
                      })();
                    }}
                  />
                </label>
                <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Multiple files ok.</span>
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                {part.is_damaged ? (
                  <p style={{ fontSize: 12, fontWeight: 500, color: "#fbbf24" }}>Marked damaged</p>
                ) : <span />}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={disabled || saving}
                    onClick={cancelEdit}
                    style={{
                      borderRadius: "var(--radius-md)", padding: "8px 16px",
                      fontSize: 13, fontWeight: 500, fontFamily: "var(--ff-display)",
                      background: "var(--bg-elevated)", border: "1px solid var(--border)",
                      color: "var(--text-secondary)", cursor: "pointer",
                      opacity: (disabled || saving) ? 0.5 : 1,
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={disabled || saving}
                    className="btn-forge"
                    style={{ padding: "8px 20px", fontSize: 13, opacity: (disabled || saving) ? 0.6 : 1 }}
                  >
                    {saving ? "Saving…" : "Save listing"}
                  </button>
                </div>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
