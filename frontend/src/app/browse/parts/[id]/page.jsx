"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { useBuyerCar } from "@/context/car-context";
import { useCart } from "@/context/cart-context";
import CarSelector from "@/components/CarSelector";
import { ApiError, apiFetch, getItem } from "@/lib/api";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

function Stars({ value, size = 13 }) {
  const filled = Math.round(Number(value) || 0);
  return (
    <span style={{ fontSize: size, letterSpacing: 1 }}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ color: i < filled ? "#fbbf24" : "var(--border)" }}>★</span>
      ))}
    </span>
  );
}

function PhotoGallery({ urls }) {
  const scrollerRef = useRef(null);
  const [active, setActive] = useState(0);
  const [failed, setFailed] = useState(new Set());
  const [lightboxIdx, setLightboxIdx] = useState(null);

  const allUrls = (urls || []).filter(Boolean);
  const validData = allUrls.map((url, i) => ({ url, i })).filter(({ i }) => !failed.has(i));
  const validUrls = validData.map((d) => d.url);
  const n = validUrls.length;

  useEffect(() => {
    setActive(0);
    setFailed(new Set());
    const el = scrollerRef.current;
    if (el) el.scrollLeft = 0;
  }, [urls]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || n < 2) return;
    const onScroll = () => {
      const w = el.clientWidth;
      if (w < 1) return;
      setActive(Math.min(Math.max(0, Math.round(el.scrollLeft / w)), n - 1));
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [n]);

  if (n === 0) return null;

  return (
    <>
      {lightboxIdx !== null && (
        <div
          onClick={() => setLightboxIdx(null)}
          style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.93)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "zoom-out" }}
        >
          <img
            src={validUrls[lightboxIdx]}
            alt=""
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "95vw", maxHeight: "92vh", objectFit: "contain", borderRadius: 8 }}
          />
          <button type="button" onClick={() => setLightboxIdx(null)}
            style={{ position: "absolute", top: 16, right: 16, background: "rgba(255,255,255,0.12)", border: "none", color: "#fff", fontSize: 22, width: 40, height: 40, borderRadius: "50%", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
            ×
          </button>
          {n > 1 && (
            <>
              <button type="button" onClick={(e) => { e.stopPropagation(); setLightboxIdx((i) => (i - 1 + n) % n); }}
                style={{ position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)", background: "rgba(255,255,255,0.12)", border: "none", color: "#fff", fontSize: 26, width: 44, height: 44, borderRadius: "50%", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
                ‹
              </button>
              <button type="button" onClick={(e) => { e.stopPropagation(); setLightboxIdx((i) => (i + 1) % n); }}
                style={{ position: "absolute", right: 16, top: "50%", transform: "translateY(-50%)", background: "rgba(255,255,255,0.12)", border: "none", color: "#fff", fontSize: 26, width: 44, height: 44, borderRadius: "50%", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
                ›
              </button>
            </>
          )}
        </div>
      )}
      <div className="relative w-full overflow-hidden rounded-2xl" style={{ border: "1px solid var(--border)" }}>
        <div
          ref={scrollerRef}
          className="flex aspect-[16/10] w-full snap-x snap-mandatory overflow-x-auto overflow-y-hidden [scrollbar-width:none]"
          style={{ touchAction: "pan-x" }}
        >
          {validData.map(({ url, i }, validIdx) => (
            <div key={i} className="h-full w-full shrink-0 snap-center" style={{ minWidth: "100%", cursor: "zoom-in" }}
              onClick={() => setLightboxIdx(validIdx)}>
              <img src={url} alt="" className="h-full w-full object-cover" draggable={false}
                onError={() => setFailed((prev) => { const s = new Set(prev); s.add(i); return s; })} />
            </div>
          ))}
        </div>
        {n > 1 && (
          <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5">
            {validUrls.map((_, i) => (
              <span key={i} className="h-1.5 rounded-full transition-all"
                style={{ width: active === i ? 18 : 6, background: active === i ? "var(--primary)" : "rgba(255,255,255,0.35)" }} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function ThumbnailStrip({ photos }) {
  if (!photos?.length) return null;
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none]" style={{ marginTop: 8 }}>
      {photos.map((p, i) => (
        <div
          key={i}
          className="shrink-0 rounded-lg overflow-hidden"
          style={{ width: 60, height: 60, border: "1px solid var(--border)", background: "var(--bg-elevated)" }}
        >
          <img src={p.thumbnail_url || p.url} alt={p.label || ""} className="w-full h-full object-cover" />
        </div>
      ))}
    </div>
  );
}

function CompatibilitySection({ compatibilities }) {
  if (!compatibilities?.length) return null;
  const byMake = {};
  for (const c of compatibilities) {
    if (!byMake[c.make_name]) byMake[c.make_name] = [];
    byMake[c.make_name].push(c);
  }
  return (
    <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}>
      <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 10 }}>
        Also fits
      </p>
      <div className="space-y-2">
        {Object.entries(byMake).map(([make, entries]) => (
          <div key={make}>
            <p style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4 }}>{make}</p>
            <div className="flex flex-wrap gap-1.5">
              {entries.map((e) => (
                <span key={e.generation_id} style={{
                  fontSize: 11, fontWeight: 600, background: "var(--bg-elevated)",
                  border: "1px solid var(--border)", borderRadius: 5, padding: "2px 8px",
                  color: "var(--text-secondary)",
                }}>
                  {e.model_name} {e.generation_label}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PublicPartDetailPage() {
  const { id: rawId } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const { car, setCar, hasCar, loaded: carLoaded } = useBuyerCar();
  const cart = useCart();

  const id = useMemo(() => {
    const n = Number(rawId);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [rawId]);

  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [adding, setAdding] = useState(false);
  const [messageBody, setMessageBody] = useState("");
  const [messaging, setMessaging] = useState(false);
  const [showCarSelector, setShowCarSelector] = useState(false);

  const inCart = id ? cart.itemIds.has(id) : false;

  useEffect(() => {
    if (!id || !carLoaded) return;
    let cancelled = false;
    setLoading(true);
    setNotFound(false);

    const params = {};
    if (car?.generationId) params.generation = car.generationId;
    if (car?.modificationId) params.modification = car.modificationId;

    getItem(id, params)
      .then((data) => { if (!cancelled) setItem(data); })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else toast.error(e?.message || "Could not load item.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [id, car?.generationId, car?.modificationId, carLoaded, toast]);

  async function handleAddToCart() {
    if (!user) { window.location.href = `/login?next=/browse/parts/${id}`; return; }
    setAdding(true);
    try {
      await apiFetch("/cart/", { method: "POST", body: JSON.stringify({ item: id }) });
      await cart.refresh();
      toast.success("Added to cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setAdding(false);
    }
  }

  async function handleRemoveFromCart() {
    const cartItemId = cart.getCartItemId(id);
    if (!cartItemId) return;
    setAdding(true);
    try {
      await apiFetch(`/cart/${cartItemId}/`, { method: "DELETE" });
      await cart.refresh();
      toast.success("Removed from cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setAdding(false);
    }
  }

  async function handleMessage(e) {
    e.preventDefault();
    if (!user) { window.location.href = `/login?next=/browse/parts/${id}`; return; }
    if (!messageBody.trim()) return;
    setMessaging(true);
    try {
      const thread = await apiFetch("/messages/start/", {
        method: "POST",
        body: JSON.stringify({ item_id: id, body: messageBody.trim() }),
      });
      toast.success("Message sent.");
      window.location.href = `/inbox?thread=${thread.id}`;
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setMessaging(false);
    }
  }

  if (!carLoaded || loading) {
    return <div className="mx-auto max-w-2xl px-6 py-16"><p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</p></div>;
  }

  if (notFound || !item) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16 text-center">
        <p style={{ fontSize: 32, marginBottom: 8 }}>🔍</p>
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Part not found.</p>
        <Link href="/search" style={{ color: "var(--primary)", fontSize: 13, marginTop: 12, display: "inline-block" }}>← Browse parts</Link>
      </div>
    );
  }

  const itemPhotoUrls = (item.photos || []).map((p) => p.url).filter(Boolean);
  const vehiclePhotoUrls = (item.vehicle_photos || []).map((p) => p.url).filter(Boolean);
  const categoryFallback = itemPhotoUrls.length === 0 && item.category_image_url ? [item.category_image_url] : [];
  const galleryUrls = [...itemPhotoUrls, ...categoryFallback, ...vehiclePhotoUrls];
  const isAssemblyItem = item.status === "hidden_in_assembly";
  const vehicleName = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean).join(" ");
  const itemOptions = item.options || [];

  const mod = item.vehicle_modification;
  const donorSpecs = mod ? [
    mod.engine_code && { label: "Engine", value: mod.engine_code },
    mod.engine_displacement_cc && { label: "Displacement", value: `${(mod.engine_displacement_cc / 1000).toFixed(1)}L` },
    mod.fuel_type && { label: "Fuel", value: mod.fuel_type.charAt(0).toUpperCase() + mod.fuel_type.slice(1) },
    mod.transmission_type && { label: "Transmission", value: mod.transmission_type.toUpperCase() },
    mod.drive_type && { label: "Drive", value: mod.drive_type.toUpperCase() },
    mod.power_hp && { label: "Power", value: `${mod.power_hp} hp` },
    mod.variant_name && { label: "Variant", value: mod.variant_name },
  ].filter(Boolean) : [];
  const verifiedCompats = item.verified_compatibilities || [];

  const fitmentStatus = item.fitment?.status || null;
  const showFitsBanner = hasCar && fitmentStatus === "fits";
  const showUnknownFitment = hasCar && fitmentStatus === "unknown";

  const vehicleLabel = [
    item.vehicle_year,
    item.vehicle_make,
    item.vehicle_model,
    item.vehicle_generation_label ? `(${item.vehicle_generation_label})` : null,
  ].filter(Boolean).join(" ");

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-10">
      <Link href="/search" style={{ color: "var(--text-muted)", fontSize: 12, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 20 }}>
        ← Back to browse
      </Link>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="space-y-5">

        {/* Fitment banner */}
        {showFitsBanner && (
          <div className="rounded-xl px-4 py-3 flex items-center gap-2"
            style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.3)" }}>
            <span>✓</span>
            <p style={{ fontSize: 13, fontWeight: 700, color: "#4ade80" }}>
              Fits your {car.displayLabel || "car"}
            </p>
          </div>
        )}
        {showUnknownFitment && (
          <div className="rounded-xl px-4 py-3"
            style={{ background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.25)" }}>
            <p style={{ fontSize: 12, color: "#fbbf24" }}>
              Fitment not confirmed for your {car.displayLabel || "car"} — verify compatibility before ordering.
            </p>
          </div>
        )}

        {/* Car selector prompt */}
        {!hasCar && (
          <div className="rounded-xl overflow-hidden" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <button
              type="button"
              onClick={() => setShowCarSelector((v) => !v)}
              className="w-full text-left px-4 py-3 flex items-center justify-between gap-4"
            >
              <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Check if this fits your car</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--primary)", flexShrink: 0 }}>
                {showCarSelector ? "Close ↑" : "Select car →"}
              </span>
            </button>
            <AnimatePresence>
              {showCarSelector && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  style={{ borderTop: "1px solid var(--border)", padding: "14px 16px", overflow: "hidden" }}
                >
                  <CarSelector
                    compact
                    submitLabel="Check fitment"
                    onSubmit={(payload) => { setCar(payload); setShowCarSelector(false); }}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        <PhotoGallery urls={galleryUrls} />

        {/* Title + price */}
        <div>
          <p style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--ff-display)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
            {item.category_name}
          </p>
          {isAssemblyItem && (
            <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.25 }}>
              {item.title}
            </h1>
          )}
          {vehicleName && (
            <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>From: {vehicleName}</p>
          )}
          <p style={{ fontSize: 26, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginTop: 10 }}>
            {formatMoney(item.price)}
          </p>
        </div>

        {/* Badges */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[
            item.condition && item.condition.replace(/_/g, " "),
            item.shipping_size && `📦 ${item.shipping_size}`,
            item.oem_part_number ? `OEM ${item.oem_part_number}` : null,
          ].filter(Boolean).map((b, i) => (
            <span key={i} style={{ fontSize: 11, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 6, padding: "3px 9px", color: "var(--text-secondary)" }}>
              {b}
            </span>
          ))}
        </div>

        {/* Item attributes (Side, Bulb type, etc.) */}
        {itemOptions.length > 0 && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {itemOptions.map((o) => (
              <span
                key={o.id}
                style={{
                  fontSize: 12, fontWeight: 600,
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 7, padding: "5px 12px",
                  color: "var(--text-primary)",
                }}
              >
                {o.option_category_name}: {o.value}
              </span>
            ))}
          </div>
        )}

        {/* Add to cart / In cart / Sold */}
        {item?.status !== "hidden_in_assembly" && (
          <div style={{ display: "flex", gap: 10 }}>
            {item?.status !== "active" ? (
              <div style={{
                flex: 1, padding: "13px 0", fontSize: 14, fontWeight: 700,
                fontFamily: "var(--ff-display)", borderRadius: 10,
                background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)",
                color: "#f87171", textAlign: "center",
              }}>
                Sold — no longer available
              </div>
            ) : inCart ? (
              <button
                type="button"
                onClick={handleRemoveFromCart}
                disabled={adding}
                style={{
                  flex: 1, padding: "13px 0", fontSize: 14, fontWeight: 700,
                  fontFamily: "var(--ff-display)", borderRadius: 10,
                  background: "var(--bg-elevated)", color: "var(--text-primary)", cursor: "pointer",
                  opacity: adding ? 0.6 : 1,
                  border: "1px solid var(--border)",
                }}
              >
                {adding ? "Removing…" : "✓ In Cart — Remove"}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleAddToCart}
                disabled={adding}
                style={{
                  flex: 1, padding: "13px 0", fontSize: 14, fontWeight: 700,
                  fontFamily: "var(--ff-display)", borderRadius: 10, border: "none",
                  background: "var(--primary)", color: "#fff", cursor: "pointer",
                  opacity: adding ? 0.6 : 1,
                }}
              >
                {adding ? "Adding…" : "Add to cart"}
              </button>
            )}
            <Link
              href="/cart"
              style={{
                padding: "13px 20px", fontSize: 14, fontWeight: 600, borderRadius: 10,
                border: "1px solid var(--border)", color: "var(--text-secondary)", textDecoration: "none",
                display: "flex", alignItems: "center",
              }}
            >
              Cart
            </Link>
          </div>
        )}

        {/* Donor vehicle specs from modification */}
        {donorSpecs.length > 0 && (
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 8 }}>Specifications</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 16px" }}>
              {donorSpecs.map((s) => (
                <div key={s.label}>
                  <span style={{ fontSize: 10, color: "var(--text-muted)", display: "block" }}>{s.label}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Description */}
        {item.description && (
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 8 }}>Description</p>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{item.description}</p>
          </div>
        )}

        {/* Donor vehicle */}
        {vehicleLabel && (
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 8 }}>Donor vehicle</p>
            <p style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 4 }}>
              {vehicleLabel}
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {item.vehicle_mileage != null && (
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{item.vehicle_mileage.toLocaleString()} mi</span>
              )}
              {item.vehicle_condition && (
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>· {item.vehicle_condition.replace(/_/g, " ")} condition</span>
              )}
            </div>
          </div>
        )}

        {/* Compatibility */}
        <CompatibilitySection compatibilities={verifiedCompats} />

        {/* Seller */}
        {item.seller_id && (
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 8 }}>Seller</p>
            <div className="flex items-start justify-between gap-3">
              <div>
                <Link href={`/sellers/${item.seller_id}`} style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", textDecoration: "none" }}>
                  {item.seller_name}
                </Link>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  {item.seller_rating_avg != null ? (
                    <>
                      <Stars value={item.seller_rating_avg} />
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        {item.seller_rating_avg.toFixed(1)} ({item.seller_review_count} reviews)
                      </span>
                    </>
                  ) : (
                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>No reviews yet</span>
                  )}
                </div>
                {item.seller_member_since && (
                  <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>Member since {item.seller_member_since}</p>
                )}
              </div>
              <Link href={`/sellers/${item.seller_id}`} style={{ fontSize: 12, fontWeight: 600, padding: "6px 14px", borderRadius: 8, border: "1px solid var(--border)", color: "var(--text-secondary)", textDecoration: "none", flexShrink: 0 }}>
                Profile →
              </Link>
            </div>
          </div>
        )}

        {/* Message seller */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "16px" }}>
          <p style={{ fontSize: 13, fontWeight: 700, fontFamily: "var(--ff-display)", color: "var(--text-primary)", marginBottom: 8 }}>
            Message the seller
          </p>
          <form onSubmit={handleMessage}>
            <textarea
              value={messageBody}
              onChange={(e) => setMessageBody(e.target.value)}
              rows={3}
              placeholder="Ask about fitment, condition, or availability…"
              disabled={messaging}
              style={{
                width: "100%", resize: "vertical", background: "var(--bg-elevated)",
                border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px",
                fontSize: 13, color: "var(--text-primary)", fontFamily: "var(--ff-body)", outline: "none",
              }}
            />
            <button
              type="submit"
              disabled={messaging || !messageBody.trim()}
              style={{
                marginTop: 8, padding: "8px 20px", fontSize: 13, fontWeight: 600,
                background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8,
                color: "var(--text-secondary)", cursor: "pointer", opacity: (messaging || !messageBody.trim()) ? 0.5 : 1,
              }}
            >
              {messaging ? "Sending…" : "Send"}
            </button>
          </form>
        </div>

      </motion.div>
    </div>
  );
}
