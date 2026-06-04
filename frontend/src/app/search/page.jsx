"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import CarSelector from "@/components/CarSelector";
import SearchItemCard from "@/components/SearchItemCard";
import { useAuth } from "@/context/auth-context";
import { useBuyerCar } from "@/context/car-context";
import { useCart } from "@/context/cart-context";
import { useToast } from "@/context/toast-context";
import {
  ApiError,
  addBundleToCart,
  addToCart,
  removeFromCart,
  removeCartBundle,
  getCategories,
  getBundles,
  getGenerations,
  getItems,
  getMakes,
  getModels,
  getOptionFilters,
  getPartNumberAutocomplete,
} from "@/lib/api";

const US_STATES = [
  "AL",
  "AK",
  "AZ",
  "AR",
  "CA",
  "CO",
  "CT",
  "DE",
  "FL",
  "GA",
  "HI",
  "ID",
  "IL",
  "IN",
  "IA",
  "KS",
  "KY",
  "LA",
  "ME",
  "MD",
  "MA",
  "MI",
  "MN",
  "MS",
  "MO",
  "MT",
  "NE",
  "NV",
  "NH",
  "NJ",
  "NM",
  "NY",
  "NC",
  "ND",
  "OH",
  "OK",
  "OR",
  "PA",
  "RI",
  "SC",
  "SD",
  "TN",
  "TX",
  "UT",
  "VT",
  "VA",
  "WA",
  "WV",
  "WI",
  "WY",
];

const SORT_OPTIONS = [
  { value: "newest", label: "Newest first" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "best_match", label: "Best match" },
];

const PAGE_SIZE = 20;
const BUNDLES_PER_PAGE = 6;
const SHELF_STATE_KEY = "pb_bundle_shelf";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

const labelStyle = {
  display: "block",
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "var(--text-muted)",
  marginBottom: 8,
};

function normalizePartNumber(raw) {
  return raw.replace(/[\s\-./]/g, "").toUpperCase();
}

function PartNumberSearch({ value, onChange }) {
  const [input, setInput] = useState(value || "");
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef(null);
  const wrapperRef = useRef(null);

  useEffect(() => {
    if (value !== input) setInput(value || "");
  }, [value]);

  useEffect(() => {
    const handleClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleChange(e) {
    const v = e.target.value;
    setInput(v);
    clearTimeout(debounceRef.current);
    if (v.length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const results = await getPartNumberAutocomplete(v);
        setSuggestions(results);
        setOpen(results.length > 0);
      } catch {
        setSuggestions([]);
      }
    }, 300);
  }

  function handleSelect(suggestion) {
    setInput(suggestion.number);
    setSuggestions([]);
    setOpen(false);
    onChange(suggestion.number);
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") {
      setOpen(false);
      onChange(input);
    }
    if (e.key === "Escape") {
      setOpen(false);
    }
  }

  function handleClear() {
    setInput("");
    setSuggestions([]);
    setOpen(false);
    onChange("");
  }

  return (
    <div ref={wrapperRef} style={{ position: "relative" }}>
      <p style={labelStyle}>Part number</p>
      <div style={{ position: "relative" }}>
        <input
          type="text"
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="OEM or cross-ref number…"
          style={{
            width: "100%",
            fontSize: 12,
            padding: "8px 28px 8px 8px",
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "var(--bg-elevated)",
            color: "var(--text-primary)",
            boxSizing: "border-box",
          }}
        />
        {input && (
          <button
            type="button"
            onClick={handleClear}
            style={{
              position: "absolute",
              right: 6,
              top: "50%",
              transform: "translateY(-50%)",
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
              fontSize: 14,
              lineHeight: 1,
              padding: 0,
            }}
          >
            ×
          </button>
        )}
      </div>
      {open && suggestions.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            zIndex: 50,
            overflow: "hidden",
            boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
          }}
        >
          {suggestions.map((s, i) => (
            <button
              key={i}
              type="button"
              onClick={() => handleSelect(s)}
              style={{
                display: "flex",
                width: "100%",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 10px",
                background: "none",
                border: "none",
                borderBottom:
                  i < suggestions.length - 1
                    ? "1px solid var(--border)"
                    : "none",
                cursor: "pointer",
                textAlign: "left",
                gap: 8,
              }}
            >
              <span
                style={{
                  fontSize: 12,
                  color: "var(--text-primary)",
                  fontWeight: 600,
                }}
              >
                {s.number}
              </span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  padding: "2px 6px",
                  borderRadius: 4,
                  background:
                    s.type === "oem"
                      ? "var(--primary-muted)"
                      : "var(--bg-elevated)",
                  color:
                    s.type === "oem" ? "var(--primary)" : "var(--text-muted)",
                  border: "1px solid var(--border)",
                  whiteSpace: "nowrap",
                }}
              >
                {s.label}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function byCountDesc(a, b) {
  return (b.item_count ?? 0) - (a.item_count ?? 0);
}

function CategoryNav({ categories, activeSlug, onSelect }) {
  const topLevel = categories.filter((c) => !c.parent).sort(byCountDesc);
  const childrenByParent = categories.reduce((acc, c) => {
    if (c.parent) {
      if (!acc[c.parent]) acc[c.parent] = [];
      acc[c.parent].push(c);
    }
    return acc;
  }, {});

  const activeCategory = categories.find((c) => c.slug === activeSlug);
  const activeParent = activeCategory
    ? categories.find((c) => c.id === activeCategory.parent)
    : null;

  // If active is a top-level with children, show its children
  const activeCatIsParent =
    activeCategory && childrenByParent[activeCategory.id]?.length > 0;
  // If active is a child, drill into parent's children list
  const drillParent = activeCategory?.parent
    ? categories.find((c) => c.id === activeCategory.parent)
    : activeCatIsParent
      ? activeCategory
      : null;

  const showChildren = drillParent
    ? (childrenByParent[drillParent.id] || []).slice().sort(byCountDesc)
    : null;

  const btnStyle = (active) => ({
    width: "100%",
    textAlign: "left",
    fontSize: 12,
    padding: "6px 8px",
    borderRadius: 6,
    background: active ? "var(--primary-muted)" : "transparent",
    border: "none",
    cursor: "pointer",
    color: active ? "var(--primary)" : "var(--text-primary)",
    fontWeight: active ? 700 : 400,
  });

  if (showChildren) {
    return (
      <div>
        <button
          type="button"
          onClick={() =>
            onSelect(activeCategory?.parent ? drillParent.slug : "")
          }
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 11,
            color: "var(--primary)",
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: "0 0 8px 0",
            fontWeight: 600,
          }}
        >
          ← {drillParent.name}
        </button>
        {showChildren.map((child) => (
          <button
            key={child.id}
            type="button"
            onClick={() =>
              onSelect(
                activeSlug === child.slug ? drillParent.slug : child.slug,
              )
            }
            style={btnStyle(activeSlug === child.slug)}
          >
            {child.name}
            {child.item_count != null && (
              <span
                style={{
                  color: "var(--text-muted)",
                  marginLeft: 4,
                  fontWeight: 400,
                }}
              >
                ({child.item_count})
              </span>
            )}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div>
      {topLevel.map((cat) => (
        <button
          key={cat.id}
          type="button"
          onClick={() => {
            if (activeSlug === cat.slug) {
              onSelect("");
            } else {
              onSelect(cat.slug);
            }
          }}
          style={btnStyle(activeSlug === cat.slug)}
        >
          {cat.name}
          {cat.item_count != null && (
            <span
              style={{
                color: "var(--text-muted)",
                marginLeft: 4,
                fontWeight: 400,
              }}
            >
              ({cat.item_count})
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function Pagination({ page, totalPages, onPage }) {
  if (totalPages <= 1) return null;

  const pages = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (page > 3) pages.push("...");
    const start = Math.max(2, page - 1);
    const end = Math.min(totalPages - 1, page + 1);
    for (let i = start; i <= end; i++) pages.push(i);
    if (page < totalPages - 2) pages.push("...");
    pages.push(totalPages);
  }

  function btnStyle(active) {
    return {
      width: 34, height: 34,
      display: "flex", alignItems: "center", justifyContent: "center",
      borderRadius: 7,
      border: active ? "1.5px solid var(--primary)" : "1px solid var(--border)",
      background: active ? "var(--primary-muted)" : "var(--bg-elevated)",
      color: active ? "var(--primary)" : "var(--text-primary)",
      fontSize: 13, fontWeight: active ? 700 : 400,
      cursor: "pointer",
    };
  }

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, marginTop: 32, flexWrap: "wrap" }}>
      <button
        type="button"
        disabled={page === 1}
        onClick={() => onPage(page - 1)}
        style={{ ...btnStyle(false), opacity: page === 1 ? 0.35 : 1, cursor: page === 1 ? "default" : "pointer", fontSize: 16 }}
      >
        ←
      </button>
      {pages.map((p, i) =>
        p === "..." ? (
          <span key={`e${i}`} style={{ fontSize: 13, color: "var(--text-muted)", padding: "0 2px" }}>…</span>
        ) : (
          <button key={p} type="button" onClick={() => onPage(p)} style={btnStyle(p === page)}>
            {p}
          </button>
        )
      )}
      <button
        type="button"
        disabled={page === totalPages}
        onClick={() => onPage(page + 1)}
        style={{ ...btnStyle(false), opacity: page === totalPages ? 0.35 : 1, cursor: page === totalPages ? "default" : "pointer", fontSize: 16 }}
      >
        →
      </button>
    </div>
  );
}

function useBundleCard(bundle, onAddToCart, onRemoveFromCart, inCart, user) {
  const [adding, setAdding] = useState(false);
  const vehicleName = [bundle.vehicle_year, bundle.vehicle_make, bundle.vehicle_model].filter(Boolean).join(" ");
  const hasDiscount = bundle.discount_pct && Number(bundle.discount_pct) > 0;
  const isAssembly = bundle.bundle_type === "assembly";
  const savings = hasDiscount ? Number(bundle.total_price) - Number(bundle.discounted_price) : 0;
  async function handleAdd(e) {
    e.preventDefault(); e.stopPropagation();
    if (!user) { window.location.href = "/login?next=/search"; return; }
    setAdding(true);
    try {
      if (inCart) {
        await onRemoveFromCart(bundle);
      } else {
        await onAddToCart(bundle.id);
      }
    } finally { setAdding(false); }
  }
  return { adding, vehicleName, hasDiscount, isAssembly, savings, handleAdd };
}

function BundleShelfCard({ bundle, user, destinationState, onAddToCart, onRemoveFromCart, inCart }) {
  const { adding, vehicleName, hasDiscount, isAssembly, savings, handleAdd } = useBundleCard(bundle, onAddToCart, onRemoveFromCart, inCart, user);
  const previewItems = (bundle.items || []).slice(0, 3);

  return (
    <div style={{ width: 272, flexShrink: 0, background: "var(--bg-surface)", border: "1.5px solid var(--border)", borderRadius: 12, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <div style={{ height: 120, background: "var(--bg-elevated)", position: "relative", overflow: "hidden", flexShrink: 0 }}>
        {bundle.primary_photo_url
          ? <img src={bundle.primary_photo_url} alt={bundle.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          : <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 28, color: "var(--text-muted)" }}>📦</div>
        }
        <span style={{ position: "absolute", top: 8, left: 8, fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: isAssembly ? "rgba(139,92,246,0.85)" : "rgba(255,92,26,0.85)", color: "#fff" }}>
          {isAssembly ? "Assembly" : "Kit"}
        </span>
        {hasDiscount && (
          <span style={{ position: "absolute", top: 8, right: 8, fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: "rgba(22,163,74,0.9)", color: "#fff" }}>
            {Number(bundle.discount_pct)}% off
          </span>
        )}
      </div>

      <div style={{ padding: "10px 12px", flex: 1, display: "flex", flexDirection: "column", gap: 5 }}>
        {isAssembly ? (
          <div>
            <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.3, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
              {bundle.name}
            </p>
            <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
              Sold as one unit · {bundle.item_count} part{bundle.item_count !== 1 ? "s" : ""}
            </p>
          </div>
        ) : (
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--text-muted)", marginBottom: 4 }}>
              Included parts
            </p>
            {previewItems.map((bi) => (
              <p key={bi.id} style={{ fontSize: 11, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginBottom: 2 }}>
                {bi.item_detail?.title || bi.item_detail?.category_name || "Part"}
              </p>
            ))}
            {bundle.item_count > 3 && <p style={{ fontSize: 10, color: "var(--text-muted)" }}>+{bundle.item_count - 3} more</p>}
          </div>
        )}

        {vehicleName && <p style={{ fontSize: 10, color: "var(--text-muted)" }}>{vehicleName}</p>}

        <div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: "var(--primary)", fontFamily: "var(--ff-display)" }}>
              {formatMoney(bundle.discounted_price)}
            </span>
            {hasDiscount && <span style={{ fontSize: 11, color: "var(--text-muted)", textDecoration: "line-through" }}>{formatMoney(bundle.total_price)}</span>}
          </div>
          {hasDiscount && savings > 0 && (
            <span style={{ fontSize: 10, fontWeight: 700, color: "#16a34a", background: "rgba(22,163,74,0.10)", borderRadius: 4, padding: "1px 6px", display: "inline-block", marginTop: 2 }}>
              Save {formatMoney(savings)} · {Number(bundle.discount_pct)}% off
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: 6, marginTop: "auto", paddingTop: 4 }}>
          <button type="button" onClick={handleAdd} disabled={adding} style={{ flex: 1, fontSize: 11, fontWeight: 700, padding: "7px 0", borderRadius: 7, background: inCart ? "var(--bg-elevated)" : "var(--primary)", color: inCart ? "var(--text-secondary)" : "#fff", border: inCart ? "1px solid var(--border)" : "none", cursor: "pointer", opacity: adding ? 0.6 : 1, fontFamily: "var(--ff-display)" }}>
            {adding ? "…" : inCart ? "Remove from cart" : isAssembly ? "Add assembly" : "Add kit"}
          </button>
          <Link href={`/bundles/${bundle.id}`} style={{ fontSize: 11, fontWeight: 600, padding: "7px 10px", borderRadius: 7, border: "1px solid var(--border)", color: "var(--text-secondary)", textDecoration: "none", whiteSpace: "nowrap" }}>
            Details
          </Link>
        </div>
      </div>
    </div>
  );
}

function ExpandedBundleCard({ bundle, user, destinationState, onAddToCart, onRemoveFromCart, inCart }) {
  const { adding, vehicleName, hasDiscount, isAssembly, savings, handleAdd } = useBundleCard(bundle, onAddToCart, onRemoveFromCart, inCart, user);

  return (
    <div style={{ background: "var(--bg-surface)", border: "1.5px solid var(--border)", borderRadius: 12, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <div style={{ aspectRatio: "16/9", background: "var(--bg-elevated)", position: "relative", overflow: "hidden" }}>
        {bundle.primary_photo_url
          ? <img src={bundle.primary_photo_url} alt={bundle.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          : <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 40, color: "var(--text-muted)" }}>📦</div>
        }
        <div style={{ position: "absolute", top: 10, left: 10, display: "flex", gap: 4 }}>
          <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, background: isAssembly ? "rgba(139,92,246,0.85)" : "rgba(255,92,26,0.85)", color: "#fff" }}>
            {isAssembly ? "Assembly" : "Kit"}
          </span>
          {hasDiscount && (
            <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, background: "rgba(22,163,74,0.9)", color: "#fff" }}>
              {Number(bundle.discount_pct)}% off
            </span>
          )}
        </div>
      </div>

      <div style={{ padding: "14px 16px", flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
        {isAssembly ? (
          <div>
            <p style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.3 }}>{bundle.name}</p>
            {vehicleName && <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 3 }}>From: {vehicleName}</p>}
            <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>Sold as one unit · {bundle.item_count} parts</p>
          </div>
        ) : (
          <div>
            {vehicleName && <p style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>From: {vehicleName}</p>}
            <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--text-muted)", marginBottom: 6 }}>
              {bundle.item_count} part{bundle.item_count !== 1 ? "s" : ""} included
            </p>
            <div style={{ background: "var(--bg-elevated)", borderRadius: 8, padding: "8px 10px" }}>
              {(bundle.items || []).slice(0, 5).map((bi) => {
                const it = bi.item_detail || {};
                return (
                  <div key={bi.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 3 }}>
                    <p style={{ fontSize: 11, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                      {it.title || it.category_name || "Part"}
                    </p>
                    <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-primary)", flexShrink: 0 }}>
                      {it.price ? formatMoney(it.price) : ""}
                    </span>
                  </div>
                );
              })}
              {bundle.item_count > 5 && <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>+{bundle.item_count - 5} more</p>}
            </div>
          </div>
        )}

        <div style={{ marginTop: "auto" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ fontSize: 18, fontWeight: 700, color: "var(--primary)", fontFamily: "var(--ff-display)" }}>{formatMoney(bundle.discounted_price)}</span>
            {hasDiscount && <span style={{ fontSize: 13, color: "var(--text-muted)", textDecoration: "line-through" }}>{formatMoney(bundle.total_price)}</span>}
          </div>
          {hasDiscount && savings > 0 && (
            <span style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", background: "rgba(22,163,74,0.10)", borderRadius: 4, padding: "2px 7px", display: "inline-block", marginTop: 4 }}>
              Save {formatMoney(savings)} · {Number(bundle.discount_pct)}% off
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" onClick={handleAdd} disabled={adding} style={{ flex: 1, fontSize: 13, fontWeight: 700, padding: "9px 0", borderRadius: 8, background: inCart ? "var(--bg-elevated)" : "var(--primary)", color: inCart ? "var(--text-secondary)" : "#fff", border: inCart ? "1px solid var(--border)" : "none", cursor: "pointer", opacity: adding ? 0.6 : 1, fontFamily: "var(--ff-display)" }}>
            {adding ? "…" : inCart ? "Remove from cart" : isAssembly ? "Add assembly" : "Add kit to cart"}
          </button>
          <Link href={`/bundles/${bundle.id}`} style={{ fontSize: 12, fontWeight: 600, padding: "9px 14px", borderRadius: 8, border: "1px solid var(--border)", color: "var(--text-secondary)", textDecoration: "none", whiteSpace: "nowrap" }}>
            Details
          </Link>
        </div>
      </div>
    </div>
  );
}

function BundleShelf({ bundles, bundlesLoading, user, destinationState, onAddToCart, onRemoveFromCart, isBundleInCart }) {
  const [mode, setModeRaw] = useState("open");
  const [bundlePage, setBundlePage] = useState(1);

  useEffect(() => {
    const saved = localStorage.getItem(SHELF_STATE_KEY);
    if (saved && ["open", "closed", "expanded"].includes(saved)) setModeRaw(saved);
  }, []);

  useEffect(() => { setBundlePage(1); }, [bundles]);

  function setMode(m) {
    setModeRaw(m);
    localStorage.setItem(SHELF_STATE_KEY, m);
  }

  const totalBundlePages = Math.ceil(bundles.length / BUNDLES_PER_PAGE);
  const pagedBundles = bundles.slice((bundlePage - 1) * BUNDLES_PER_PAGE, bundlePage * BUNDLES_PER_PAGE);

  function hBtn(label, onClick) {
    return (
      <button type="button" onClick={onClick} style={{ fontSize: 11, fontWeight: 600, padding: "4px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-elevated)", color: "var(--text-secondary)", cursor: "pointer", whiteSpace: "nowrap" }}>
        {label}
      </button>
    );
  }

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: mode === "closed" ? 0 : 10 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, minWidth: 0 }}>
          <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-muted)", flexShrink: 0 }}>
            Kits & Bundles
          </p>
          {!bundlesLoading && (
            <p style={{ fontSize: 12, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {bundles.length} kit{bundles.length !== 1 ? "s" : ""}{mode === "closed" ? " available" : " — buy together"}
            </p>
          )}
        </div>
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          {mode === "closed" && hBtn("Show ↓", () => setMode("open"))}
          {mode === "open" && <>{hBtn("Expand ⊞", () => setMode("expanded"))}{hBtn("Collapse ↑", () => setMode("closed"))}</>}
          {mode === "expanded" && <>{hBtn("← Shelf", () => setMode("open"))}{hBtn("Close ↑", () => setMode("closed"))}</>}
        </div>
      </div>

      {mode !== "closed" && (
        <>
          {bundlesLoading ? (
            <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading kits…</p>
          ) : mode === "open" ? (
            <div style={{ display: "flex", gap: 12, overflowX: "auto", paddingBottom: 8, scrollbarWidth: "thin" }}>
              {bundles.map((b) => <BundleShelfCard key={b.id} bundle={b} user={user} destinationState={destinationState} onAddToCart={onAddToCart} onRemoveFromCart={onRemoveFromCart} inCart={isBundleInCart(b)} />)}
            </div>
          ) : (
            <>
              <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
                {pagedBundles.map((b) => <ExpandedBundleCard key={b.id} bundle={b} user={user} destinationState={destinationState} onAddToCart={onAddToCart} onRemoveFromCart={onRemoveFromCart} inCart={isBundleInCart(b)} />)}
              </div>
              {totalBundlePages > 1 && <Pagination page={bundlePage} totalPages={totalBundlePages} onPage={setBundlePage} />}
            </>
          )}
          <div style={{ height: 1, background: "var(--border)", marginTop: 16 }} />
        </>
      )}
    </div>
  );
}

function SearchContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const { car, setCar, clearCar } = useBuyerCar();
  const { itemIds, bundleIds, getCartItemId, refresh: refreshCart } = useCart();
  const toast = useToast();

  const [items, setItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [categories, setCategories] = useState([]);
  const [makes, setMakes] = useState([]);
  const [generations, setGenerations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [optionFilters, setOptionFilters] = useState([]);
  const [bundles, setBundles] = useState([]);
  const [bundlesLoading, setBundlesLoading] = useState(false);

  const filters = useMemo(() => {
    const optionParams = {};
    searchParams.forEach((val, key) => {
      if (key.startsWith("option_") && val) optionParams[key] = val;
    });
    return {
      part_number: searchParams.get("part_number") || "",
      category: searchParams.get("category") || "",
      make: searchParams.get("make") || "",
      generation:
        searchParams.get("generation") ||
        (car?.generationId ? String(car.generationId) : ""),
      modification:
        searchParams.get("modification") ||
        (car?.modificationId ? String(car.modificationId) : ""),
      year: searchParams.get("year") || (car?.year ? String(car.year) : ""),
      price_min: searchParams.get("price_min") || "",
      price_max: searchParams.get("price_max") || "",
      destination_state: searchParams.get("destination_state") || "",
      pickup_state: searchParams.get("pickup_state") || "",
      sort: searchParams.get("sort") || "newest",
      compatible_only:
        searchParams.get("compatible_only") ?? (car?.generationId ? "1" : "0"),
      page: parseInt(searchParams.get("page") || "1", 10),
      ...optionParams,
    };
  }, [searchParams, car]);

  const updateParams = useCallback(
    (updates) => {
      const next = new URLSearchParams(searchParams.toString());
      if (!("page" in updates)) next.set("page", "1");
      Object.entries(updates).forEach(([key, val]) => {
        if (val === "" || val == null || val === false) next.delete(key);
        else next.set(key, String(val));
      });
      router.replace(`/search?${next.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  useEffect(() => {
    const catParams = { with_counts: "1" };
    if (filters.generation) catParams.generation = filters.generation;
    if (filters.compatible_only === "1") catParams.compatible_only = "1";
    getCategories(catParams)
      .then((d) => setCategories(Array.isArray(d) ? d : []))
      .catch(() => {});
    getMakes({ with_counts: "1" })
      .then((d) => setMakes(Array.isArray(d) ? d : d?.results || []))
      .catch(() => {});
  }, [filters.generation, filters.compatible_only]);

  useEffect(() => {
    if (!filters.make) {
      setGenerations([]);
      return;
    }
    getModels(filters.make)
      .then((models) => {
        const list = Array.isArray(models) ? models : models?.results || [];
        if (list.length === 0) return;
        Promise.all(list.map((m) => getGenerations(m.id))).then((all) => {
          const flat = all.flatMap((g) =>
            Array.isArray(g) ? g : g?.results || [],
          );
          setGenerations(flat);
        });
      })
      .catch(() => setGenerations([]));
  }, [filters.make]);

  useEffect(() => {
    if (!filters.category) {
      setOptionFilters([]);
      return;
    }
    const p = { category: filters.category };
    if (filters.generation) p.generation = filters.generation;
    if (filters.modification) p.modification = filters.modification;
    getOptionFilters(p)
      .then((d) => setOptionFilters(Array.isArray(d) ? d : []))
      .catch(() => setOptionFilters([]));
  }, [filters.category, filters.generation, filters.modification]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setBundlesLoading(true);

    const params = {};
    if (filters.part_number) params.part_number = filters.part_number;
    if (filters.category) params.category = filters.category;
    if (filters.make) params.make = filters.make;
    if (filters.generation) params.generation = filters.generation;
    if (filters.modification) params.modification = filters.modification;
    if (filters.year) params.year = filters.year;
    if (filters.price_min) params.price_min = filters.price_min;
    if (filters.price_max) params.price_max = filters.price_max;
    if (filters.pickup_state) params.pickup_state = filters.pickup_state;
    if (filters.sort) params.sort = filters.sort;
    if (filters.compatible_only === "1" && filters.generation)
      params.compatible_only = "1";
    params.limit = PAGE_SIZE;
    params.offset = (filters.page - 1) * PAGE_SIZE;
    Object.entries(filters).forEach(([k, v]) => {
      if (k.startsWith("option_") && v) params[k] = v;
    });

    const bundleParams = {};
    if (filters.make) bundleParams.make = filters.make;
    if (filters.generation) bundleParams.generation = filters.generation;
    if (filters.category) bundleParams.category = filters.category;

    (async () => {
      try {
        const data = await getItems(params);
        if (!cancelled) {
          setItems(data.results || []);
          setTotalCount(data.count ?? data.results?.length ?? 0);
        }
      } catch (e) {
        if (!cancelled && e instanceof ApiError) toast.error(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    (async () => {
      try {
        const data = await getBundles(bundleParams);
        if (!cancelled)
          setBundles(Array.isArray(data) ? data : data?.results || []);
      } catch {
        if (!cancelled) setBundles([]);
      } finally {
        if (!cancelled) setBundlesLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [filters, toast]);

  async function handleAddToCart(itemId) {
    await addToCart(itemId);
    await refreshCart();
    toast.success("Added to cart.");
  }

  async function handleRemoveFromCart(itemId) {
    const cartItemId = getCartItemId(itemId);
    if (!cartItemId) return;
    await removeFromCart(cartItemId);
    await refreshCart();
    toast.success("Removed from cart.");
  }

  async function handleAddBundleToCart(bundleId) {
    try {
      await addBundleToCart(bundleId);
      await refreshCart();
      toast.success("Added to cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  }

  async function handleRemoveBundleFromCart(bundle) {
    try {
      if (bundle.bundle_type === "assembly" && bundle.assembly_item_id) {
        const cartItemId = getCartItemId(bundle.assembly_item_id);
        if (cartItemId) await removeFromCart(cartItemId);
      } else {
        await removeCartBundle(bundle.id);
      }
      await refreshCart();
      toast.success("Removed from cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  }

  function isBundleInCart(bundle) {
    if (bundle.bundle_type === "assembly") {
      return bundle.assembly_item_id ? itemIds.has(bundle.assembly_item_id) : false;
    }
    return bundleIds.has(bundle.id);
  }

  function handlePageChange(newPage) {
    updateParams({ page: newPage });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const resultSummary =
    car?.displayLabel && filters.compatible_only === "1"
      ? `${totalCount} part${totalCount !== 1 ? "s" : ""} matching your ${car.displayLabel}`
      : `${totalCount} part${totalCount !== 1 ? "s" : ""} found`;

  const showCarForm = !car?.generationId && !filters.generation;

  const normalizedSearchPN = filters.part_number
    ? normalizePartNumber(filters.part_number)
    : "";

  const requiredSpecs = optionFilters.filter((g) => g.is_required);
  const optionalSpecs = optionFilters.filter((g) => !g.is_required);

  function renderSpecGroup(group) {
    const paramKey = `option_${group.type}`;
    const active = filters[paramKey] || "";
    return (
      <div key={group.type} style={{ marginBottom: 12 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginBottom: 6,
          }}
        >
          <p
            style={{
              fontSize: 10,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--text-muted)",
            }}
          >
            {group.name}
          </p>
          {group.is_required && !active && (
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                color: "var(--primary)",
                background: "var(--primary-muted)",
                padding: "1px 5px",
                borderRadius: 4,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Helps narrow results
            </span>
          )}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {group.values.map((val) => (
            <button
              key={val}
              type="button"
              onClick={() =>
                updateParams({ [paramKey]: active === val ? "" : val })
              }
              style={{
                fontSize: 11,
                fontWeight: 600,
                padding: "3px 10px",
                borderRadius: 6,
                border:
                  active === val
                    ? "1px solid var(--primary)"
                    : "1px solid var(--border)",
                background:
                  active === val
                    ? "var(--primary-muted)"
                    : "var(--bg-elevated)",
                color:
                  active === val ? "var(--primary)" : "var(--text-secondary)",
                cursor: "pointer",
              }}
            >
              {val}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-10">
      <div className="mb-6">
        <p className="section-label mb-1">Marketplace</p>
        <h1 className="heading-display text-2xl">Search parts</h1>
      </div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Sidebar */}
        <aside className="lg:w-64 shrink-0 space-y-6">
          {/* Car filter */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              padding: 16,
            }}
          >
            <p style={labelStyle}>Your car</p>
            {car?.generationId ? (
              <>
                <p
                  style={{
                    fontSize: 13,
                    color: "var(--text-primary)",
                    lineHeight: 1.4,
                  }}
                >
                  Filtering for: <strong>{car.displayLabel}</strong>
                </p>
                <label
                  className="flex items-center gap-2 mt-3"
                  style={{ fontSize: 12, color: "var(--text-secondary)" }}
                >
                  <input
                    type="checkbox"
                    checked={filters.compatible_only === "1"}
                    onChange={(e) =>
                      updateParams({
                        compatible_only: e.target.checked ? "1" : "0",
                      })
                    }
                  />
                  Only compatible parts
                </label>
                <button
                  type="button"
                  onClick={() => {
                    clearCar();
                    updateParams({
                      generation: "",
                      modification: "",
                      year: "",
                      compatible_only: "0",
                    });
                  }}
                  style={{
                    marginTop: 8,
                    fontSize: 12,
                    color: "var(--primary)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  Change car
                </button>
              </>
            ) : showCarForm ? (
              <CarSelector
                compact
                submitLabel="Set my car"
                onSubmit={async (payload) => {
                  await setCar(payload);
                  updateParams({
                    generation: payload.generationId,
                    modification: payload.modificationId || "",
                    year: payload.year,
                    compatible_only: "1",
                  });
                }}
              />
            ) : (
              <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
                Set a car to see fitment badges.
              </p>
            )}
          </div>
          {/* My state */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              padding: 16,
            }}
          >
            <p style={labelStyle}>My state</p>
            <select
              value={filters.destination_state}
              onChange={(e) =>
                updateParams({
                  destination_state: e.target.value,
                  pickup_state: filters.pickup_state ? e.target.value : "",
                })
              }
              style={{
                width: "100%",
                fontSize: 12,
                padding: 8,
                borderRadius: 8,
                border: "1px solid var(--border)",
                background: "var(--bg-elevated)",
                color: "var(--text-primary)",
              }}
            >
              <option value="">Select state</option>
              {US_STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            {filters.destination_state && (
              <label
                className="flex items-center gap-2 mt-3"
                style={{
                  fontSize: 12,
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={!!filters.pickup_state}
                  onChange={(e) =>
                    updateParams({
                      pickup_state: e.target.checked
                        ? filters.destination_state
                        : "",
                    })
                  }
                />
                Local pickup only ({filters.destination_state})
              </label>
            )}
          </div>
          {/* Part number search */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              padding: 16,
            }}
          >
            <PartNumberSearch
              value={filters.part_number}
              onChange={(v) => updateParams({ part_number: v })}
            />
          </div>

          {/* Categories — drill-down */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              padding: 16,
            }}
          >
            <p style={labelStyle}>Category</p>
            <CategoryNav
              categories={categories}
              activeSlug={filters.category}
              onSelect={(slug) => updateParams({ category: slug })}
            />
          </div>

          {/* Make (when no car set) */}
          {!car?.generationId && (
            <div
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                padding: 16,
              }}
            >
              <p style={labelStyle}>Make</p>
              <select
                value={filters.make}
                onChange={(e) =>
                  updateParams({ make: e.target.value, generation: "" })
                }
                style={{
                  width: "100%",
                  fontSize: 12,
                  padding: 8,
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--bg-elevated)",
                  color: "var(--text-primary)",
                }}
              >
                <option value="">All makes</option>
                {makes.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                    {m.listing_count != null ? ` (${m.listing_count})` : ""}
                  </option>
                ))}
              </select>
              {filters.make && generations.length > 0 && (
                <select
                  value={filters.generation}
                  onChange={(e) => updateParams({ generation: e.target.value })}
                  style={{
                    width: "100%",
                    fontSize: 12,
                    padding: 8,
                    borderRadius: 8,
                    border: "1px solid var(--border)",
                    background: "var(--bg-elevated)",
                    color: "var(--text-primary)",
                    marginTop: 8,
                  }}
                >
                  <option value="">All generations</option>
                  {generations.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.display_label || g.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {/* Optional specs only — required specs live at the top of results */}
          {filters.category && optionalSpecs.length > 0 && (
            <div
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                padding: 16,
              }}
            >
              <p style={labelStyle}>Filters</p>
              {optionalSpecs.map(renderSpecGroup)}
            </div>
          )}

          {/* Sort */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              padding: 16,
            }}
          >
            <p style={labelStyle}>Sort by</p>
            <select
              value={filters.sort}
              onChange={(e) => updateParams({ sort: e.target.value })}
              style={{
                width: "100%",
                fontSize: 12,
                padding: 8,
                borderRadius: 8,
                border: "1px solid var(--border)",
                background: "var(--bg-elevated)",
                color: "var(--text-primary)",
              }}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          {/* Price */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              padding: 16,
            }}
          >
            <p style={labelStyle}>Price</p>
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="Min"
                value={filters.price_min}
                onChange={(e) => updateParams({ price_min: e.target.value })}
                style={{
                  flex: 1,
                  fontSize: 12,
                  padding: 8,
                  borderRadius: 8,
                  minWidth: 0,
                  border: "1px solid var(--border)",
                  background: "var(--bg-elevated)",
                  color: "var(--text-primary)",
                }}
              />
              <input
                type="number"
                placeholder="Max"
                value={filters.price_max}
                onChange={(e) => updateParams({ price_max: e.target.value })}
                style={{
                  flex: 1,
                  fontSize: 12,
                  padding: 8,
                  borderRadius: 8,
                  minWidth: 0,
                  border: "1px solid var(--border)",
                  background: "var(--bg-elevated)",
                  color: "var(--text-primary)",
                }}
              />
            </div>
          </div>
        </aside>

        {/* Results */}
        <div className="flex-1 min-w-0">

          {/* Required specs bar — shown at top when category selected */}
          {filters.category && requiredSpecs.length > 0 && (
            <div
              style={{
                marginBottom: 16,
                background: "var(--bg-surface)",
                border: "1px solid var(--primary-border-soft, var(--border))",
                borderRadius: 10,
                padding: "12px 14px",
              }}
            >
              {requiredSpecs.map((group) => {
                const paramKey = `option_${group.type}`;
                const active = filters[paramKey] || "";
                return (
                  <div key={group.type} style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: "var(--primary)", whiteSpace: "nowrap" }}>
                      {group.name}:
                    </span>
                    {active ? (
                      <button
                        type="button"
                        onClick={() => updateParams({ [paramKey]: "" })}
                        style={{
                          fontSize: 11, fontWeight: 700, padding: "3px 10px",
                          borderRadius: 20, border: "1px solid var(--primary)",
                          background: "var(--primary)", color: "#fff",
                          cursor: "pointer", display: "flex", alignItems: "center", gap: 5,
                        }}
                      >
                        {active}
                        <span style={{ fontSize: 13, lineHeight: 1 }}>×</span>
                      </button>
                    ) : (
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        {group.values.map((val) => (
                          <button
                            key={val}
                            type="button"
                            onClick={() => updateParams({ [paramKey]: val })}
                            style={{
                              fontSize: 11, fontWeight: 600, padding: "3px 12px",
                              borderRadius: 20, border: "1px solid var(--primary)",
                              background: "transparent", color: "var(--primary)",
                              cursor: "pointer",
                            }}
                          >
                            {val}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}


          {filters.part_number && (
            <div
              style={{
                fontSize: 12,
                color: "var(--text-secondary)",
                marginBottom: 12,
                padding: "6px 10px",
                background: "var(--bg-elevated)",
                borderRadius: 6,
                display: "inline-block",
              }}
            >
              Searching by part number: <strong>{filters.part_number}</strong>
            </div>
          )}

          {/* Kits & Bundles shelf */}
          {(bundlesLoading || bundles.length > 0) && (
            <BundleShelf
              bundles={bundles}
              bundlesLoading={bundlesLoading}
              user={user}
              destinationState={filters.destination_state}
              onAddToCart={handleAddBundleToCart}
              onRemoveFromCart={handleRemoveBundleFromCart}
              isBundleInCart={isBundleInCart}
            />
          )}

          <p
            style={{
              fontSize: 13,
              color: "var(--text-muted)",
              marginBottom: 16,
            }}
          >
            {loading ? "Loading…" : resultSummary}
          </p>

          {loading ? (
            <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
              Loading parts…
            </p>
          ) : items.length === 0 ? (
            <div style={{ textAlign: "center", padding: "48px 0" }}>
              <p style={{ fontSize: 32, marginBottom: 8 }}>🔍</p>
              <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
                No parts found. Try adjusting filters.
              </p>
            </div>
          ) : (
            <div
              className="grid gap-4"
              style={{
                gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              }}
            >
              {items.map((item) => (
                <SearchItemCard
                  key={item.id}
                  item={item}
                  user={user}
                  destinationState={filters.destination_state}
                  carGenerationLabel={car?.generationName}
                  partNumberQuery={normalizedSearchPN}
                  onAddToCart={handleAddToCart}
                  onRemoveFromCart={handleRemoveFromCart}
                  inCart={itemIds.has(item.id)}
                />
              ))}
            </div>
          )}

          {!loading && totalCount > PAGE_SIZE && (
            <Pagination
              page={filters.page}
              totalPages={Math.ceil(totalCount / PAGE_SIZE)}
              onPage={handlePageChange}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="p-10 text-sm" style={{ color: "var(--text-muted)" }}>
          Loading…
        </div>
      }
    >
      <SearchContent />
    </Suspense>
  );
}
