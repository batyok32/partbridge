"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { MAKES, MODELS_BY_MAKE } from "@/lib/cars-data";
import { PARTS } from "@/lib/parts-data";
import { returnPolicyBrief } from "@/lib/return-policy";
import { PartsPickerMulti } from "@/components/PartsPickerMulti";

const YEARS = Array.from({ length: new Date().getFullYear() - 1979 }, (_, i) =>
  String(new Date().getFullYear() - i)
);

const STORAGE_KEY = "partbridge_browse_prefs_v2";
const RESULTS_CACHE_KEY = "partbridge_browse_results_v1";
const CACHE_TTL_MS = 30 * 60 * 1000; // 30 min
const PARTS_PER_PAGE = 120;
const DONORS_PER_LOAD = 8;

/**
 * Compact page control: first pages, ellipsis, current neighborhood, ellipsis, last pages.
 * @param {number} totalPages
 * @param {number} currentPage0  zero-based current page
 * @returns {(number | "ellipsis")[]}
 */
function partsPaginationEntries(totalPages, currentPage0) {
  if (totalPages <= 1) return [];
  if (totalPages <= 9) {
    return Array.from({ length: totalPages }, (_, i) => i);
  }
  const pages = new Set([0, totalPages - 1]);
  for (let i = currentPage0 - 1; i <= currentPage0 + 1; i++) {
    if (i >= 0 && i < totalPages) pages.add(i);
  }
  for (let i = 0; i < 2; i++) pages.add(i);
  for (let i = totalPages - 2; i < totalPages; i++) pages.add(i);

  const sorted = [...pages].sort((a, b) => a - b);
  const out = [];
  let prev = -2;
  for (const p of sorted) {
    if (prev >= 0 && p - prev > 1) out.push("ellipsis");
    out.push(p);
    prev = p;
  }
  return out;
}

/** Case- and whitespace-insensitive match for dropdown filters vs API strings. */
function browseStrEq(a, b) {
  const x = (a ?? "").toString().trim().toLowerCase();
  const y = (b ?? "").toString().trim().toLowerCase();
  return x === y;
}

function browsePartHasPhoto(p) {
  const urls = p?.image_urls;
  if (Array.isArray(urls)) {
    for (const u of urls) {
      if (!u) continue;
      if (typeof u === "string" && u.trim()) return true;
      if (typeof u === "object" && u.url && String(u.url).trim()) return true;
    }
  }
  if (p?.card_image_url && String(p.card_image_url).trim()) return true;
  const vp = p?.vehicle_public || {};
  const g = vp.photo_urls;
  if (Array.isArray(g)) {
    for (const ph of g) {
      if (!ph) continue;
      if (typeof ph === "string" && ph.trim()) return true;
      if (typeof ph === "object" && ph.url && String(ph.url).trim())
        return true;
    }
  }
  if (vp.primary_photo_url && String(vp.primary_photo_url).trim()) return true;
  return false;
}

/** "No damage" = part not flagged damaged and donor vehicle not flagged damaged. */
function browsePartPassesNoDamage(p) {
  const d = p?.is_damaged;
  const partDamaged = d === true || d === "true" || d === 1;
  const veh = p?.vehicle_public?.has_damage;
  const vehDamaged = veh === true || veh === "true" || veh === 1;
  return !partDamaged && !vehDamaged;
}

function browseCarHasPhoto(c) {
  const g = c?.photo_urls;
  if (Array.isArray(g) && g.length > 0) {
    for (const ph of g) {
      if (!ph) continue;
      if (typeof ph === "string" && ph.trim()) return true;
      if (typeof ph === "object" && ph.url && String(ph.url).trim())
        return true;
    }
  }
  return Boolean(c?.primary_photo_url && String(c.primary_photo_url).trim());
}

function loadResultsCache() {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(RESULTS_CACHE_KEY);
    if (!raw) return null;
    const d = JSON.parse(raw);
    if (Date.now() - (d.timestamp || 0) > CACHE_TTL_MS) return null;
    return d;
  } catch {
    return null;
  }
}

function saveResultsCache(searchKey, payload) {
  try {
    sessionStorage.setItem(
      RESULTS_CACHE_KEY,
      JSON.stringify({ searchKey, ...payload, timestamp: Date.now() })
    );
  } catch {
    /* ignore */
  }
}

// ─── Inline SVG icons ────────────────────────────────────────────────────────

const S = (p) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={p.className}
    aria-hidden
  >
    {p.children}
  </svg>
);
const IcSearch = ({ className }) => (
  <S className={className}>
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.35-4.35" />
  </S>
);
const IcChevDown = ({ className }) => (
  <S className={className}>
    <path d="m6 9 6 6 6-6" />
  </S>
);
const IcX = ({ className }) => (
  <S className={className}>
    <path d="M18 6 6 18m0-12 12 12" />
  </S>
);
const IcZap = ({ className }) => (
  <S className={className}>
    <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
  </S>
);
const IcPin = ({ className }) => (
  <S className={className}>
    <path d="M12 2a7 7 0 0 1 7 7c0 4.97-7 13-7 13S5 13.97 5 9a7 7 0 0 1 7-7z" />
    <circle cx="12" cy="9" r="2.5" />
  </S>
);

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Format AI fitment chip: Make Model · year_start–year_end (inclusive). */
function formatAiVehicleChip(c) {
  const name = [c.make, c.model, c.trim].filter(Boolean).join(" ");
  const rs = c.year_range_start ?? c.year;
  const re = c.year_range_end ?? c.year;
  if (rs != null && re != null) {
    const yr = rs === re ? String(rs) : `${rs}–${re}`;
    return `${name} · ${yr}`;
  }
  return name || "—";
}

function loadSaved() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function savePrefs(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // ignore
  }
}

// ─── VehiclePhotoGallery ──────────────────────────────────────────────────────

/**
 * Swipeable gallery for donor vehicle cards.
 * - First EAGER_COUNT photos load immediately; the rest load lazily when reached.
 * - Supports touch swipe (mobile) and arrow button navigation (desktop).
 */
const EAGER_COUNT = 2;

function VehiclePhotoGallery({ photos, alt = "" }) {
  const urls = photos?.length
    ? photos.map((p) => (typeof p === "string" ? p : p.url)).filter(Boolean)
    : [];
  const [idx, setIdx] = useState(0);
  const [loaded, setLoaded] = useState(
    () =>
      new Set(
        Array.from({ length: Math.min(EAGER_COUNT, urls.length) }, (_, i) => i)
      )
  );
  const touchStart = useRef(null);

  if (urls.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center text-xs text-zinc-400">
        No photo
      </div>
    );
  }

  function go(next) {
    const n = (next + urls.length) % urls.length;
    setIdx(n);
    // Unlock loading for the next photo ahead too
    setLoaded((prev) => {
      const s = new Set(prev);
      s.add(n);
      if (n + 1 < urls.length) s.add(n + 1);
      return s;
    });
  }

  function onTouchStart(e) {
    touchStart.current = e.touches[0].clientX;
  }
  function onTouchEnd(e) {
    if (touchStart.current == null) return;
    const dx = e.changedTouches[0].clientX - touchStart.current;
    touchStart.current = null;
    if (Math.abs(dx) < 30) return;
    go(dx < 0 ? idx + 1 : idx - 1);
  }

  return (
    <div
      className="relative h-full w-full overflow-hidden"
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      {urls.map(
        (url, i) =>
          loaded.has(i) && (
            <img
              key={url}
              src={url}
              alt={alt}
              loading={i < EAGER_COUNT ? "eager" : "lazy"}
              className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-200 ${
                i === idx ? "opacity-100" : "opacity-0 pointer-events-none"
              }`} // eslint-disable-line @next/next/no-img-element
            />
          )
      )}

      {/* Dot indicators */}
      {urls.length > 1 && (
        <div className="absolute bottom-1 left-0 right-0 flex justify-center gap-1">
          {urls.map((_, i) => (
            <span
              key={i}
              className={`h-1 w-1 rounded-full transition-colors ${
                i === idx ? "bg-white" : "bg-white/40"
              }`}
            />
          ))}
        </div>
      )}

      {/* Prev / Next arrows */}
      {urls.length > 1 && (
        <>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              go(idx - 1);
            }}
            className="absolute left-1 top-1/2 -translate-y-1/2 rounded-full bg-black/30 p-0.5 text-white hover:bg-black/60"
            aria-label="Previous photo"
          >
            <svg viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
              <path
                d="M10 3l-5 5 5 5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              go(idx + 1);
            }}
            className="absolute right-1 top-1/2 -translate-y-1/2 rounded-full bg-black/30 p-0.5 text-white hover:bg-black/60"
            aria-label="Next photo"
          >
            <svg viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
              <path
                d="M6 3l5 5-5 5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          </button>
        </>
      )}
    </div>
  );
}

// ─── PartCard ─────────────────────────────────────────────────────────────────

function PartCard({ part, buyerZip, buyerMake, buyerModel, user, onMessage }) {
  const vp = part.vehicle_public || {};
  const vehicleName = [vp.year, vp.make, vp.model, vp.trim]
    .filter(Boolean)
    .join(" ");

  const partPhotos = (part.image_urls || []).filter(Boolean).map((url) => ({
    url: typeof url === "string" ? url : url.url,
    kind: "part",
  }));
  const carPhotos = (vp.photo_urls || [])
    .filter(Boolean)
    .map((p) => ({ url: typeof p === "string" ? p : p.url, kind: "car" }));
  const allPhotos = [...partPhotos, ...carPhotos];
  if (!allPhotos.length && vp.primary_photo_url)
    allPhotos.push({ url: vp.primary_photo_url, kind: "car" });

  const shipping = part.shipping_preview || {};
  const shippingOptions = shipping.shipping_options || [];
  const standardOption = shippingOptions.find((o) => o.code === "standard");

  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState(null);
  const [cartDone, setCartDone] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const [cartNotes, setCartNotes] = useState("");
  const [cartThenGo, setCartThenGo] = useState(false);

  async function doAddToCart(thenGo = false, notes = "") {
    if (!user) {
      window.location.href = `/login?next=/browse`;
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      const trimmed = (notes || "").trim();
      await apiFetch("/cart/", {
        method: "POST",
        body: JSON.stringify({
          vehicle_part_id: part.id,
          quantity: 1,
          shipping_mode: "standard",
          buyer_zip: buyerZip.trim() || undefined,
          ...(trimmed ? { buyer_notes: trimmed } : {}),
        }),
      });
      setCartDone(true);
      setCartOpen(false);
      if (thenGo) window.location.href = "/cart";
    } catch (err) {
      setAddError(
        err instanceof ApiError ? err.message : "Could not add to cart."
      );
    } finally {
      setAdding(false);
    }
  }

  const specBadge =
    "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px]";
  const specBadgeStyle = {
    background: "var(--bg-elevated)",
    color: "var(--text-secondary)",
    border: "1px solid var(--border)",
  };

  return (
    <article
      className="flex overflow-hidden rounded-[14px] transition-all duration-200"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
      }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.borderColor = "var(--border-strong)")
      }
      onMouseLeave={(e) =>
        (e.currentTarget.style.borderColor = "var(--border)")
      }
    >
      {/* Photo */}
      <div
        className="relative w-36 shrink-0 sm:w-48"
        style={{ background: "var(--bg-elevated)" }}
      >
        <VehiclePhotoGallery photos={allPhotos} alt={part.label} />
      </div>

      {/* Info */}
      <div className="flex min-w-0 flex-1 flex-col justify-between p-3 sm:p-4">
        <div>
          {/* Label + price */}
          <div className="flex items-start justify-between gap-2">
            <p
              className="text-sm font-semibold leading-snug"
              style={{
                fontFamily: "var(--ff-display)",
                color: "var(--text-primary)",
              }}
            >
              {part.label}
            </p>
            {part.price != null && (
              <span
                className="shrink-0 font-bold"
                style={{
                  fontFamily: "var(--ff-mono)",
                  fontSize: 14,
                  color: "var(--primary)",
                }}
              >
                ${Number(part.price).toFixed(2)}
              </span>
            )}
          </div>

          {/* Badges */}
          <div className="mt-1.5 flex flex-wrap gap-1">
            <span
              className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
              style={{
                background: "var(--primary-muted)",
                color: "var(--primary-bright)",
                border: "1px solid rgba(255,92,26,0.2)",
              }}
            >
              Buy Now
            </span>
            {part.condition_draft && (
              <span
                className="rounded-full px-2 py-0.5 text-[11px] font-medium"
                style={{
                  background: "var(--bg-elevated)",
                  color: "var(--text-secondary)",
                  border: "1px solid var(--border)",
                }}
              >
                {part.condition_draft}
              </span>
            )}
            {part.is_damaged && (
              <span
                className="rounded-full px-2 py-0.5 text-[11px] font-medium"
                style={{
                  background: "rgba(245,158,11,0.1)",
                  color: "var(--warning)",
                  border: "1px solid rgba(245,158,11,0.2)",
                }}
              >
                Damaged
              </span>
            )}
          </div>

          {/* Vehicle + specs */}
          {vehicleName && (
            <div className="mt-1.5">
              <Link
                href={`/browse/vehicles/${vp.vehicle_id}`}
                className="text-xs font-medium transition-colors"
                style={{ color: "var(--text-muted)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.color = "var(--primary)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "var(--text-muted)")
                }
              >
                {vehicleName}
              </Link>
              <div className="mt-1 flex flex-wrap gap-1">
                {vp.color && (
                  <span className={specBadge} style={specBadgeStyle}>
                    <span
                      className="font-semibold"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Color
                    </span>
                    {vp.color}
                  </span>
                )}
                {vp.engine && (
                  <span className={specBadge} style={specBadgeStyle}>
                    <span
                      className="font-semibold"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Engine
                    </span>
                    {vp.engine}
                  </span>
                )}
                {vp.transmission && (
                  <span className={specBadge} style={specBadgeStyle}>
                    <span
                      className="font-semibold"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Trans.
                    </span>
                    {vp.transmission}
                  </span>
                )}
                {vp.drivetrain && (
                  <span className={specBadge} style={specBadgeStyle}>
                    <span
                      className="font-semibold"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Drive
                    </span>
                    {vp.drivetrain}
                  </span>
                )}
                {(vp.location_state || vp.location_zip_masked) && (
                  <span className={specBadge} style={specBadgeStyle}>
                    <IcPin className="h-3 w-3 shrink-0" />
                    {[vp.location_state, vp.location_zip_masked]
                      .filter(Boolean)
                      .join(" ")}
                  </span>
                )}
                {vp.has_damage && (
                  <span
                    className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium"
                    style={{
                      background: "rgba(245,158,11,0.1)",
                      color: "var(--warning)",
                    }}
                  >
                    Vehicle damage
                  </span>
                )}
              </div>
              {vp.seller?.display_name && (
                <div
                  className="mt-1 flex items-center gap-1.5 text-[11px]"
                  style={{ color: "var(--text-muted)" }}
                >
                  <span
                    className="font-medium"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {vp.seller.display_name}
                  </span>
                  {vp.seller.completed_sales > 0 && (
                    <>
                      <span>·</span>
                      <span style={{ color: "var(--success)" }}>
                        {vp.seller.completed_sales} sale
                        {vp.seller.completed_sales !== 1 ? "s" : ""}
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Description */}
          {part.description && (
            <p
              className="mt-1 line-clamp-2 text-xs"
              style={{ color: "var(--text-muted)" }}
            >
              {part.description}
            </p>
          )}

          {/* Shipping one-liner */}
          {shipping.available && standardOption ? (
            <p
              className="mt-1 text-[11px]"
              style={{ color: "var(--text-muted)" }}
            >
              Ship:{" "}
              <span
                className="font-medium"
                style={{ color: "var(--text-secondary)" }}
              >
                ${standardOption.usd}
              </span>
              {shipping.estimate && (
                <span
                  className="ml-1"
                  style={{ color: "var(--text-disabled)" }}
                >
                  · {shipping.estimate}
                </span>
              )}
            </p>
          ) : !buyerZip ? (
            <p
              className="mt-1 text-[11px]"
              style={{ color: "var(--text-disabled)" }}
            >
              Enter ZIP to see shipping.
            </p>
          ) : null}

          {part.return_policy && (
            <p
              className="mt-0.5 text-[11px]"
              style={{ color: "var(--text-muted)" }}
            >
              {returnPolicyBrief(part.return_policy)}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {addError && (
            <p className="w-full text-xs" style={{ color: "var(--danger)" }}>
              {addError}
            </p>
          )}
          {cartDone ? (
            <Link
              href="/cart"
              className="inline-flex items-center gap-1 rounded-[8px] px-3 py-1.5 text-xs font-semibold text-white"
              style={{ background: "var(--primary)" }}
            >
              View cart →
            </Link>
          ) : (
            <>
              <button
                type="button"
                disabled={adding}
                onClick={() => {
                  setCartThenGo(false);
                  setCartNotes("");
                  setCartOpen(true);
                }}
                className="inline-flex items-center gap-1 rounded-[8px] px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-60"
                style={{
                  background: "var(--primary-muted)",
                  color: "var(--primary-bright)",
                  border: "1px solid rgba(255,92,26,0.25)",
                }}
              >
                {adding && !cartOpen && (
                  <span
                    className="h-3 w-3 animate-spin rounded-full border-2"
                    style={{
                      borderColor: "rgba(255,92,26,0.3)",
                      borderTopColor: "var(--primary)",
                    }}
                  />
                )}
                Add to cart
              </button>
              <button
                type="button"
                disabled={adding}
                onClick={() => {
                  setCartThenGo(true);
                  setCartNotes("");
                  setCartOpen(true);
                }}
                className="inline-flex items-center rounded-[8px] px-3 py-1.5 text-xs font-semibold text-white transition-colors disabled:opacity-60"
                style={{ background: "var(--primary)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "var(--primary-bright)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "var(--primary)")
                }
              >
                Buy now
              </button>
            </>
          )}
          <button
            type="button"
            onClick={() => onMessage(part)}
            className="inline-flex items-center gap-1 rounded-[8px] px-3 py-1.5 text-xs font-medium transition-colors"
            style={{
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--border-strong)";
              e.currentTarget.style.color = "var(--text-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.color = "var(--text-muted)";
            }}
          >
            Message
          </button>
        </div>
      </div>

      {cartOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-end justify-center p-4 sm:items-center"
          role="dialog"
          aria-modal
        >
          <div
            className="absolute inset-0 bg-black/70"
            onClick={() => !adding && setCartOpen(false)}
          />
          <div
            className="relative z-10 w-full max-w-md rounded-[16px] p-5 shadow-xl"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
            }}
          >
            <p
              className="text-sm font-semibold"
              style={{
                fontFamily: "var(--ff-display)",
                color: "var(--text-primary)",
              }}
            >
              {cartThenGo ? "Buy now" : "Add to cart"}
            </p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
              {part.label}
            </p>
            <label className="mt-3 block">
              <span
                className="text-xs font-medium"
                style={{ color: "var(--text-secondary)" }}
              >
                Note for the seller{" "}
                <span
                  className="font-normal"
                  style={{ color: "var(--text-muted)" }}
                >
                  (optional)
                </span>
              </span>
              <textarea
                value={cartNotes}
                onChange={(e) => setCartNotes(e.target.value)}
                rows={3}
                placeholder="e.g. Driver side (LH), color, trim, VIN…"
                disabled={adding}
                className="mt-1 w-full resize-none rounded-[8px] px-3 py-2 text-sm focus:outline-none disabled:opacity-60"
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                  fontFamily: "var(--ff-body)",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "var(--primary)";
                  e.target.style.boxShadow = "0 0 0 3px var(--primary-muted)";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "var(--border)";
                  e.target.style.boxShadow = "none";
                }}
              />
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                disabled={adding}
                onClick={() => setCartOpen(false)}
                className="rounded-[8px] px-4 py-2 text-sm font-medium transition-colors"
                style={{
                  border: "1px solid var(--border)",
                  color: "var(--text-secondary)",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={adding}
                onClick={() => void doAddToCart(cartThenGo, cartNotes)}
                className="inline-flex items-center gap-2 rounded-[8px] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                style={{ background: "var(--primary)" }}
              >
                {adding && (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                )}
                {cartThenGo ? "Continue" : "Add to cart"}
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

// ─── PartSelectField ──────────────────────────────────────────────────────────

function PartSelectField({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [aiName, setAiName] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(false);
  const wrapRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target))
        setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 30);
  }, [open]);

  const q = query.trim().toLowerCase();
  const filtered = q ? PARTS.filter((p) => p.toLowerCase().includes(q)) : PARTS;
  const hasMatches = filtered.length > 0;

  // Auto-call AI after 600 ms when no matches
  useEffect(() => {
    if (!q || hasMatches) {
      setAiName(null);
      setAiError(false);
      return;
    }
    if (aiLoading || aiName) return;
    const t = setTimeout(async () => {
      setAiLoading(true);
      setAiError(false);
      try {
        const data = await apiFetch("/browse/normalize-part/", {
          auth: false,
          method: "POST",
          body: JSON.stringify({ raw_name: query.trim() }),
        });
        setAiName(data.normalized_name || query.trim());
      } catch {
        setAiError(true);
      } finally {
        setAiLoading(false);
      }
    }, 600);
    return () => clearTimeout(t);
  }, [q, hasMatches]); // eslint-disable-line react-hooks/exhaustive-deps

  function select(name) {
    onChange(name);
    setOpen(false);
    setQuery("");
    setAiName(null);
  }

  function clear(e) {
    e.stopPropagation();
    onChange("");
    setQuery("");
    setAiName(null);
  }

  return (
    <div ref={wrapRef} className="relative min-w-0 flex-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex h-11 w-full items-center justify-between rounded-[8px] px-3 text-sm focus:outline-none"
        style={{
          background: "var(--bg-elevated)",
          border: `1px solid ${open ? "var(--primary)" : "var(--border)"}`,
          boxShadow: open ? "0 0 0 3px var(--primary-muted)" : "none",
          transition: "border-color 0.15s, box-shadow 0.15s",
        }}
      >
        <span
          className="truncate"
          style={{ color: value ? "var(--text-primary)" : "var(--text-muted)" }}
        >
          {value || "Part name (optional)"}
        </span>
        <span className="ml-2 flex shrink-0 items-center gap-1">
          {value && (
            <span
              role="button"
              onClick={clear}
              className="flex h-4 w-4 items-center justify-center"
              style={{ color: "var(--text-muted)" }}
            >
              <IcX className="h-3 w-3" />
            </span>
          )}
          <IcChevDown
            className="h-4 w-4"
            style={{ color: "var(--text-muted)" }}
          />
        </span>
      </button>

      {open && (
        <div
          className="absolute left-0 right-0 top-[calc(100%+4px)] z-[200] rounded-[12px] shadow-xl overflow-hidden"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
          }}
        >
          <div
            className="p-2"
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            <div className="relative">
              <IcSearch
                className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2"
                style={{ color: "var(--text-muted)" }}
              />
              <input
                ref={inputRef}
                type="text"
                placeholder="Search parts…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setAiName(null);
                  setAiError(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setOpen(false);
                }}
                className="h-9 w-full rounded-[8px] pl-8 pr-3 text-sm focus:outline-none"
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                  fontFamily: "var(--ff-body)",
                }}
              />
            </div>
          </div>
          <ul className="max-h-52 overflow-y-auto py-1" role="listbox">
            {hasMatches ? (
              filtered.map((p) => (
                <li key={p}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => select(p)}
                    className="w-full px-4 py-2 text-left text-sm transition-colors"
                    style={{
                      color: "var(--text-secondary)",
                      fontFamily: "var(--ff-body)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--bg-hover)";
                      e.currentTarget.style.color = "var(--text-primary)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "transparent";
                      e.currentTarget.style.color = "var(--text-secondary)";
                    }}
                  >
                    {p}
                  </button>
                </li>
              ))
            ) : (
              <li
                className="px-4 py-3 text-sm"
                style={{ color: "var(--text-muted)" }}
              >
                No matching parts found.
              </li>
            )}
          </ul>
          {q && !hasMatches && (
            <div
              className="p-2"
              style={{ borderTop: "1px solid var(--border-subtle)" }}
            >
              {aiName ? (
                <button
                  type="button"
                  onClick={() => select(aiName)}
                  className="flex w-full items-center gap-2 rounded-[8px] px-3 py-2 text-left text-sm transition-colors"
                  style={{
                    background: "var(--primary-muted)",
                    color: "var(--primary-bright)",
                    border: "1px solid rgba(255,92,26,0.2)",
                  }}
                >
                  <IcZap className="h-3.5 w-3.5 shrink-0" />
                  <span>Use &ldquo;{aiName}&rdquo;</span>
                </button>
              ) : aiError ? (
                <p
                  className="px-2 py-1.5 text-xs"
                  style={{ color: "var(--text-muted)" }}
                >
                  No match — press Search anyway.
                </p>
              ) : (
                <div
                  className="flex items-center gap-2 px-3 py-2 text-sm"
                  style={{ color: "var(--text-muted)" }}
                >
                  <span
                    className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2"
                    style={{
                      borderColor: "var(--border)",
                      borderTopColor: "var(--primary)",
                    }}
                  />
                  Looking up part…
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

function BrowsePageInner() {
  const { user } = useAuth();
  const toast = useToast();
  const searchParams = useSearchParams();
  const urlSearchFired = useRef(false);

  const [results, setResults] = useState([]);
  const [count, setCount] = useState(0);
  /** Full DB match count from assist API (may exceed `results.length` when response is capped). */
  const [listingsTotalCount, setListingsTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [compatibleVehicles, setCompatibleVehicles] = useState([]);
  const [potentialCars, setPotentialCars] = useState([]);
  const [normalizedPart, setNormalizedPart] = useState("");
  const [aiSource, setAiSource] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const [buyerYear, setBuyerYear] = useState("");
  const [buyerMake, setBuyerMake] = useState("");
  const [buyerModel, setBuyerModel] = useState("");
  const [partNeed, setPartNeed] = useState("");
  const [buyerZip, setBuyerZip] = useState("");
  const [locatingZip, setLocatingZip] = useState(false);
  const [formOpen, setFormOpen] = useState(true);
  const [hydrated, setHydrated] = useState(false);
  const [partsPage, setPartsPage] = useState(0);
  const [donorVisible, setDonorVisible] = useState(DONORS_PER_LOAD);
  const [activeTab, setActiveTab] = useState("cars"); // "parts" | "cars"

  // ── Parts filters / sort ──────────────────────────────────────────────────
  const [partSort, setPartSort] = useState("newest"); // "newest" | "price_asc" | "price_desc"
  const [partFilterNoDamage, setPartFilterNoDamage] = useState(false);
  const [partFilterHasPhotos, setPartFilterHasPhotos] = useState(false);
  const [partFilterEngine, setPartFilterEngine] = useState("");
  const [partFilterColor, setPartFilterColor] = useState("");
  const [partFilterTrans, setPartFilterTrans] = useState("");

  // ── Cars filters / sort ───────────────────────────────────────────────────
  const [carSort, setCarSort] = useState("default"); // "default" | "most_parts"
  const [carFilterNoDamage, setCarFilterNoDamage] = useState(false);
  const [carFilterHasPhotos, setCarFilterHasPhotos] = useState(false);
  const [carFilterEngine, setCarFilterEngine] = useState("");
  const [carFilterColor, setCarFilterColor] = useState("");
  const [carFilterTrans, setCarFilterTrans] = useState("");

  // ── Per-card message modal (parts picker + message) ──────────────────────
  const [msgModal, setMsgModal] = useState(null); // { card, parts, text, sending, sent, error }
  const [selectedVehicleIds, setSelectedVehicleIds] = useState([]);
  const [bulkMsgModal, setBulkMsgModal] = useState(null); // { text, sending, sent, error, count }

  const messageBaseHref = user ? "/inbox" : "/login?next=%2Fbrowse";

  // ── Hydrate from localStorage + restore cached results ────────────────────
  useEffect(() => {
    let year = "",
      make = "",
      model = "",
      part = "",
      zip = "";
    const s = loadSaved();
    if (s) {
      if (s.buyerYear) {
        setBuyerYear(s.buyerYear);
        year = s.buyerYear;
      }
      if (s.buyerMake) {
        setBuyerMake(s.buyerMake);
        make = s.buyerMake;
      }
      if (s.buyerModel) {
        setBuyerModel(s.buyerModel);
        model = s.buyerModel;
      }
      if (s.partNeed) {
        setPartNeed(s.partNeed);
        part = s.partNeed;
      }
      if (s.buyerZip) {
        setBuyerZip(s.buyerZip);
        zip = s.buyerZip;
      }
      if (typeof s.formOpen === "boolean") setFormOpen(s.formOpen);
    }
    // Restore cached results if the search params still match
    const cache = loadResultsCache();
    const cacheKey = [year, make, model, part, zip].join("|");
    if (cache && cache.searchKey === cacheKey) {
      setResults(cache.results ?? []);
      setPotentialCars(cache.potentialCars ?? []);
      setCount(cache.count ?? 0);
      setListingsTotalCount(
        cache.listingsTotalCount ?? cache.count ?? cache.results?.length ?? 0
      );
      setNormalizedPart(cache.normalizedPart ?? "");
      setAiSource(cache.aiSource ?? "");
      setCompatibleVehicles(cache.compatibleVehicles ?? []);
      setHasSearched(true);
      setFormOpen(false);
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    savePrefs({
      buyerYear,
      buyerMake,
      buyerModel,
      partNeed,
      buyerZip,
      formOpen,
    });
  }, [
    hydrated,
    buyerYear,
    buyerMake,
    buyerModel,
    partNeed,
    buyerZip,
    formOpen,
  ]);

  // ── Seed from URL params & auto-search ────────────────────────────────────
  useEffect(() => {
    if (!hydrated || urlSearchFired.current) return;
    const urlYear = searchParams.get("year") || "";
    const urlMake = searchParams.get("make") || "";
    const urlModel = searchParams.get("model") || "";
    const urlPart = searchParams.get("part") || "";
    if (!urlYear && !urlMake && !urlModel && !urlPart) return;
    urlSearchFired.current = true;
    if (urlYear) setBuyerYear(urlYear);
    if (urlMake) setBuyerMake(urlMake);
    if (urlModel) setBuyerModel(urlModel);
    if (urlPart) setPartNeed(urlPart);
    const cacheKey = [
      urlYear,
      urlMake,
      urlModel,
      urlPart,
      buyerZip.trim(),
    ].join("|");
    setTimeout(async () => {
      setLoading(true);
      try {
        const data = await apiFetch("/browse/cars/assist/", {
          auth: false,
          method: "POST",
          body: JSON.stringify({
            buyer_year: urlYear ? Number(urlYear) : undefined,
            buyer_make: urlMake,
            buyer_model: urlModel,
            part_need: urlPart,
            buyer_zip: buyerZip.trim(),
          }),
        });
        applyResult(data, cacheKey);
      } catch (err) {
        if (err instanceof ApiError) toast.error(err.message);
      } finally {
        setLoading(false);
      }
    }, 0);
  }, [hydrated, searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  function applyResult(data, searchKey) {
    const listings = Array.isArray(data.listings) ? data.listings : [];
    const compatible = Array.isArray(data.compatible_vehicles)
      ? data.compatible_vehicles
      : [];
    const totalFromApi = Number(
      data.listings_total_count ?? data.listings_count ?? listings.length
    );
    const payload = {
      results: listings,
      potentialCars: Array.isArray(data.potential_cars)
        ? data.potential_cars
        : [],
      count: Number(data.listings_count ?? listings.length),
      listingsTotalCount: totalFromApi,
      normalizedPart: data.normalized_part_query || "",
      aiSource: data.ai_source || "",
      compatibleVehicles: compatible,
    };
    setResults(payload.results);
    setPotentialCars(payload.potentialCars);
    setCount(payload.count);
    setListingsTotalCount(payload.listingsTotalCount);
    setNormalizedPart(payload.normalizedPart);
    setAiSource(payload.aiSource);
    setCompatibleVehicles(payload.compatibleVehicles);
    setHasSearched(true);
    setPartsPage(0);
    setDonorVisible(DONORS_PER_LOAD);
    setMsgModal(null);
    setSelectedVehicleIds([]);
    setBulkMsgModal(null);
    setPartSort("newest");
    setPartFilterNoDamage(false);
    setPartFilterHasPhotos(false);
    setPartFilterEngine("");
    setPartFilterColor("");
    setPartFilterTrans("");
    setCarSort("default");
    setCarFilterNoDamage(false);
    setCarFilterHasPhotos(false);
    setCarFilterEngine("");
    setCarFilterColor("");
    setCarFilterTrans("");
    // Default tab: parts if we have listings, else cars
    setActiveTab(listings.length > 0 ? "parts" : "cars");
    setFormOpen(false);
    saveResultsCache(searchKey, payload);
  }

  // ── Search ────────────────────────────────────────────────────────────────
  async function handleSearch(e) {
    e.preventDefault();
    if (!buyerMake.trim() && !partNeed.trim()) {
      toast.warning("Please select a make or enter a part name to search.");
      return;
    }
    const cacheKey = [
      buyerYear.trim(),
      buyerMake.trim(),
      buyerModel.trim(),
      partNeed.trim(),
      buyerZip.trim(),
    ].join("|");
    setLoading(true);
    try {
      const data = await apiFetch("/browse/cars/assist/", {
        auth: false,
        method: "POST",
        body: JSON.stringify({
          buyer_year: buyerYear.trim() ? Number(buyerYear) : undefined,
          buyer_make: buyerMake.trim(),
          buyer_model: buyerModel.trim(),
          part_need: partNeed.trim(),
          buyer_zip: buyerZip.trim(),
        }),
      });
      applyResult(data, cacheKey);
    } catch (e2) {
      if (e2 instanceof ApiError) toast.error(e2.message);
    } finally {
      setLoading(false);
    }
  }

  async function detectZip() {
    if (!navigator.geolocation) {
      toast.warning("Geolocation not supported.");
      return;
    }
    setLocatingZip(true);
    try {
      const pos = await new Promise((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 20000,
          maximumAge: 0,
        })
      );
      const { latitude: lat, longitude: lon } = pos.coords;
      try {
        const data = await apiFetch(
          `/browse/reverse-zip/?lat=${encodeURIComponent(
            lat
          )}&lon=${encodeURIComponent(lon)}`,
          { auth: false }
        );
        if (data?.zip) {
          setBuyerZip(String(data.zip));
          return;
        }
      } catch {
        /* try client fallback */
      }
      const res = await fetch(
        `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=en`
      );
      const j = await res.json();
      const m = String(j.postcode || j.postalCode || j.zipcode || "").match(
        /(\d{5})/
      );
      if (m) {
        setBuyerZip(m[1]);
        return;
      }
      toast.warning("Could not detect ZIP. Enter it manually.");
    } catch {
      toast.warning("Location permission denied. Enter ZIP manually.");
    } finally {
      setLocatingZip(false);
    }
  }

  // ── Dynamic filter options derived from results ───────────────────────────
  const uniq = (arr) =>
    [
      ...new Set(
        arr.map((x) => (x ?? "").toString().trim()).filter((s) => s.length > 0)
      ),
    ].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  const partEngineOpts = uniq(results.map((p) => p.vehicle_public?.engine));

  const partColorOpts = uniq(results.map((p) => p.vehicle_public?.color));
  const partTransOpts = uniq(
    results.map((p) => p.vehicle_public?.transmission)
  );
  const carEngineOpts = uniq(potentialCars.map((c) => c.engine));
  const carColorOpts = uniq(potentialCars.map((c) => c.color));
  const carTransOpts = uniq(potentialCars.map((c) => c.transmission));

  // ── Filtered + sorted parts ───────────────────────────────────────────────
  const filteredParts = useMemo(() => {
    const filtered = results.filter((p) => {
      const vp = p.vehicle_public || {};
      if (partFilterNoDamage && !browsePartPassesNoDamage(p)) return false;
      if (partFilterHasPhotos && !browsePartHasPhoto(p)) return false;
      if (partFilterEngine && !browseStrEq(vp.engine, partFilterEngine))
        return false;
      if (partFilterColor && !browseStrEq(vp.color, partFilterColor))
        return false;
      if (partFilterTrans && !browseStrEq(vp.transmission, partFilterTrans))
        return false;
      return true;
    });
    const copy = [...filtered];
    copy.sort((a, b) => {
      if (partSort === "price_asc")
        return (Number(a.price) || 0) - (Number(b.price) || 0);
      if (partSort === "price_desc")
        return (Number(b.price) || 0) - (Number(a.price) || 0);
      const ta = a.updated_at ? new Date(a.updated_at).getTime() : 0;
      const tb = b.updated_at ? new Date(b.updated_at).getTime() : 0;
      if (tb !== ta) return tb - ta;
      return (Number(b.id) || 0) - (Number(a.id) || 0);
    });
    return copy;
  }, [
    results,
    partSort,
    partFilterNoDamage,
    partFilterHasPhotos,
    partFilterEngine,
    partFilterColor,
    partFilterTrans,
  ]);

  const partsPageMax = Math.max(
    0,
    Math.ceil(filteredParts.length / PARTS_PER_PAGE) - 1
  );
  const safePartsPage = Math.min(partsPage, partsPageMax);

  useEffect(() => {
    setPartsPage((p) => (p > partsPageMax ? partsPageMax : p));
  }, [filteredParts.length, partsPageMax]);

  // ── Filtered + sorted cars ────────────────────────────────────────────────
  const filteredCars = useMemo(() => {
    return potentialCars
      .filter((c) => {
        const vehDamaged =
          c.has_damage === true ||
          c.has_damage === "true" ||
          c.has_damage === 1;
        if (carFilterNoDamage && vehDamaged) return false;
        if (carFilterHasPhotos && !browseCarHasPhoto(c)) return false;
        if (carFilterEngine && !browseStrEq(c.engine, carFilterEngine))
          return false;
        if (carFilterColor && !browseStrEq(c.color, carFilterColor))
          return false;
        if (carFilterTrans && !browseStrEq(c.transmission, carFilterTrans))
          return false;
        return true;
      })
      .sort((a, b) => {
        if (carSort === "most_parts")
          return (b.matching_parts_count || 0) - (a.matching_parts_count || 0);
        return 0;
      });
  }, [
    potentialCars,
    carFilterNoDamage,
    carFilterHasPhotos,
    carFilterEngine,
    carFilterColor,
    carFilterTrans,
    carSort,
  ]);

  const zipOk = Boolean(buyerZip.trim());
  const searchSummary = [
    buyerYear,
    buyerMake,
    buyerModel,
    partNeed || "any part",
    buyerZip && `ZIP ${buyerZip}`,
  ]
    .filter(Boolean)
    .join(" · ");

  // ── Render ────────────────────────────────────────────────────────────────
  const selectStyle = {
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    color: "var(--text-primary)",
    fontFamily: "var(--ff-body)",
    outline: "none",
    transition: "border-color 0.15s",
  };

  return (
    <div className="mx-auto min-h-screen max-w-7xl px-4 py-10 sm:px-6">
      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div>
        <span className="section-label">Browse</span>
        <h1 className="mt-2 heading-display text-3xl sm:text-4xl">
          Find parts that fit
        </h1>
      </div>

      {/* ── Search bar ───────────────────────────────────────────────────── */}
      <div className="mt-6">
        {formOpen ? (
          <form onSubmit={handleSearch}>
            <div
              className="flex flex-col gap-2 rounded-[14px] p-2 sm:flex-row sm:items-stretch"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              {/* Year */}
              <div className="relative min-w-0 sm:max-w-[100px]">
                <select
                  value={buyerYear}
                  onChange={(e) => setBuyerYear(e.target.value)}
                  className="h-11 w-full appearance-none rounded-[8px] px-3 pr-8 text-sm focus:outline-none"
                  style={selectStyle}
                  onFocus={(e) =>
                    (e.target.style.borderColor = "var(--primary)")
                  }
                  onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                >
                  <option value="">Year</option>
                  {YEARS.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
                <IcChevDown
                  className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2"
                  style={{ color: "var(--text-muted)" }}
                />
              </div>

              {/* Make */}
              <div className="relative min-w-0 flex-1">
                <select
                  value={buyerMake}
                  onChange={(e) => {
                    setBuyerMake(e.target.value);
                    setBuyerModel("");
                  }}
                  className="h-11 w-full appearance-none rounded-[8px] px-3 pr-8 text-sm focus:outline-none"
                  style={selectStyle}
                  onFocus={(e) =>
                    (e.target.style.borderColor = "var(--primary)")
                  }
                  onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                >
                  <option value="">Make</option>
                  {MAKES.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                <IcChevDown
                  className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2"
                  style={{ color: "var(--text-muted)" }}
                />
              </div>

              {/* Model */}
              <div className="relative min-w-0 flex-1">
                <select
                  value={buyerModel}
                  onChange={(e) => setBuyerModel(e.target.value)}
                  disabled={!buyerMake}
                  className="h-11 w-full appearance-none rounded-[8px] px-3 pr-8 text-sm focus:outline-none disabled:opacity-40"
                  style={selectStyle}
                  onFocus={(e) =>
                    (e.target.style.borderColor = "var(--primary)")
                  }
                  onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                >
                  <option value="">Model</option>
                  {(MODELS_BY_MAKE[buyerMake] || []).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                <IcChevDown
                  className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2"
                  style={{ color: "var(--text-muted)" }}
                />
              </div>

              {/* Part */}
              <PartSelectField value={partNeed} onChange={setPartNeed} />

              {/* ZIP */}
              <div
                className="flex h-11 min-w-0 flex-1 items-center rounded-[8px] sm:max-w-[130px]"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  transition: "border-color 0.15s",
                }}
                onFocusCapture={(e) =>
                  (e.currentTarget.style.borderColor = "var(--primary)")
                }
                onBlurCapture={(e) =>
                  (e.currentTarget.style.borderColor = "var(--border)")
                }
              >
                <input
                  value={buyerZip}
                  onChange={(e) => setBuyerZip(e.target.value)}
                  placeholder="ZIP code"
                  inputMode="numeric"
                  className="h-full min-w-0 flex-1 rounded-[8px] bg-transparent px-3 text-sm focus:outline-none"
                  style={{
                    color: "var(--text-primary)",
                    fontFamily: "var(--ff-body)",
                    minHeight: "50px",
                  }}
                />
                <button
                  type="button"
                  title="Detect my location"
                  disabled={locatingZip}
                  onClick={() => void detectZip()}
                  className="flex h-full items-center px-2.5 disabled:opacity-50 transition-colors"
                  style={{ color: "var(--text-muted)" }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.color = "var(--primary)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.color = "var(--text-muted)")
                  }
                >
                  {locatingZip ? (
                    <span
                      className="h-3.5 w-3.5 animate-spin rounded-full border-2"
                      style={{
                        borderColor: "var(--border)",
                        borderTopColor: "var(--primary)",
                      }}
                    />
                  ) : (
                    <IcPin className="h-4 w-4" />
                  )}
                </button>
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-[8px] px-5 text-sm font-semibold text-white disabled:opacity-60 transition-colors"
                style={{
                  background: "var(--primary)",
                  fontFamily: "var(--ff-display)",
                }}
                onMouseEnter={(e) =>
                  !loading &&
                  (e.currentTarget.style.background = "var(--primary-bright)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "var(--primary)")
                }
              >
                <IcSearch className="h-4 w-4" />
                {loading ? "Searching…" : "Search"}
              </button>
            </div>
          </form>
        ) : (
          /* Collapsed summary pill */
          <button
            type="button"
            onClick={() => setFormOpen(true)}
            className="flex w-full items-center justify-between rounded-[12px] px-4 py-3 text-left transition-all"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.borderColor = "var(--border-strong)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.borderColor = "var(--border)")
            }
          >
            <span
              className="text-sm"
              style={{
                color: "var(--text-secondary)",
                fontFamily: "var(--ff-body)",
              }}
            >
              {searchSummary || "Set your search"}
            </span>
            <span
              className="ml-4 shrink-0 text-xs font-semibold"
              style={{
                color: "var(--primary)",
                fontFamily: "var(--ff-display)",
              }}
            >
              Edit search
            </span>
          </button>
        )}
      </div>

      {/* ── Post-search context ───────────────────────────────────────────── */}
      {normalizedPart && (
        <p className="mt-3 text-xs" style={{ color: "var(--text-muted)" }}>
          Searching for:{" "}
          <span
            className="font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            {normalizedPart}
          </span>
        </p>
      )}

      {compatibleVehicles.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {compatibleVehicles.map((vehicle, index) => (
            <span
              key={index}
              className="inline-flex items-center rounded-full px-2 py-1 text-xs"
              style={{
                background: "var(--bg-elevated)",
                color: "var(--text-secondary)",
                border: "1px solid var(--border)",
              }}
            >
              {vehicle.year_range_start}-{vehicle.year_range_end} {vehicle.make}{" "}
              {vehicle.model}
            </span>
          ))}
        </div>
      )}

      {/* ── Results ───────────────────────────────────────────────────────── */}
      {loading && (
        <div className="mt-12 flex flex-col items-center gap-3">
          <span
            className="h-6 w-6 animate-spin rounded-full border-2"
            style={{
              borderColor: "var(--border)",
              borderTopColor: "var(--primary)",
            }}
          />
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Searching…
          </p>
        </div>
      )}

      {!loading &&
        hasSearched &&
        results.length === 0 &&
        potentialCars.length === 0 && (
          <p
            className="mt-8 text-center text-sm"
            style={{ color: "var(--text-muted)" }}
          >
            No results found — try adjusting your search.
          </p>
        )}

      {/* ── Message modal ─────────────────────────────────────────────────── */}
      {msgModal && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center sm:items-center p-4"
          role="dialog"
          aria-modal
        >
          <div
            className="absolute inset-0 bg-black/70"
            onClick={() => setMsgModal(null)}
          />
          <div
            className="relative z-10 w-full max-w-md overflow-y-auto rounded-[16px] shadow-xl max-h-[90vh]"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
            }}
          >
            <div
              className="flex items-center justify-between px-5 py-4"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              <div>
                <p
                  className="text-xs font-bold uppercase tracking-widest"
                  style={{
                    color: "var(--text-muted)",
                    fontFamily: "var(--ff-display)",
                  }}
                >
                  Message seller
                </p>
                <p
                  className="mt-0.5 text-sm font-semibold"
                  style={{
                    fontFamily: "var(--ff-display)",
                    color: "var(--text-primary)",
                  }}
                >
                  {msgModal.vehicleName}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMsgModal(null)}
                className="rounded-[8px] p-1.5 transition-colors"
                style={{ color: "var(--text-muted)" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-hover)";
                  e.currentTarget.style.color = "var(--text-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--text-muted)";
                }}
              >
                <IcX className="h-5 w-5" />
              </button>
            </div>
            {msgModal.sent ? (
              <div className="p-6 text-center">
                <p
                  className="font-semibold"
                  style={{
                    fontFamily: "var(--ff-display)",
                    color: "var(--text-primary)",
                  }}
                >
                  Message sent!
                </p>
                <p
                  className="mt-1 text-sm"
                  style={{ color: "var(--text-muted)" }}
                >
                  Check your{" "}
                  <Link href="/inbox" style={{ color: "var(--primary)" }}>
                    inbox
                  </Link>{" "}
                  for the reply.
                </p>
                <button
                  type="button"
                  onClick={() => setMsgModal(null)}
                  className="mt-4 rounded-[8px] px-5 py-2 text-sm font-semibold text-white"
                  style={{ background: "var(--primary)" }}
                >
                  Done
                </button>
              </div>
            ) : (
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (!msgModal) return;
                  if (!user) {
                    window.location.href = `/login?next=/browse`;
                    return;
                  }
                  if (!msgModal.samplePartId) return;
                  setMsgModal((m) => ({ ...m, sending: true, error: null }));
                  try {
                    await apiFetch("/messages/start/", {
                      method: "POST",
                      body: JSON.stringify({
                        vehicle_part_id: msgModal.samplePartId,
                        message: msgModal.text.trim(),
                      }),
                    });
                    setMsgModal((m) => ({ ...m, sending: false, sent: true }));
                  } catch (err) {
                    toast.error(
                      err instanceof ApiError ? err.message : "Failed to send."
                    );
                    setMsgModal((m) => ({ ...m, sending: false }));
                  }
                }}
                className="p-5 space-y-4"
              >
                <div
                  className="rounded-[10px] p-3"
                  style={{
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border)",
                  }}
                >
                  <PartsPickerMulti
                    selected={msgModal.parts}
                    onChange={(parts) => {
                      const base = `Hi, I'm looking for ${
                        parts.length
                          ? parts.join(", ")
                          : partNeed.trim() || "a part"
                      } for my ${buyerMake} ${buyerModel}. Is anything from your ${
                        msgModal.card?.year
                      } ${msgModal.card?.make} ${
                        msgModal.card?.model
                      } compatible?`;
                      setMsgModal((m) => ({ ...m, parts, text: base }));
                    }}
                    label="Which parts do you need?"
                  />
                </div>
                <textarea
                  value={msgModal.text}
                  onChange={(e) =>
                    setMsgModal((m) => ({ ...m, text: e.target.value }))
                  }
                  rows={4}
                  placeholder="Type your message…"
                  className="w-full resize-none rounded-[10px] px-4 py-3 text-sm focus:outline-none"
                  style={{
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border)",
                    color: "var(--text-primary)",
                    fontFamily: "var(--ff-body)",
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = "var(--primary)";
                    e.target.style.boxShadow = "0 0 0 3px var(--primary-muted)";
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = "var(--border)";
                    e.target.style.boxShadow = "none";
                  }}
                />
                {!user && (
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    You&apos;ll be asked to sign in before sending.
                  </p>
                )}
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setMsgModal(null)}
                    className="flex-1 rounded-[8px] py-2.5 text-sm font-medium transition-colors"
                    style={{
                      border: "1px solid var(--border)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={msgModal.sending || !msgModal.text.trim()}
                    className="flex-1 inline-flex items-center justify-center gap-2 rounded-[8px] py-2.5 text-sm font-semibold text-white disabled:opacity-60"
                    style={{ background: "var(--primary)" }}
                  >
                    {msgModal.sending ? (
                      <>
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                        Sending…
                      </>
                    ) : (
                      "Send message"
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ── Tabs + results ─────────────────────────────────────────────────── */}
      {!loading && (results.length > 0 || potentialCars.length > 0) && (
        <div className="mt-6">
          {/* Tab bar */}
          <div
            className="flex gap-1 pb-0"
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            {results.length > 0 && (
              <button
                type="button"
                onClick={() => setActiveTab("parts")}
                className="px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition-colors"
                style={{
                  borderBottomColor:
                    activeTab === "parts" ? "var(--primary)" : "transparent",
                  color:
                    activeTab === "parts"
                      ? "var(--primary)"
                      : "var(--text-muted)",
                  fontFamily: "var(--ff-display)",
                }}
              >
                Buy Now Parts
                <span
                  className="ml-1.5 rounded-full px-1.5 py-0.5 text-[11px] font-bold"
                  style={{
                    background:
                      activeTab === "parts"
                        ? "var(--primary-muted)"
                        : "var(--bg-elevated)",
                    color:
                      activeTab === "parts"
                        ? "var(--primary)"
                        : "var(--text-muted)",
                  }}
                >
                  {listingsTotalCount > results.length
                    ? `${results.length} / ${listingsTotalCount}`
                    : results.length}
                </span>
              </button>
            )}
            <button
              type="button"
              onClick={() => setActiveTab("cars")}
              className="px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition-colors"
              style={{
                borderBottomColor:
                  activeTab === "cars" ? "var(--primary)" : "transparent",
                color:
                  activeTab === "cars" ? "var(--primary)" : "var(--text-muted)",
                fontFamily: "var(--ff-display)",
              }}
            >
              Donor Cars
              <span
                className="ml-1.5 rounded-full px-1.5 py-0.5 text-[11px] font-bold"
                style={{
                  background:
                    activeTab === "cars"
                      ? "var(--primary-muted)"
                      : "var(--bg-elevated)",
                  color:
                    activeTab === "cars"
                      ? "var(--primary)"
                      : "var(--text-muted)",
                }}
              >
                {potentialCars.length}
              </span>
            </button>
          </div>

          {/* ── Parts tab ── */}
          {activeTab === "parts" && results.length > 0 && (
            <div className="mt-3">
              {listingsTotalCount > results.length && (
                <p
                  className="mb-2 rounded-[8px] px-3 py-2 text-xs"
                  style={{
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    color: "var(--text-muted)",
                  }}
                >
                  Showing{" "}
                  <strong style={{ color: "var(--text-secondary)" }}>
                    {results.length}
                  </strong>{" "}
                  of{" "}
                  <strong style={{ color: "var(--text-secondary)" }}>
                    {listingsTotalCount}
                  </strong>{" "}
                  matching parts (newest first; server limit for one search).
                  Narrow with filters or a more specific part name to find what
                  you need.
                </p>
              )}
              {/* Filter / sort bar */}
              <div className="flex flex-wrap items-center gap-2 pb-3">
                <select
                  value={partSort}
                  onChange={(e) => {
                    setPartSort(e.target.value);
                    setPartsPage(0);
                  }}
                  className="rounded-[6px] px-2.5 py-1.5 text-xs font-medium focus:outline-none"
                  style={{
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    color: "var(--text-secondary)",
                    fontFamily: "var(--ff-body)",
                  }}
                >
                  <option value="newest">Sort: Newest</option>
                  <option value="price_asc">Price ↑</option>
                  <option value="price_desc">Price ↓</option>
                </select>
                {partEngineOpts.length >= 1 && (
                  <select
                    value={partFilterEngine}
                    onChange={(e) => {
                      setPartFilterEngine(e.target.value);
                      setPartsPage(0);
                    }}
                    className="rounded-[6px] px-2.5 py-1.5 text-xs font-medium focus:outline-none"
                    style={{
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border)",
                      color: "var(--text-secondary)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    <option value="">All engines</option>
                    {partEngineOpts.map((e) => (
                      <option key={e} value={e}>
                        {e}
                      </option>
                    ))}
                  </select>
                )}
                {partColorOpts.length >= 1 && (
                  <select
                    value={partFilterColor}
                    onChange={(e) => {
                      setPartFilterColor(e.target.value);
                      setPartsPage(0);
                    }}
                    className="rounded-[6px] px-2.5 py-1.5 text-xs font-medium focus:outline-none"
                    style={{
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border)",
                      color: "var(--text-secondary)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    <option value="">All colors</option>
                    {partColorOpts.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                )}
                {partTransOpts.length >= 1 && (
                  <select
                    value={partFilterTrans}
                    onChange={(e) => {
                      setPartFilterTrans(e.target.value);
                      setPartsPage(0);
                    }}
                    className="rounded-[6px] px-2.5 py-1.5 text-xs font-medium focus:outline-none"
                    style={{
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border)",
                      color: "var(--text-secondary)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    <option value="">All transmissions</option>
                    {partTransOpts.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setPartFilterNoDamage((v) => !v);
                    setPartsPage(0);
                  }}
                  className="rounded-full px-3 py-1 text-xs font-medium transition-all"
                  style={{
                    background: partFilterNoDamage
                      ? "var(--primary-muted)"
                      : "var(--bg-elevated)",
                    border: `1px solid ${
                      partFilterNoDamage
                        ? "rgba(255,92,26,0.3)"
                        : "var(--border)"
                    }`,
                    color: partFilterNoDamage
                      ? "var(--primary-bright)"
                      : "var(--text-muted)",
                  }}
                >
                  No damage
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPartFilterHasPhotos((v) => !v);
                    setPartsPage(0);
                  }}
                  className="rounded-full px-3 py-1 text-xs font-medium transition-all"
                  style={{
                    background: partFilterHasPhotos
                      ? "var(--primary-muted)"
                      : "var(--bg-elevated)",
                    border: `1px solid ${
                      partFilterHasPhotos
                        ? "rgba(255,92,26,0.3)"
                        : "var(--border)"
                    }`,
                    color: partFilterHasPhotos
                      ? "var(--primary-bright)"
                      : "var(--text-muted)",
                  }}
                >
                  Has photos
                </button>
                {filteredParts.length !== results.length && (
                  <span
                    className="ml-auto text-xs"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {filteredParts.length} of {results.length}
                  </span>
                )}
              </div>
              {filteredParts.length === 0 ? (
                <p
                  className="py-6 text-center text-sm"
                  style={{ color: "var(--text-muted)" }}
                >
                  No parts match these filters.
                </p>
              ) : (
                <>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {filteredParts
                      .slice(
                        safePartsPage * PARTS_PER_PAGE,
                        (safePartsPage + 1) * PARTS_PER_PAGE
                      )
                      .map((part) => (
                        <PartCard
                          key={part.id}
                          part={part}
                          buyerZip={buyerZip}
                          buyerMake={buyerMake}
                          buyerModel={buyerModel}
                          user={user}
                          onMessage={(p) => {
                            const vp = p.vehicle_public || {};
                            const vehicleName = [
                              vp.year,
                              vp.make,
                              vp.model,
                              vp.trim,
                            ]
                              .filter(Boolean)
                              .join(" ");
                            setMsgModal({
                              card: vp,
                              samplePartId: p.id,
                              vehicleName,
                              parts: [],
                              text: `Hi, I'm interested in the ${p.label} for my ${buyerMake} ${buyerModel}. Is it still available?`,
                              sending: false,
                              sent: false,
                              error: null,
                            });
                          }}
                        />
                      ))}
                  </div>
                  {/* Pagination — compact page numbers + ellipsis */}
                  {Math.ceil(filteredParts.length / PARTS_PER_PAGE) > 1 &&
                    (() => {
                      const totalPages = Math.ceil(
                        filteredParts.length / PARTS_PER_PAGE
                      );
                      const entries = partsPaginationEntries(
                        totalPages,
                        safePartsPage
                      );
                      return (
                        <div className="mt-3 flex flex-wrap items-center justify-center gap-1">
                          <button
                            type="button"
                            onClick={() =>
                              setPartsPage((p) => Math.max(0, p - 1))
                            }
                            disabled={safePartsPage === 0}
                            className="rounded-[8px] px-3 py-1.5 text-sm font-medium transition-all disabled:opacity-40"
                            style={{
                              border: "1px solid var(--border)",
                              color: "var(--text-secondary)",
                              fontFamily: "var(--ff-body)",
                            }}
                            onMouseEnter={(e) =>
                              !e.currentTarget.disabled &&
                              (e.currentTarget.style.borderColor =
                                "var(--border-strong)")
                            }
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderColor =
                                "var(--border)";
                            }}
                          >
                            ← Prev
                          </button>
                          {entries.map((entry, idx) =>
                            entry === "ellipsis" ? (
                              <span
                                key={`e-${idx}`}
                                className="px-1.5 py-1.5 text-sm font-medium"
                                style={{
                                  color: "var(--text-muted)",
                                  fontFamily: "var(--ff-body)",
                                  letterSpacing: "0.06em",
                                }}
                                aria-hidden
                              >
                                …
                              </span>
                            ) : (
                              <button
                                key={entry}
                                type="button"
                                onClick={() => setPartsPage(entry)}
                                className="rounded-[8px] min-w-[2.25rem] px-2.5 py-1.5 text-sm font-medium transition-all"
                                style={{
                                  background:
                                    entry === safePartsPage
                                      ? "var(--primary-muted)"
                                      : "transparent",
                                  border: `1px solid ${
                                    entry === safePartsPage
                                      ? "rgba(255,92,26,0.3)"
                                      : "var(--border)"
                                  }`,
                                  color:
                                    entry === safePartsPage
                                      ? "var(--primary)"
                                      : "var(--text-muted)",
                                }}
                              >
                                {entry + 1}
                              </button>
                            )
                          )}
                          <button
                            type="button"
                            onClick={() =>
                              setPartsPage((p) => Math.min(partsPageMax, p + 1))
                            }
                            disabled={safePartsPage >= partsPageMax}
                            className="rounded-[8px] px-3 py-1.5 text-sm font-medium transition-all disabled:opacity-40"
                            style={{
                              border: "1px solid var(--border)",
                              color: "var(--text-secondary)",
                              fontFamily: "var(--ff-body)",
                            }}
                            onMouseEnter={(e) =>
                              !e.currentTarget.disabled &&
                              (e.currentTarget.style.borderColor =
                                "var(--border-strong)")
                            }
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderColor =
                                "var(--border)";
                            }}
                          >
                            Next →
                          </button>
                        </div>
                      );
                    })()}
                </>
              )}
            </div>
          )}

          {/* ── Cars tab ── */}
          {activeTab === "cars" && (
            <div className="mt-3">
              {potentialCars.length === 0 ? (
                <p
                  className="py-6 text-center text-sm"
                  style={{ color: "var(--text-muted)" }}
                >
                  No donor cars found for this search.
                </p>
              ) : (
                <>
                  {/* Filter / sort bar */}
                  <div className="flex flex-wrap items-center gap-2 pb-3">
                    <select
                      value={carSort}
                      onChange={(e) => {
                        setCarSort(e.target.value);
                        setDonorVisible(DONORS_PER_LOAD);
                      }}
                      className="rounded-[6px] px-2.5 py-1.5 text-xs font-medium focus:outline-none"
                      style={{
                        background: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                        color: "var(--text-secondary)",
                        fontFamily: "var(--ff-body)",
                      }}
                    >
                      <option value="default">Sort: Default</option>
                      <option value="most_parts">Most parts</option>
                    </select>
                    {carEngineOpts.length >= 1 && (
                      <select
                        value={carFilterEngine}
                        onChange={(e) => {
                          setCarFilterEngine(e.target.value);
                          setDonorVisible(DONORS_PER_LOAD);
                        }}
                        className="rounded-[6px] px-2.5 py-1.5 text-xs font-medium focus:outline-none"
                        style={{
                          background: "var(--bg-elevated)",
                          border: "1px solid var(--border)",
                          color: "var(--text-secondary)",
                          fontFamily: "var(--ff-body)",
                        }}
                      >
                        <option value="">All engines</option>
                        {carEngineOpts.map((e) => (
                          <option key={e} value={e}>
                            {e}
                          </option>
                        ))}
                      </select>
                    )}
                    {carColorOpts.length >= 1 && (
                      <select
                        value={carFilterColor}
                        onChange={(e) => {
                          setCarFilterColor(e.target.value);
                          setDonorVisible(DONORS_PER_LOAD);
                        }}
                        className="rounded-[6px] px-2.5 py-1.5 text-xs font-medium focus:outline-none"
                        style={{
                          background: "var(--bg-elevated)",
                          border: "1px solid var(--border)",
                          color: "var(--text-secondary)",
                          fontFamily: "var(--ff-body)",
                        }}
                      >
                        <option value="">All colors</option>
                        {carColorOpts.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    )}
                    {carTransOpts.length >= 1 && (
                      <select
                        value={carFilterTrans}
                        onChange={(e) => {
                          setCarFilterTrans(e.target.value);
                          setDonorVisible(DONORS_PER_LOAD);
                        }}
                        className="rounded-[6px] px-2.5 py-1.5 text-xs font-medium focus:outline-none"
                        style={{
                          background: "var(--bg-elevated)",
                          border: "1px solid var(--border)",
                          color: "var(--text-secondary)",
                          fontFamily: "var(--ff-body)",
                        }}
                      >
                        <option value="">All transmissions</option>
                        {carTransOpts.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setCarFilterNoDamage((v) => !v);
                        setDonorVisible(DONORS_PER_LOAD);
                      }}
                      className="rounded-full px-3 py-1 text-xs font-medium transition-all"
                      style={{
                        background: carFilterNoDamage
                          ? "var(--primary-muted)"
                          : "var(--bg-elevated)",
                        border: `1px solid ${
                          carFilterNoDamage
                            ? "rgba(255,92,26,0.3)"
                            : "var(--border)"
                        }`,
                        color: carFilterNoDamage
                          ? "var(--primary-bright)"
                          : "var(--text-muted)",
                      }}
                    >
                      No damage
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setCarFilterHasPhotos((v) => !v);
                        setDonorVisible(DONORS_PER_LOAD);
                      }}
                      className="rounded-full px-3 py-1 text-xs font-medium transition-all"
                      style={{
                        background: carFilterHasPhotos
                          ? "var(--primary-muted)"
                          : "var(--bg-elevated)",
                        border: `1px solid ${
                          carFilterHasPhotos
                            ? "rgba(255,92,26,0.3)"
                            : "var(--border)"
                        }`,
                        color: carFilterHasPhotos
                          ? "var(--primary-bright)"
                          : "var(--text-muted)",
                      }}
                    >
                      Has photos
                    </button>
                    {filteredCars.length !== potentialCars.length && (
                      <span
                        className="ml-auto text-xs"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {filteredCars.length} of {potentialCars.length}
                      </span>
                    )}
                  </div>

                  {filteredCars.length === 0 ? (
                    <p
                      className="py-6 text-center text-sm"
                      style={{ color: "var(--text-muted)" }}
                    >
                      No cars match these filters.
                    </p>
                  ) : (
                    <>
                      <div className="space-y-4">
                        {filteredCars.slice(0, donorVisible).map((car) => {
                          const vehicleName = [
                            car.year,
                            car.make,
                            car.model,
                            car.trim,
                          ]
                            .filter(Boolean)
                            .join(" ");
                          const photos = car.photo_urls?.length
                            ? car.photo_urls
                            : car.primary_photo_url
                            ? [car.primary_photo_url]
                            : [];
                          const samplePartId = car.sample_vehicle_part_id;
                          const canMessage = Boolean(samplePartId);
                          const isSelected = selectedVehicleIds.includes(
                            car.vehicle_id
                          );
                          return (
                            <article
                              key={car.vehicle_id}
                              className="flex overflow-hidden rounded-[14px] transition-all duration-200"
                              style={{
                                background: "var(--bg-surface)",
                                border: "1px solid var(--border)",
                              }}
                              onMouseEnter={(e) =>
                                (e.currentTarget.style.borderColor =
                                  "var(--border-strong)")
                              }
                              onMouseLeave={(e) =>
                                (e.currentTarget.style.borderColor =
                                  "var(--border)")
                              }
                            >
                              {/* Photo */}
                              <div
                                className="relative w-36 shrink-0 sm:w-52"
                                style={{ background: "var(--bg-elevated)" }}
                              >
                                <VehiclePhotoGallery
                                  key={car.vehicle_id}
                                  photos={photos}
                                  alt={vehicleName}
                                />
                                <label
                                  className={`absolute left-2 top-2 z-10 flex h-7 w-7 cursor-pointer items-center justify-center rounded-[6px] backdrop-blur-sm ${
                                    !canMessage
                                      ? "cursor-not-allowed opacity-40"
                                      : ""
                                  }`}
                                  style={{
                                    background: "rgba(10,10,13,0.8)",
                                    border: "1px solid var(--border)",
                                  }}
                                  title={
                                    canMessage
                                      ? "Select to message seller"
                                      : "No part to start a thread"
                                  }
                                >
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    disabled={!canMessage}
                                    onChange={() => {
                                      setSelectedVehicleIds((prev) =>
                                        prev.includes(car.vehicle_id)
                                          ? prev.filter(
                                              (id) => id !== car.vehicle_id
                                            )
                                          : canMessage
                                          ? [...prev, car.vehicle_id]
                                          : prev
                                      );
                                    }}
                                    className="h-4 w-4 rounded"
                                    style={{ accentColor: "var(--primary)" }}
                                    aria-label={`Select ${vehicleName} for messaging`}
                                  />
                                </label>
                              </div>
                              {/* Info */}
                              <div className="flex min-w-0 flex-1 flex-col justify-between p-3 sm:p-4">
                                <div>
                                  <div className="flex items-start justify-between gap-2">
                                    <Link
                                      href={`/browse/vehicles/${car.vehicle_id}`}
                                      className="min-w-0 flex-1 text-sm font-semibold leading-snug sm:text-base transition-colors"
                                      style={{
                                        fontFamily: "var(--ff-display)",
                                        color: "var(--text-primary)",
                                      }}
                                      onMouseEnter={(e) =>
                                        (e.currentTarget.style.color =
                                          "var(--primary)")
                                      }
                                      onMouseLeave={(e) =>
                                        (e.currentTarget.style.color =
                                          "var(--text-primary)")
                                      }
                                    >
                                      {vehicleName}
                                    </Link>
                                    {car.has_damage && (
                                      <span
                                        className="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium"
                                        style={{
                                          background: "rgba(245,158,11,0.1)",
                                          color: "var(--warning)",
                                          border:
                                            "1px solid rgba(245,158,11,0.2)",
                                        }}
                                      >
                                        Damage
                                      </span>
                                    )}
                                  </div>
                                  <div className="mt-1.5 flex flex-wrap gap-1">
                                    {car.color && (
                                      <span
                                        className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px]"
                                        style={{
                                          background: "var(--bg-elevated)",
                                          color: "var(--text-secondary)",
                                          border: "1px solid var(--border)",
                                        }}
                                      >
                                        <span className="font-semibold">
                                          Color
                                        </span>{" "}
                                        {car.color}
                                      </span>
                                    )}
                                    {car.engine && (
                                      <span
                                        className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px]"
                                        style={{
                                          background: "var(--bg-elevated)",
                                          color: "var(--text-secondary)",
                                          border: "1px solid var(--border)",
                                        }}
                                      >
                                        <span className="font-semibold">
                                          Engine
                                        </span>{" "}
                                        {car.engine}
                                      </span>
                                    )}
                                    {car.transmission && (
                                      <span
                                        className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px]"
                                        style={{
                                          background: "var(--bg-elevated)",
                                          color: "var(--text-secondary)",
                                          border: "1px solid var(--border)",
                                        }}
                                      >
                                        <span className="font-semibold">
                                          Trans.
                                        </span>{" "}
                                        {car.transmission}
                                      </span>
                                    )}
                                    {(car.location_state ||
                                      car.location_zip_masked) && (
                                      <span
                                        className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px]"
                                        style={{
                                          background: "var(--bg-elevated)",
                                          color: "var(--text-secondary)",
                                          border: "1px solid var(--border)",
                                        }}
                                      >
                                        <IcPin className="h-3 w-3 shrink-0" />
                                        {[
                                          car.location_state,
                                          car.location_zip_masked,
                                        ]
                                          .filter(Boolean)
                                          .join(" ")}
                                      </span>
                                    )}
                                  </div>
                                  {car.seller && (
                                    <div
                                      className="mt-1.5 flex items-center gap-1.5 text-[11px]"
                                      style={{ color: "var(--text-muted)" }}
                                    >
                                      <span
                                        className="font-medium"
                                        style={{
                                          color: "var(--text-secondary)",
                                        }}
                                      >
                                        {car.seller.display_name}
                                      </span>
                                      {car.seller.completed_sales > 0 && (
                                        <>
                                          <span>·</span>
                                          <span
                                            className="flex items-center gap-0.5"
                                            style={{ color: "var(--success)" }}
                                          >
                                            <svg
                                              viewBox="0 0 16 16"
                                              className="h-3 w-3"
                                              style={{ fill: "var(--success)" }}
                                            >
                                              <path d="M8 1l1.9 3.8 4.1.6-3 2.9.7 4.1L8 10.4l-3.7 1.9.7-4.1-3-2.9 4.2-.6z" />
                                            </svg>
                                            {car.seller.completed_sales} sale
                                            {car.seller.completed_sales !== 1
                                              ? "s"
                                              : ""}
                                          </span>
                                        </>
                                      )}
                                    </div>
                                  )}
                                </div>
                                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                                  {car.matching_parts_count > 0 ? (
                                    <span
                                      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
                                      style={{
                                        background: "var(--primary-muted)",
                                        color: "var(--primary-bright)",
                                        border: "1px solid rgba(255,92,26,0.2)",
                                      }}
                                    >
                                      {car.matching_parts_count} part
                                      {car.matching_parts_count !== 1
                                        ? "s"
                                        : ""}{" "}
                                      listed
                                    </span>
                                  ) : (
                                    <span
                                      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                                      style={{
                                        background: "var(--bg-elevated)",
                                        color: "var(--text-muted)",
                                        border: "1px solid var(--border)",
                                      }}
                                    >
                                      Ask availability
                                    </span>
                                  )}
                                  <div className="flex gap-2">
                                    <Link
                                      href={`/browse/vehicles/${car.vehicle_id}`}
                                      className="rounded-[8px] px-3 py-1.5 text-xs font-medium transition-colors"
                                      style={{
                                        border: "1px solid var(--border)",
                                        color: "var(--text-muted)",
                                      }}
                                      onMouseEnter={(e) => {
                                        e.currentTarget.style.borderColor =
                                          "var(--border-strong)";
                                        e.currentTarget.style.color =
                                          "var(--text-primary)";
                                      }}
                                      onMouseLeave={(e) => {
                                        e.currentTarget.style.borderColor =
                                          "var(--border)";
                                        e.currentTarget.style.color =
                                          "var(--text-muted)";
                                      }}
                                    >
                                      View car
                                    </Link>
                                    <button
                                      type="button"
                                      disabled={!canMessage}
                                      onClick={() => {
                                        if (!samplePartId) return;
                                        setMsgModal({
                                          card: car,
                                          samplePartId,
                                          vehicleName,
                                          parts: [],
                                          text: `Hi, I'm looking for ${
                                            partNeed.trim() || "a part"
                                          } for my ${buyerMake} ${buyerModel}. Is anything from your ${
                                            car.year
                                          } ${car.make} ${
                                            car.model
                                          } compatible?`,
                                          sending: false,
                                          sent: false,
                                          error: null,
                                        });
                                      }}
                                      className="rounded-[8px] px-3 py-1.5 text-xs font-semibold text-white transition-colors disabled:opacity-40"
                                      style={{ background: "var(--primary)" }}
                                      onMouseEnter={(e) =>
                                        !e.currentTarget.disabled &&
                                        (e.currentTarget.style.background =
                                          "var(--primary-bright)")
                                      }
                                      onMouseLeave={(e) =>
                                        (e.currentTarget.style.background =
                                          "var(--primary)")
                                      }
                                    >
                                      Message
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </article>
                          );
                        })}
                      </div>
                      {filteredCars.length > donorVisible && (
                        <div className="mt-2 flex flex-col items-center gap-1">
                          <p className="text-xs text-zinc-400">
                            Showing {donorVisible} of {filteredCars.length}
                          </p>
                          <button
                            type="button"
                            onClick={() =>
                              setDonorVisible((v) => v + DONORS_PER_LOAD)
                            }
                            className="rounded-[8px] px-5 py-2 text-sm font-medium transition-all"
                            style={{
                              border: "1px solid var(--border)",
                              color: "var(--text-secondary)",
                              fontFamily: "var(--ff-body)",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.borderColor =
                                "var(--border-strong)";
                              e.currentTarget.style.color =
                                "var(--text-primary)";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderColor =
                                "var(--border)";
                              e.currentTarget.style.color =
                                "var(--text-secondary)";
                            }}
                          >
                            Load more
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Bulk message bar ── */}
          {selectedVehicleIds.length > 0 && (
            <div
              className="fixed bottom-4 left-1/2 z-40 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-2 rounded-[16px] px-4 py-3 shadow-xl backdrop-blur"
              style={{
                background: "rgba(26,26,33,0.95)",
                border: "1px solid var(--border-strong)",
              }}
            >
              <span
                className="text-sm font-medium"
                style={{
                  color: "var(--text-secondary)",
                  fontFamily: "var(--ff-body)",
                }}
              >
                {selectedVehicleIds.length} selected
              </span>
              <button
                type="button"
                onClick={() => {
                  const need = partNeed.trim() || "a part";
                  setBulkMsgModal({
                    parts: [],
                    text: `Hi, I'm looking for ${need} for my ${buyerMake} ${buyerModel}. Is anything from your inventory compatible?`,
                    sending: false,
                    sent: false,
                    error: null,
                    count: selectedVehicleIds.length,
                  });
                }}
                className="rounded-[8px] px-4 py-2 text-sm font-semibold text-white transition-colors"
                style={{ background: "var(--primary)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "var(--primary-bright)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "var(--primary)")
                }
              >
                Message sellers
              </button>
              <button
                type="button"
                onClick={() => setSelectedVehicleIds([])}
                className="text-sm font-medium transition-colors"
                style={{ color: "var(--text-muted)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.color = "var(--text-primary)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "var(--text-muted)")
                }
              >
                Clear
              </button>
            </div>
          )}

          {/* ── Bulk message modal ── */}
          {bulkMsgModal && (
            <div
              className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center"
              role="dialog"
              aria-modal
            >
              <div
                className="absolute inset-0 bg-black/50"
                onClick={() => setBulkMsgModal(null)}
              />
              <div
                className="relative z-10 max-h-[90vh] w-full max-w-md overflow-y-auto rounded-[16px] shadow-xl"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                }}
              >
                <div
                  className="flex items-center justify-between px-5 py-4"
                  style={{ borderBottom: "1px solid var(--border-subtle)" }}
                >
                  <div>
                    <p
                      className="text-xs font-bold uppercase tracking-widest"
                      style={{
                        color: "var(--text-muted)",
                        fontFamily: "var(--ff-display)",
                      }}
                    >
                      Message sellers
                    </p>
                    <p
                      className="mt-0.5 text-sm font-semibold"
                      style={{
                        fontFamily: "var(--ff-display)",
                        color: "var(--text-primary)",
                      }}
                    >
                      {bulkMsgModal.count} vehicle
                      {bulkMsgModal.count !== 1 ? "s" : ""} selected
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setBulkMsgModal(null)}
                    className="rounded-[8px] p-1.5 transition-colors"
                    style={{ color: "var(--text-muted)" }}
                  >
                    <IcX className="h-5 w-5" />
                  </button>
                </div>
                {bulkMsgModal.sent ? (
                  <div className="p-6 text-center">
                    <p
                      className="font-semibold"
                      style={{
                        fontFamily: "var(--ff-display)",
                        color: "var(--text-primary)",
                      }}
                    >
                      Messages sent!
                    </p>
                    <p
                      className="mt-1 text-sm"
                      style={{ color: "var(--text-muted)" }}
                    >
                      Check your{" "}
                      <Link href="/inbox" style={{ color: "var(--primary)" }}>
                        inbox
                      </Link>{" "}
                      for replies.
                    </p>
                    <button
                      type="button"
                      onClick={() => setBulkMsgModal(null)}
                      className="mt-4 rounded-[8px] px-5 py-2 text-sm font-semibold text-white"
                      style={{ background: "var(--primary)" }}
                    >
                      Done
                    </button>
                  </div>
                ) : (
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      if (!bulkMsgModal) return;
                      if (!user) {
                        window.location.href = "/login?next=/browse";
                        return;
                      }
                      const partIds = potentialCars
                        .filter(
                          (c) =>
                            selectedVehicleIds.includes(c.vehicle_id) &&
                            c.sample_vehicle_part_id
                        )
                        .map((c) => c.sample_vehicle_part_id);
                      if (!partIds.length) {
                        toast.warning("No vehicles could be messaged.");
                        return;
                      }
                      setBulkMsgModal((m) => ({
                        ...m,
                        sending: true,
                        error: null,
                      }));
                      try {
                        await apiFetch("/messages/bulk-rfq/", {
                          method: "POST",
                          body: JSON.stringify({
                            vehicle_part_ids: partIds,
                            message: bulkMsgModal.text.trim(),
                          }),
                        });
                        setBulkMsgModal((m) => ({
                          ...m,
                          sending: false,
                          sent: true,
                          count: partIds.length,
                        }));
                        setSelectedVehicleIds([]);
                      } catch (err) {
                        toast.error(
                          err instanceof ApiError
                            ? err.message
                            : "Failed to send."
                        );
                        setBulkMsgModal((m) => ({ ...m, sending: false }));
                      }
                    }}
                    className="space-y-4 p-5"
                  >
                    <div
                      className="rounded-[10px] p-3"
                      style={{
                        background: "var(--bg-surface)",
                        border: "1px solid var(--border)",
                      }}
                    >
                      <PartsPickerMulti
                        selected={bulkMsgModal.parts ?? []}
                        onChange={(picked) => {
                          const need = picked.length
                            ? picked.join(", ")
                            : partNeed.trim() || "a part";
                          setBulkMsgModal((m) =>
                            m
                              ? {
                                  ...m,
                                  parts: picked,
                                  text: `Hi, I'm looking for ${need} for my ${buyerMake} ${buyerModel}. Is anything from your inventory compatible?`,
                                }
                              : m
                          );
                        }}
                        label="Which parts are you looking for?"
                      />
                    </div>
                    <textarea
                      value={bulkMsgModal.text}
                      onChange={(e) =>
                        setBulkMsgModal((m) => ({ ...m, text: e.target.value }))
                      }
                      rows={5}
                      placeholder="Your message to all selected sellers…"
                      className="w-full resize-none rounded-[10px] px-4 py-3 text-sm focus:outline-none"
                      style={{
                        background: "var(--bg-surface)",
                        border: "1px solid var(--border)",
                        color: "var(--text-primary)",
                        fontFamily: "var(--ff-body)",
                      }}
                      onFocus={(e) => {
                        e.target.style.borderColor = "var(--primary)";
                        e.target.style.boxShadow =
                          "0 0 0 3px var(--primary-muted)";
                      }}
                      onBlur={(e) => {
                        e.target.style.borderColor = "var(--border)";
                        e.target.style.boxShadow = "none";
                      }}
                    />
                    {!user && (
                      <p
                        className="text-xs"
                        style={{ color: "var(--text-muted)" }}
                      >
                        You&apos;ll be asked to sign in before sending.
                      </p>
                    )}
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setBulkMsgModal(null)}
                        className="flex-1 rounded-[8px] py-2.5 text-sm font-medium transition-colors"
                        style={{
                          border: "1px solid var(--border)",
                          color: "var(--text-secondary)",
                        }}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={
                          bulkMsgModal.sending || !bulkMsgModal.text.trim()
                        }
                        className="flex-1 inline-flex items-center justify-center gap-2 rounded-[8px] py-2.5 text-sm font-semibold text-white disabled:opacity-60 transition-colors"
                        style={{ background: "var(--primary)" }}
                        onMouseEnter={(e) =>
                          !e.currentTarget.disabled &&
                          (e.currentTarget.style.background =
                            "var(--primary-bright)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background = "var(--primary)")
                        }
                      >
                        {bulkMsgModal.sending ? (
                          <>
                            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                            Sending…
                          </>
                        ) : (
                          "Send to all"
                        )}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function BrowsePage() {
  return (
    <Suspense>
      <BrowsePageInner />
    </Suspense>
  );
}
