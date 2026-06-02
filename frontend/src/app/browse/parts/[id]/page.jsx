"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch, getItem } from "@/lib/api";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

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
      setActive(Math.min(Math.max(0, Math.round(el.scrollLeft / w)), n - 1));
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [n]);

  if (n === 0) {
    return (
      <div className="flex aspect-[16/10] w-full items-center justify-center rounded-2xl text-7xl"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
        📦
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-hidden rounded-2xl" style={{ border: "1px solid var(--border)" }}>
      <div
        ref={scrollerRef}
        className="flex aspect-[16/10] w-full snap-x snap-mandatory overflow-x-auto overflow-y-hidden [scrollbar-width:none]"
        style={{ touchAction: "pan-x" }}
      >
        {list.map((url, i) => (
          <div key={i} className="h-full w-full shrink-0 snap-center" style={{ minWidth: "100%" }}>
            <img src={url} alt="" className="h-full w-full object-cover" draggable={false} />
          </div>
        ))}
      </div>
      {n > 1 && (
        <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5">
          {list.map((_, i) => (
            <span key={i} className="h-1.5 rounded-full transition-all"
              style={{ width: active === i ? 18 : 6, background: active === i ? "var(--primary)" : "rgba(255,255,255,0.35)" }} />
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

  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [adding, setAdding] = useState(false);
  const [messageBody, setMessageBody] = useState("");
  const [messaging, setMessaging] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getItem(id)
      .then((data) => setItem(data))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else if (e instanceof ApiError) toast.error(e.message);
      })
      .finally(() => setLoading(false));
  }, [id, toast]);

  async function handleAddToCart() {
    if (!user) { window.location.href = `/login?next=/browse/parts/${id}`; return; }
    setAdding(true);
    try {
      await apiFetch("/cart/", { method: "POST", body: JSON.stringify({ item: id }) });
      toast.success("Added to cart.");
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

  if (loading) {
    return <div className="mx-auto max-w-2xl px-6 py-16"><p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</p></div>;
  }

  if (notFound || !item) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16 text-center">
        <p style={{ fontSize: 32, marginBottom: 8 }}>🔍</p>
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Part not found.</p>
        <Link href="/browse" style={{ color: "var(--primary)", fontSize: 13, marginTop: 12, display: "inline-block" }}>← Browse parts</Link>
      </div>
    );
  }

  const galleryUrls = (item.photos || []).map((p) => p.url).filter(Boolean);
  const vehicleName = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean).join(" ");
  const survivingOptions = (item.options || []).filter((o) => !o.is_ai_eliminated);

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-10">
      <Link href="/browse" style={{ color: "var(--text-muted)", fontSize: 12, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 20 }}>
        ← Back to browse
      </Link>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="space-y-6">
        <PhotoGallery urls={galleryUrls} />

        {/* Title + price */}
        <div>
          <p style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--ff-display)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
            {item.category_name}
          </p>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.25 }}>
            {item.title}
          </h1>
          {vehicleName && (
            <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>From: {vehicleName}</p>
          )}
          <p style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginTop: 10 }}>
            {formatMoney(item.price)}
          </p>
        </div>

        {/* Badges */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[
            item.condition?.replace(/_/g, " "),
            `📦 ${item.shipping_size}`,
            item.oem_part_number ? `OEM ${item.oem_part_number}` : null,
          ].filter(Boolean).map((b, i) => (
            <span key={i} style={{ fontSize: 11, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 6, padding: "3px 9px", color: "var(--text-secondary)" }}>
              {b}
            </span>
          ))}
        </div>

        {/* Options */}
        {survivingOptions.length > 0 && (
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 8 }}>Options</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {survivingOptions.map((o) => (
                <span key={o.id} style={{ fontSize: 12, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 6, padding: "3px 9px", color: "var(--text-primary)" }}>
                  {o.option_category_name}: {o.value}
                </span>
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

        {/* Actions */}
        <div style={{ display: "flex", gap: 10 }}>
          <button
            type="button"
            onClick={handleAddToCart}
            disabled={adding}
            style={{
              flex: 1, padding: "12px 0", fontSize: 14, fontWeight: 700,
              fontFamily: "var(--ff-display)", borderRadius: 10, border: "none",
              background: "var(--primary)", color: "#fff", cursor: "pointer",
              opacity: adding ? 0.6 : 1,
            }}
          >
            {adding ? "Adding…" : "Add to cart"}
          </button>
          <Link
            href="/cart"
            style={{
              padding: "12px 20px", fontSize: 14, fontWeight: 600, borderRadius: 10,
              border: "1px solid var(--border)", color: "var(--text-secondary)", textDecoration: "none",
              display: "flex", alignItems: "center",
            }}
          >
            Cart
          </Link>
        </div>

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
