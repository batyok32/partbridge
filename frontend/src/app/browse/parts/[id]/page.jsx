"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { effectivePartBuyPrice } from "@/lib/part-pricing";
import { BROWSE_PREFS_KEY, readSavedBuyerZip, writeSavedBuyerZip } from "@/lib/browse-prefs";
import { returnPolicyBadgeLabel, returnPolicyBrief } from "@/lib/return-policy";

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
  const key = part?.part_family?.category?.illustration_key;
  return ILLUSTRATION_EMOJI[key] || "📦";
}

function formatCondition(code) {
  if (!code) return "—";
  return String(code).replace(/_/g, " ");
}

/** Scroll-snap gallery for part + vehicle photos */
function PhotoGallery({ urls }) {
  const scrollerRef = useRef(null);
  const [active, setActive] = useState(0);
  const list = Array.isArray(urls) ? urls.filter(Boolean) : [];
  const n = list.length;

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollLeft = 0;
    setActive(0);
  }, [urls]);

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
  }, [n]);

  if (n === 0) {
    return (
      <div
        className="flex aspect-[16/10] w-full items-center justify-center rounded-2xl text-7xl"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
      >
        📦
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-hidden rounded-2xl" style={{ border: "1px solid var(--border)" }}>
      <div
        ref={scrollerRef}
        className="flex aspect-[16/10] w-full snap-x snap-mandatory overflow-x-auto overflow-y-hidden [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
        style={{ touchAction: "pan-x", WebkitOverflowScrolling: "touch" }}
      >
        {list.map((url, i) => (
          <div key={`${url}-${i}`} className="h-full w-full shrink-0 snap-center" style={{ minWidth: "100%" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={url} alt="" className="h-full w-full object-cover" draggable={false} />
          </div>
        ))}
      </div>
      {n > 1 && (
        <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5">
          {list.map((_, i) => (
            <span
              key={i}
              className="h-1.5 rounded-full transition-all"
              style={{
                width: active === i ? 18 : 6,
                background: active === i ? "var(--primary)" : "rgba(255,255,255,0.35)",
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function PublicPartDetailPage() {
  const { id: rawId } = useParams();
  const { user } = useAuth();
  const toast = useToast();

  const id = useMemo(() => {
    const n = Number(rawId);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [rawId]);

  const [part, setPart] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [buyerZip, setBuyerZip] = useState("");
  const [shippingMode, setShippingMode] = useState("standard");
  const [cartNotes, setCartNotes] = useState("");
  const [cartOpen, setCartOpen] = useState(false);
  const [busyCart, setBusyCart] = useState(false);

  useEffect(() => {
    setBuyerZip(readSavedBuyerZip());
  }, []);

  const loadPart = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setNotFound(false);
    try {
      const qs = new URLSearchParams();
      const z = buyerZip.trim();
      if (z) qs.set("buyer_zip", z);
      const q = qs.toString();
      const path = `/browse/parts/${id}/` + (q ? `?${q}` : "");
      const data = await apiFetch(path, { auth: false });
      setPart(data);
      const opts = data.shipping_preview?.shipping_options || [];
      const codes = new Set(opts.map((o) => o.code));
      setShippingMode((prev) => {
        if (codes.has(prev)) return prev;
        return opts[0]?.code || prev;
      });
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setNotFound(true);
      else if (e instanceof ApiError) toast.error(e.message);
      setPart(null);
    } finally {
      setLoading(false);
    }
  }, [id, buyerZip, toast]);

  useEffect(() => {
    void loadPart();
  }, [loadPart]);

  const eff = part?.listing_state_effective || part?.listing_state;
  const vp = part?.vehicle_public || {};
  const ship = part?.shipping_preview || {};
  const options = Array.isArray(ship.shipping_options) ? ship.shipping_options : [];
  const zipOk = Boolean(buyerZip.trim());
  const headline = [vp.year, vp.make, vp.model].filter(Boolean).join(" ");

  const galleryUrls = useMemo(() => {
    const partUrls = Array.isArray(part?.image_urls) ? part.image_urls.filter(Boolean) : [];
    const veh = vp.photo_urls;
    const vehUrls = Array.isArray(veh) ? veh.map((p) => p.url).filter(Boolean) : [];
    const merged = [...partUrls];
    for (const u of vehUrls) {
      if (!merged.includes(u)) merged.push(u);
    }
    return merged;
  }, [part, vp.photo_urls]);

  const messageHref = user
    ? `/inbox?part=${encodeURIComponent(String(id))}&auto=1&msg=${encodeURIComponent(`Hi, I'm interested in ${part?.label || "this part"}. Is it still available?`)}`
    : `/login?next=${encodeURIComponent(typeof window !== "undefined" ? window.location.pathname : `/browse/parts/${id}`)}`;

  async function addToCart() {
    if (!user || !part) return;
    if (shippingMode !== "pickup" && !buyerZip.trim()) {
      toast.warning("Enter your ZIP before adding to cart.");
      return;
    }
    setBusyCart(true);
    try {
      await apiFetch("/cart/", {
        method: "POST",
        body: JSON.stringify({
          vehicle_part_id: part.id,
          quantity: 1,
          shipping_mode: shippingMode,
          buyer_zip: buyerZip.trim(),
          ...(cartNotes.trim() ? { buyer_notes: cartNotes.trim() } : {}),
        }),
      });
      toast.success("Added to cart.");
      setCartOpen(false);
      setCartNotes("");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setBusyCart(false);
    }
  }

  function persistZip(z) {
    setBuyerZip(z);
    try {
      const raw = localStorage.getItem(BROWSE_PREFS_KEY);
      const j = raw ? JSON.parse(raw) : {};
      j.buyerZip = z;
      localStorage.setItem(BROWSE_PREFS_KEY, JSON.stringify(j));
    } catch {
      writeSavedBuyerZip(z);
    }
  }

  if (!id) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Invalid part.</p>
      </div>
    );
  }

  if (loading && !part) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading part…</p>
      </div>
    );
  }

  if (notFound || !part) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="heading-display text-xl mb-2">Part not found</h1>
        <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
          This listing may have sold, expired, or been removed from search.
        </p>
        <Link href="/browse" className="btn-forge inline-flex" style={{ padding: "10px 20px", fontSize: 14 }}>
          Back to browse
        </Link>
      </div>
    );
  }

  const buyPrice = effectivePartBuyPrice(part);
  const listNum = part.price != null && part.price !== "" ? Number(part.price) : null;
  const showOffer =
    buyPrice != null &&
    listNum != null &&
    Number.isFinite(listNum) &&
    Math.abs(buyPrice - listNum) > 0.005;
  const canBuy = eff === "buy_now" && buyPrice != null;

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-10">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-25" />

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="relative z-10">
        <nav className="mb-6 flex flex-wrap items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
          <Link href="/browse" className="hover:underline" style={{ color: "var(--primary)" }}>Browse</Link>
          <span aria-hidden>/</span>
          {vp.vehicle_id ? (
            <>
              <Link href={`/browse/vehicles/${vp.vehicle_id}`} className="hover:underline" style={{ color: "var(--primary)" }}>
                {headline || "Vehicle"}
              </Link>
              <span aria-hidden>/</span>
            </>
          ) : null}
          <span className="truncate" style={{ color: "var(--text-secondary)" }}>{part.label}</span>
        </nav>

        <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:items-start">
          <div>
            {galleryUrls.length > 0 ? (
              <PhotoGallery urls={galleryUrls} />
            ) : (
              <div
                className="flex aspect-[16/10] w-full items-center justify-center rounded-2xl text-7xl"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
              >
                {categoryEmoji(part)}
              </div>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              {eff === "buy_now" && (
                <span className="rounded-full px-2.5 py-0.5 text-xs font-bold" style={{ background: "var(--primary)", color: "#fff" }}>
                  Buy now
                </span>
              )}
              {eff === "sold" && (
                <span className="rounded-full px-2.5 py-0.5 text-xs font-bold" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
                  Sold
                </span>
              )}
              <span
                className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                style={{
                  background: "var(--success-muted)",
                  border: "1px solid color-mix(in srgb, var(--success) 35%, transparent)",
                  color: "var(--success)",
                }}
              >
                {returnPolicyBadgeLabel(part.return_policy)}
              </span>
              {part.is_damaged && (
                <span className="rounded-full px-2.5 py-0.5 text-xs font-medium" style={{ background: "rgba(245,158,11,0.15)", color: "#fbbf24" }}>
                  May have damage
                </span>
              )}
            </div>

            <h1 className="heading-display mt-4 text-2xl sm:text-3xl" style={{ color: "var(--text-primary)" }}>
              {part.label}
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
              {part.part_family?.category?.name} · {part.part_family?.name}
              {part.variant_key ? ` · ${part.variant_key}` : ""}
            </p>

            {buyPrice != null && (
              <p className="price-mono mt-3 text-3xl font-bold tabular-nums" style={{ color: "var(--primary-bright)" }}>
                {showOffer && listNum != null && (
                  <span className="mr-2 text-xl font-semibold line-through opacity-60" style={{ color: "var(--text-muted)" }}>
                    {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(listNum)}
                  </span>
                )}
                {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(buyPrice)}
              </p>
            )}

            {part.offer_expires_at && showOffer && eff === "buy_now" && (
              <p className="mt-2 text-xs font-medium" style={{ color: "var(--primary)" }}>
                Limited offer ends {new Date(part.offer_expires_at).toLocaleString()}
              </p>
            )}

            {part.buy_now_expires_at && eff === "buy_now" && (
              <p className="mt-2 text-xs" style={{ color: "var(--warning)" }}>
                Buy Now ends {new Date(part.buy_now_expires_at).toLocaleString()}
              </p>
            )}
          </div>

          <div
            className="space-y-5 rounded-2xl p-5 lg:sticky lg:top-24"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <div>
              <p className="section-label mb-2">Shipping estimate</p>
              <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>Your ZIP</label>
              <div className="flex gap-2">
                <input
                  value={buyerZip}
                  onChange={(e) => persistZip(e.target.value)}
                  placeholder="98101"
                  className="input-forge flex-1"
                  maxLength={10}
                />
                <button
                  type="button"
                  className="rounded-lg px-3 text-sm font-semibold"
                  style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", color: "var(--text-secondary)" }}
                  onClick={() => void loadPart()}
                >
                  Update
                </button>
              </div>
              {!zipOk && (
                <p className="mt-2 text-xs" style={{ color: "var(--warning)" }}>Enter ZIP to see tier and delivery options.</p>
              )}
            </div>

            {zipOk && options.length > 0 && (
              <div>
                <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                  Service level
                </p>
                <div className="flex flex-wrap gap-2">
                  {options.map((opt) => (
                    <label
                      key={opt.code}
                      className="cursor-pointer rounded-lg px-3 py-2 text-xs font-semibold transition-colors"
                      style={{
                        border: shippingMode === opt.code ? "1px solid var(--primary-border-strong)" : "1px solid var(--border)",
                        background: shippingMode === opt.code ? "var(--primary-muted)" : "var(--bg-elevated)",
                        color: shippingMode === opt.code ? "var(--primary)" : "var(--text-secondary)",
                      }}
                    >
                      <input
                        type="radio"
                        className="sr-only"
                        name="ship-mode"
                        checked={shippingMode === opt.code}
                        onChange={() => setShippingMode(opt.code)}
                      />
                      {opt.label} · {Number(opt.usd) === 0 ? "Free" : `$${opt.usd}`}
                    </label>
                  ))}
                </div>
                {ship.estimate && (
                  <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>{ship.estimate}</p>
                )}
                {ship.disclaimer && (
                  <p className="mt-1 text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>{ship.disclaimer}</p>
                )}
              </div>
            )}

            <div className="flex flex-col gap-2 sm:flex-row">
              <Link href={messageHref} className="btn-ghost flex flex-1 justify-center py-2.5 text-sm">
                Message seller
              </Link>
              {canBuy && (
                <Link
                  href={`/checkout?part=${encodeURIComponent(String(part.id))}&shipping=${encodeURIComponent(shippingMode)}`}
                  className="btn-forge flex flex-1 justify-center py-2.5 text-center text-sm"
                >
                  Buy now
                </Link>
              )}
              {canBuy && user && (
                <button
                  type="button"
                  className="btn-ghost flex flex-1 justify-center py-2.5 text-sm"
                  onClick={() => setCartOpen(true)}
                >
                  Add to cart
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Detail sections */}
        <div className="mt-10 grid gap-6 sm:grid-cols-2">
          <section
            className="rounded-2xl p-5"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <h2 className="text-sm font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
              Description
            </h2>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {part.description?.trim() || "No description provided."}
            </p>
          </section>

          <section
            className="rounded-2xl p-5"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <h2 className="text-sm font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
              Condition
            </h2>
            <p className="mt-2 text-sm capitalize" style={{ color: "var(--text-primary)" }}>
              {formatCondition(part.condition_draft)}
            </p>
            {part.condition_description?.trim() && (
              <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {part.condition_description}
              </p>
            )}
          </section>
        </div>

        {(part.color_override ||
          part.location_note ||
          part.size_length_cm != null ||
          part.size_packaged_length_cm != null) && (
          <section
            className="mt-6 rounded-2xl p-5"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <h2 className="text-sm font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
              Details & dimensions
            </h2>
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
              {part.color_override?.trim() && (
                <>
                  <dt style={{ color: "var(--text-muted)" }}>Color</dt>
                  <dd style={{ color: "var(--text-secondary)" }}>{part.color_override}</dd>
                </>
              )}
              {part.location_note?.trim() && (
                <>
                  <dt style={{ color: "var(--text-muted)" }}>Location note</dt>
                  <dd style={{ color: "var(--text-secondary)" }}>{part.location_note}</dd>
                </>
              )}
              {(part.size_length_cm != null || part.size_width_cm != null || part.size_height_cm != null) && (
                <>
                  <dt style={{ color: "var(--text-muted)" }}>Part size (L×W×H cm)</dt>
                  <dd className="price-mono" style={{ color: "var(--text-secondary)" }}>
                    {[part.size_length_cm, part.size_width_cm, part.size_height_cm].map((x) => (x != null ? Number(x).toFixed(1) : "—")).join(" × ")}
                  </dd>
                </>
              )}
              {(part.size_packaged_length_cm != null ||
                part.size_packaged_width_cm != null ||
                part.size_packaged_height_cm != null) && (
                <>
                  <dt style={{ color: "var(--text-muted)" }}>Packaged (L×W×H cm)</dt>
                  <dd className="price-mono" style={{ color: "var(--text-secondary)" }}>
                    {[part.size_packaged_length_cm, part.size_packaged_width_cm, part.size_packaged_height_cm]
                      .map((x) => (x != null ? Number(x).toFixed(1) : "—"))
                      .join(" × ")}
                  </dd>
                </>
              )}
            </dl>
          </section>
        )}

        <section
          className="mt-6 rounded-2xl p-5"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <h2 className="text-sm font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Donor vehicle
          </h2>
          <div className="mt-3 flex flex-wrap gap-3 text-sm" style={{ color: "var(--text-secondary)" }}>
            <span>{headline || "—"}</span>
            {vp.trim && <span>· {vp.trim}</span>}
            {vp.engine && <span>· {vp.engine}</span>}
            {vp.transmission && <span>· {vp.transmission}</span>}
            {vp.drivetrain && <span>· {vp.drivetrain}</span>}
            {vp.color && <span>· {vp.color}</span>}
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
            Ships from {vp.location_state || "—"} {vp.location_zip_masked || ""}
            {vp.has_damage ? " · vehicle may have reported damage" : ""}
          </p>
          {vp.vehicle_id && (
            <Link
              href={`/browse/vehicles/${vp.vehicle_id}`}
              className="mt-3 inline-block text-sm font-semibold"
              style={{ color: "var(--primary)" }}
            >
              View all parts from this vehicle →
            </Link>
          )}
        </section>

        <section
          className="mt-6 rounded-2xl p-5"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <h2 className="text-sm font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Returns
          </h2>
          <p className="mt-2 text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            {returnPolicyBrief(part.return_policy)}
          </p>
        </section>

        <p className="mt-8 text-xs" style={{ color: "var(--text-muted)" }}>
          Listing updated {part.updated_at ? new Date(part.updated_at).toLocaleString() : "—"}
          {part.created_at ? ` · created ${new Date(part.created_at).toLocaleDateString()}` : ""}
        </p>
      </motion.div>

      {cartOpen && canBuy && user && (
        <div className="fixed inset-0 z-[100] flex items-end justify-center p-4 sm:items-center" role="dialog" aria-modal>
          <div className="absolute inset-0 bg-black/60" onClick={() => setCartOpen(false)} />
          <div
            className="relative z-10 w-full max-w-md p-5"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", boxShadow: "var(--shadow-xl)" }}
          >
            <p className="text-sm font-semibold" style={{ fontFamily: "var(--ff-display)", color: "var(--text-primary)" }}>Add to cart</p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>{part.label}</p>
            <label className="mt-3 block">
              <span className="text-xs font-medium" style={{ color: "var(--text-secondary)", fontFamily: "var(--ff-display)" }}>
                Note for the seller <span style={{ fontWeight: 400, color: "var(--text-muted)" }}>(optional)</span>
              </span>
              <textarea
                value={cartNotes}
                onChange={(e) => setCartNotes(e.target.value)}
                rows={3}
                placeholder="e.g. Driver side (LH), color…"
                className="input-forge mt-1 w-full resize-none"
                style={{ minHeight: 80 }}
              />
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCartOpen(false)}
                className="rounded-lg px-4 py-2 text-sm"
                style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button type="button" onClick={() => void addToCart()} disabled={busyCart} className="btn-forge" style={{ padding: "8px 20px", fontSize: 13 }}>
                {busyCart ? "Adding…" : "Add to cart"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
