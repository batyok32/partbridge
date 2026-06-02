"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch, getCategories, getItems, getMakes } from "@/lib/api";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

function conditionLabel(c) {
  return { excellent: "Excellent", good: "Good", fair: "Fair", for_parts: "For parts" }[c] || c || "—";
}

function sizeLabel(s) {
  return { small: "Small", medium: "Medium", large: "Large", xl: "Extra Large" }[s] || s || "—";
}

function ItemCard({ item, user, onAddToCart }) {
  const [adding, setAdding] = useState(false);
  const vehicleName = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean).join(" ") || "—";

  async function handleCart() {
    if (!user) { window.location.href = `/login?next=/browse`; return; }
    setAdding(true);
    try {
      await onAddToCart(item.id);
    } finally {
      setAdding(false);
    }
  }

  return (
    <div
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-xl)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Photo */}
      <div style={{ aspectRatio: "16/10", background: "var(--bg-elevated)", position: "relative", overflow: "hidden" }}>
        {item.primary_photo_url ? (
          <img src={item.primary_photo_url} alt={item.title} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-muted)", fontSize: 32 }}>📦</div>
        )}
        <span style={{
          position: "absolute", top: 8, left: 8,
          background: "rgba(0,0,0,0.6)", borderRadius: 6, padding: "2px 8px",
          fontSize: 11, color: "#fff", fontFamily: "var(--ff-display)", fontWeight: 600,
        }}>
          {item.category_name}
        </span>
      </div>

      {/* Body */}
      <div style={{ padding: "12px 14px", flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
        <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.3 }}>{item.title}</p>
        <p style={{ fontSize: 11, color: "var(--text-muted)" }}>{vehicleName}</p>

        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 2 }}>
          <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-secondary)" }}>
            {conditionLabel(item.condition)}
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-secondary)" }}>
            📦 {sizeLabel(item.shipping_size)}
          </span>
          {item.oem_part_number && (
            <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--ff-mono)" }}>OEM {item.oem_part_number}</span>
          )}
        </div>

        <div style={{ marginTop: "auto", paddingTop: 10, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
            {formatMoney(item.price)}
          </span>
          <div style={{ display: "flex", gap: 6 }}>
            <Link
              href={`/browse/parts/${item.id}`}
              style={{
                fontSize: 12, fontWeight: 600, padding: "6px 12px", borderRadius: 8,
                border: "1px solid var(--border)", color: "var(--text-secondary)", textDecoration: "none",
              }}
            >
              Details
            </Link>
            <button
              type="button"
              onClick={handleCart}
              disabled={adding}
              style={{
                fontSize: 12, fontWeight: 600, padding: "6px 12px", borderRadius: 8,
                background: "var(--primary)", color: "#fff", border: "none", cursor: "pointer",
                opacity: adding ? 0.6 : 1,
              }}
            >
              {adding ? "…" : "Add to cart"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function BrowseContent() {
  const { user } = useAuth();
  const toast = useToast();
  const searchParams = useSearchParams();

  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [makes, setMakes] = useState([]);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState(searchParams.get("q") || "");
  const [categorySlug, setCategorySlug] = useState(searchParams.get("category") || "");
  const [makeId, setMakeId] = useState(searchParams.get("make") || "");
  const [condition, setCondition] = useState(searchParams.get("condition") || "");

  useEffect(() => {
    getCategories().then((d) => setCategories(Array.isArray(d) ? d : [])).catch(() => {});
    getMakes().then((d) => setMakes(Array.isArray(d) ? d : d?.results || [])).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const params = {};
        if (search.trim()) params.q = search.trim();
        if (categorySlug) params.category = categorySlug;
        if (makeId) params.make = makeId;
        if (condition) params.condition = condition;
        const data = await getItems(params);
        if (!cancelled) setItems(Array.isArray(data) ? data : data.results || []);
      } catch (e) {
        if (!cancelled && e instanceof ApiError) toast.error(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [search, categorySlug, makeId, condition, toast]);

  async function handleAddToCart(itemId) {
    try {
      await apiFetch("/cart/", { method: "POST", body: JSON.stringify({ item: itemId }) });
      toast.success("Added to cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10">
      <div className="mb-8">
        <p className="section-label mb-1">Marketplace</p>
        <h1 className="heading-display text-2xl">Browse Parts</h1>
      </div>

      {/* Filters */}
      <div
        style={{
          display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 24,
          background: "var(--bg-surface)", border: "1px solid var(--border)",
          borderRadius: "var(--radius-xl)", padding: "16px",
        }}
      >
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search parts…"
          style={{
            flex: "1 1 200px", background: "var(--bg-elevated)", border: "1px solid var(--border)",
            borderRadius: 8, color: "var(--text-primary)", padding: "8px 12px", fontSize: 13,
            outline: "none", fontFamily: "var(--ff-body)",
          }}
        />
        <select
          value={categorySlug}
          onChange={(e) => setCategorySlug(e.target.value)}
          style={{ flex: "0 0 160px", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text-primary)", padding: "8px 10px", fontSize: 13 }}
        >
          <option value="">All categories</option>
          {categories.map((c) => <option key={c.id} value={c.slug}>{c.name}</option>)}
        </select>
        <select
          value={makeId}
          onChange={(e) => setMakeId(e.target.value)}
          style={{ flex: "0 0 140px", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text-primary)", padding: "8px 10px", fontSize: 13 }}
        >
          <option value="">All makes</option>
          {makes.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
        <select
          value={condition}
          onChange={(e) => setCondition(e.target.value)}
          style={{ flex: "0 0 140px", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text-primary)", padding: "8px 10px", fontSize: 13 }}
        >
          <option value="">Any condition</option>
          <option value="excellent">Excellent</option>
          <option value="good">Good</option>
          <option value="fair">Fair</option>
          <option value="for_parts">For parts</option>
        </select>
        {(search || categorySlug || makeId || condition) && (
          <button
            type="button"
            onClick={() => { setSearch(""); setCategorySlug(""); setMakeId(""); setCondition(""); }}
            style={{ fontSize: 12, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Results */}
      {loading ? (
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading parts…</p>
      ) : items.length === 0 ? (
        <div style={{ textAlign: "center", padding: "48px 0" }}>
          <p style={{ fontSize: 32, marginBottom: 8 }}>🔍</p>
          <p style={{ color: "var(--text-muted)", fontSize: 14 }}>No parts found. Try adjusting the filters.</p>
        </div>
      ) : (
        <>
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16 }}>{items.length} part{items.length !== 1 ? "s" : ""}</p>
          <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
            {items.map((item) => (
              <ItemCard key={item.id} item={item} user={user} onAddToCart={handleAddToCart} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function BrowsePage() {
  return (
    <Suspense fallback={<div className="p-10 text-sm" style={{ color: "var(--text-muted)" }}>Loading…</div>}>
      <BrowseContent />
    </Suspense>
  );
}
