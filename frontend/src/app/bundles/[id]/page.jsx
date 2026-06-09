"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, addBundleToCart, apiFetch, getBundle } from "@/lib/api";
import { formatShippingEstimate } from "@/lib/shipping-rates";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

function BundleHeroImage({ bundle }) {
  const [failed, setFailed] = useState(0);
  const srcs = [bundle.primary_photo_url, bundle.bundle_category_image_url].filter(Boolean);
  const src = srcs[failed];
  if (!src) return null;
  return (
    <div className="rounded-2xl overflow-hidden" style={{ border: "1px solid var(--border)", aspectRatio: "16/9" }}>
      <img
        key={src}
        src={src}
        alt={bundle.name}
        className="w-full h-full object-cover"
        onError={() => setFailed((f) => f + 1)}
      />
    </div>
  );
}

function ItemImage({ item }) {
  const srcs = [...(item.photo_urls || []), item.primary_photo_url, item.category_image_url].filter(Boolean);
  const [failed, setFailed] = useState(0);
  const src = srcs[failed];
  if (!src) {
    return (
      <div style={{ width: 56, height: 56, borderRadius: 8, background: "var(--bg-elevated)", border: "1px solid var(--border)", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" style={{ opacity: 0.3 }}>
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
          <polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" />
        </svg>
      </div>
    );
  }
  return (
    <div style={{ width: 56, height: 56, borderRadius: 8, overflow: "hidden", flexShrink: 0, border: "1px solid var(--border)" }}>
      <img key={src} src={src} alt={item.title || item.category_name} className="w-full h-full object-cover" onError={() => setFailed((f) => f + 1)} />
    </div>
  );
}

export default function BundleDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [adding, setAdding] = useState(false);
  const [messageBody, setMessageBody] = useState("");
  const [messaging, setMessaging] = useState(false);

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

  async function handleMessage(e) {
    e.preventDefault();
    if (!user) { window.location.href = `/login?next=/bundles/${id}`; return; }
    if (!messageBody.trim()) return;
    const firstItemId = items[0]?.id;
    if (!firstItemId) return;
    setMessaging(true);
    try {
      const thread = await apiFetch("/messages/start/", {
        method: "POST",
        body: JSON.stringify({ item_id: firstItemId, body: messageBody.trim() }),
      });
      toast.success("Message sent.");
      window.location.href = `/inbox?thread=${thread.id}`;
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Could not send message.");
    } finally {
      setMessaging(false);
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
  const seller = items[0] ? { id: items[0].seller_id, name: items[0].seller_name } : null;

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-10">
      <Link href="/search" style={{ color: "var(--text-muted)", fontSize: 12, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 20 }}>
        ← Back to search
      </Link>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="space-y-5">

        {/* Hero image with fallback */}
        <BundleHeroImage bundle={bundle} />

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
                <span style={{ fontSize: 11, fontWeight: 700, background: "rgba(74,222,128,0.12)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.3)", borderRadius: 5, padding: "2px 8px" }}>
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
          style={{ width: "100%", padding: "13px 0", fontSize: 14, fontWeight: 700, fontFamily: "var(--ff-display)", borderRadius: 10, border: "none", background: "var(--primary)", color: "#fff", cursor: "pointer", opacity: adding ? 0.6 : 1 }}
        >
          {adding ? "Adding…" : `Add all ${bundle.item_count} parts to cart`}
        </button>

        {/* Included parts — scrollable, full details */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}>
          <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 10 }}>
            {bundle.item_count} part{bundle.item_count !== 1 ? "s" : ""} included
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12, maxHeight: 480, overflowY: "auto", paddingRight: 2 }}>
            {items.map((item) => {
              const vehicleStr = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean).join(" ");
              return (
                <Link
                  key={item.id}
                  href={`/browse/parts/${item.id}`}
                  style={{ display: "flex", gap: 10, alignItems: "flex-start", textDecoration: "none", color: "inherit" }}
                >
                  <ItemImage item={item} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.3, marginBottom: 2 }}>
                      {item.category_name || item.title}
                    </p>
                    {vehicleStr && (
                      <p style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 2 }}>From: {vehicleStr}</p>
                    )}
                    {/* Part numbers */}
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 2 }}>
                      {item.oem_part_number && (
                        <span style={{ fontSize: 10, fontFamily: "var(--ff-mono)", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
                          OEM {item.oem_part_number}
                        </span>
                      )}
                      {(item.alt_part_numbers || []).slice(0, 2).map((p) => (
                        <span key={p.id || p.number} style={{ fontSize: 10, fontFamily: "var(--ff-mono)", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
                          {p.number}
                        </span>
                      ))}
                    </div>
                    {/* Options */}
                    {(item.options || []).length > 0 && (
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 2 }}>
                        {(item.options || []).map((o) => (
                          <span key={o.id} style={{ fontSize: 10, fontWeight: 600, background: "var(--primary-muted)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--primary)" }}>
                            {o.option_category_name}: {o.value}
                          </span>
                        ))}
                      </div>
                    )}
                    {/* Size + condition */}
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {item.condition && (
                        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{item.condition.replace(/_/g, " ")}</span>
                      )}
                      {item.shipping_size && (
                        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>· {item.shipping_size}</span>
                      )}
                    </div>
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", flexShrink: 0 }}>
                    {formatMoney(item.price)}
                  </span>
                </Link>
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

        {/* Seller + message */}
        {seller?.id && (
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
              <div>
                <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 4 }}>Seller</p>
                <Link href={`/sellers/${seller.id}`} style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", textDecoration: "none" }}>
                  {seller.name}
                </Link>
              </div>
              <Link href={`/sellers/${seller.id}`} style={{ fontSize: 12, fontWeight: 600, padding: "6px 14px", borderRadius: 8, border: "1px solid var(--border)", color: "var(--text-secondary)", textDecoration: "none", flexShrink: 0 }}>
                Profile →
              </Link>
            </div>
            <p style={{ fontSize: 13, fontWeight: 700, fontFamily: "var(--ff-display)", color: "var(--text-primary)", marginBottom: 8 }}>
              Message the seller
            </p>
            <form onSubmit={handleMessage}>
              <textarea
                value={messageBody}
                onChange={(e) => setMessageBody(e.target.value)}
                rows={3}
                placeholder="Ask about this bundle, availability, or condition…"
                disabled={messaging}
                style={{ width: "100%", resize: "vertical", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px", fontSize: 13, color: "var(--text-primary)", fontFamily: "var(--ff-body)", outline: "none", boxSizing: "border-box" }}
              />
              <button
                type="submit"
                disabled={messaging || !messageBody.trim()}
                style={{ marginTop: 8, padding: "8px 20px", fontSize: 13, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text-secondary)", cursor: "pointer", opacity: (messaging || !messageBody.trim()) ? 0.5 : 1 }}
              >
                {messaging ? "Sending…" : "Send"}
              </button>
            </form>
          </div>
        )}

      </motion.div>
    </div>
  );
}
