"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

import { PartListingCard } from "@/components/PartListingCard";
import { useAuth } from "@/context/auth-context";
import { isApprovedSeller } from "@/lib/roles";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

const PHOTO_KINDS = [
  { value: "exterior",   label: "Exterior" },
  { value: "engine_bay", label: "Engine bay" },
  { value: "interior",   label: "Interior" },
  { value: "odometer",   label: "Odometer" },
];

const DAMAGE_OPTIONS = [
  "Front-end collision","Rear-end collision","Driver-side collision","Passenger-side collision",
  "Rollover","Flood / water damage","Fire damage","Hail damage","Frame damage","Airbags deployed",
  "Theft damage","Vandalism","Mechanical failure","Undercarriage damage","Roof damage","Windshield damage",
];

const inputStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "8px 12px",
  fontSize: 13,
  outline: "none",
  fontFamily: "var(--ff-body)",
  width: "100%",
};

const selectStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "8px 12px",
  fontSize: 13,
  outline: "none",
  fontFamily: "var(--ff-body)",
  width: "100%",
};

const sectionStyle = {
  background: "var(--bg-surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-xl)",
  padding: "20px",
  marginTop: 24,
};

const sectionHeader = {
  fontSize: 15,
  fontWeight: 700,
  color: "var(--text-primary)",
  fontFamily: "var(--ff-display)",
  marginBottom: 4,
};

const sectionSub = {
  fontSize: 12,
  color: "var(--text-muted)",
};

function SectionLabel({ children }) {
  return (
    <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 12 }}>
      {children}
    </p>
  );
}

/** Compact page indices + ellipsis (0-based current page). */
function vehiclePartsPaginationEntries(totalPages, currentPage0) {
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

export default function VehicleDashboardPage() {
  const { id } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();

  const [vehicle, setVehicle] = useState(null);
  const [categories, setCategories] = useState([]);
  const [parts, setParts] = useState([]);
  const [partsCount, setPartsCount] = useState(0);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [listingTab, setListingTab] = useState("buy_now");
  const [partSearchInput, setPartSearchInput] = useState("");
  const [partSearch, setPartSearch] = useState("");
  const [ordering, setOrdering] = useState("updated");
  const [page, setPage] = useState(1);
  const pageSize = 30;
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [priceTemplateText, setPriceTemplateText] = useState("");
  const [templateBusy, setTemplateBusy] = useState(false);
  const [customPartName, setCustomPartName] = useState("");
  const [customPartCategoryId, setCustomPartCategoryId] = useState("");
  const [customPartBusy, setCustomPartBusy] = useState(false);
  const [vehicleConditionDesc, setVehicleConditionDesc] = useState("");
  const [vehicleCondBusy, setVehicleCondBusy] = useState(false);
  const [pickupAllowed, setPickupAllowed] = useState(false);
  const [pickupAddress, setPickupAddress] = useState("");
  const [locationState, setLocationState] = useState("");
  const [locationZip, setLocationZip] = useState("");
  const [vehicleReturnPolicy, setVehicleReturnPolicy] = useState("green");
  const [vehicleSettingsBusy, setVehicleSettingsBusy] = useState(false);
  const [selectedPartIds, setSelectedPartIds] = useState([]);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [vehicleEditMode, setVehicleEditMode] = useState(false);
  const [hasDamage, setHasDamage] = useState(false);
  const [damageItems, setDamageItems] = useState([]);
  const [customDamageInput, setCustomDamageInput] = useState("");
  const [damageSaving, setDamageSaving] = useState(false);
  const damageSynced = useRef(false);

  const partsTotalPages = Math.max(1, Math.ceil((partsCount || 0) / pageSize));
  useEffect(() => {
    setPage((p) => Math.min(Math.max(1, p), partsTotalPages));
  }, [partsCount, pageSize, partsTotalPages]);

  function resetVehicleFormFromServer() {
    if (!vehicle) return;
    setVehicleConditionDesc(vehicle.condition_description || "");
    setPickupAllowed(!!vehicle.pickup_allowed);
    setPickupAddress(vehicle.pickup_address || "");
    setLocationState((vehicle.location_state || "").trim().toUpperCase());
    setLocationZip((vehicle.location_zip || "").trim());
    setVehicleReturnPolicy(vehicle.return_policy_default || "green");
    setHasDamage(vehicle.has_damage || false);
    setDamageItems(Array.isArray(vehicle.damage_items) ? vehicle.damage_items : []);
    setCustomDamageInput("");
  }

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!authLoading && user && !isApprovedSeller(user)) router.replace("/seller/apply");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user || !id) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [cats, v] = await Promise.all([apiFetch("/catalog/part-categories/"), apiFetch(`/vehicles/${id}/`)]);
        if (!cancelled) {
          setCategories(Array.isArray(cats) ? cats : []);
          setVehicle(v);
          setVehicleConditionDesc(v?.condition_description || "");
          setPickupAllowed(!!v?.pickup_allowed);
          setPickupAddress(v?.pickup_address || "");
          setLocationState((v?.location_state || "").trim().toUpperCase());
          setLocationZip((v?.location_zip || "").trim());
          setVehicleReturnPolicy(v?.return_policy_default || "green");
        }
      } catch (e) {
        if (!cancelled && e instanceof ApiError) toast.error(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, id, toast]);

  useEffect(() => {
    if (vehicle && !damageSynced.current) {
      setHasDamage(vehicle.has_damage || false);
      setDamageItems(vehicle.damage_items || []);
      damageSynced.current = true;
    }
  }, [vehicle]);

  const partSearchPrevRef = useRef(partSearchInput);
  useEffect(() => {
    const t = setTimeout(() => {
      setPartSearch(partSearchInput);
      if (partSearchPrevRef.current !== partSearchInput) {
        partSearchPrevRef.current = partSearchInput;
        setPage(1);
      }
    }, 400);
    return () => clearTimeout(t);
  }, [partSearchInput]);

  useEffect(() => {
    if (!user || !id) return;
    let cancelled = false;
    (async () => {
      try {
        const qs = new URLSearchParams({ page_size: String(pageSize), page: String(page), hide_removed: "1" });
        if (categoryFilter) qs.set("category", categoryFilter);
        if (listingTab) qs.set("listing_state", listingTab);
        if (partSearch.trim()) qs.set("q", partSearch.trim());
        if (ordering) qs.set("ordering", ordering);
        const data = await apiFetch(`/vehicles/${id}/parts/?${qs.toString()}`);
        const rows = data.results ?? data;
        if (!cancelled) {
          setParts(Array.isArray(rows) ? rows : []);
          setPartsCount(data.count ?? (Array.isArray(rows) ? rows.length : 0));
        }
      } catch (e) {
        if (!cancelled && e instanceof ApiError) toast.error(e.message);
      }
    })();
    return () => { cancelled = true; };
  }, [user, id, categoryFilter, listingTab, partSearch, ordering, page, toast]);

  const analyticsStatus = vehicle?.analytics_status;
  useEffect(() => {
    if (!user || !id || analyticsStatus !== "processing") return;
    const interval = setInterval(async () => {
      try { const v = await apiFetch(`/vehicles/${id}/`); setVehicle(v); } catch { /* ignore */ }
    }, 4000);
    return () => clearInterval(interval);
  }, [user, id, analyticsStatus]);

  async function reloadParts() {
    const qs = new URLSearchParams({ page_size: String(pageSize), page: String(page), hide_removed: "1" });
    if (categoryFilter) qs.set("category", categoryFilter);
    if (listingTab) qs.set("listing_state", listingTab);
    if (partSearch.trim()) qs.set("q", partSearch.trim());
    if (ordering) qs.set("ordering", ordering);
    const data = await apiFetch(`/vehicles/${id}/parts/?${qs.toString()}`);
    const rows = data.results ?? data;
    setParts(Array.isArray(rows) ? rows : []);
    setPartsCount(data.count ?? (Array.isArray(rows) ? rows.length : 0));
  }

  function toggleSelectedPart(partId) {
    setSelectedPartIds((prev) => prev.includes(partId) ? prev.filter((x) => x !== partId) : [...prev, partId]);
  }

  async function bulkDeleteSelected() {
    if (selectedPartIds.length === 0) return;
    const ok = window.confirm(`Delete ${selectedPartIds.length} selected parts?`);
    if (!ok) return;
    setBulkBusy(true);
    try {
      await apiFetch(`/vehicles/${id}/parts/bulk_delete/`, { method: "POST", body: JSON.stringify({ part_ids: selectedPartIds }) });
      toast.success(`Deleted ${selectedPartIds.length} parts.`);
      setSelectedPartIds([]);
      await reloadParts();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const needsForce = Array.isArray(e.body?.needs_force) ? e.body.needs_force : [];
        const blocked = Array.isArray(e.body?.blocked) ? e.body.blocked : [];
        if (blocked.length) { toast.error(`Some parts have orders and cannot be deleted (${blocked.length}).`); return; }
        if (needsForce.length) {
          const ok2 = window.confirm(`Some selected parts have offers/messages attached (${needsForce.length}).\n\nForce delete anyway?`);
          if (!ok2) return;
          await apiFetch(`/vehicles/${id}/parts/bulk_delete/`, { method: "POST", body: JSON.stringify({ part_ids: selectedPartIds, force: 1 }) });
          toast.success(`Deleted ${selectedPartIds.length} parts (forced).`);
          setSelectedPartIds([]);
          await reloadParts();
          return;
        }
      }
      if (e instanceof ApiError) toast.error(e.message);
    } finally { setBulkBusy(false); }
  }

  async function patchPart(partId, body) {
    try { await apiFetch(`/vehicles/${id}/parts/${partId}/`, { method: "PATCH", body: JSON.stringify(body) }); }
    catch (e) { if (e instanceof ApiError) { toast.error(e.message); return; } }
    await reloadParts();
  }

  async function deletePart(partId) {
    setBusy(true);
    try {
      await apiFetch(`/vehicles/${id}/parts/${partId}/`, { method: "DELETE" });
      toast.success("Part deleted.");
      await reloadParts();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const counts = e.body?.counts;
        if (counts?.orders) { toast.error(e.message); return; }
        const ok = window.confirm(`This part has activity attached. Delete anyway?`);
        if (!ok) return;
        await apiFetch(`/vehicles/${id}/parts/${partId}/?force=1`, { method: "DELETE" });
        toast.success("Part deleted (forced)."); await reloadParts(); return;
      }
      if (e instanceof ApiError) toast.error(e.message);
    } finally { setBusy(false); }
  }

  async function addCustomPart() {
    const name = customPartName.trim(); const catId = customPartCategoryId;
    if (!name || !catId) return;
    setCustomPartBusy(true);
    try {
      const r = await apiFetch(`/vehicles/${id}/custom_parts/`, { method: "POST", body: JSON.stringify({ category: Number(catId), name, variant_templates: [] }) });
      toast.success(`Custom part added (${r.parts_created} line${r.parts_created === 1 ? "" : "s"} created).`);
      setCustomPartName(""); await reloadParts();
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setCustomPartBusy(false); }
  }

  async function refreshMarket() {
    setBusy(true);
    try {
      await apiFetch(`/vehicles/${id}/refresh_market_analysis/`, { method: "POST", body: "{}" });
      const v = await apiFetch(`/vehicles/${id}/`); setVehicle(v);
      toast.success("Market analytics queued. This page will update when processing completes.");
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setBusy(false); }
  }

  async function saveVehicleCondition() {
    setVehicleCondBusy(true);
    try {
      await apiFetch(`/vehicles/${id}/`, { method: "PATCH", body: JSON.stringify({ condition_description: vehicleConditionDesc }) });
      toast.success("Vehicle condition saved.");
      const v = await apiFetch(`/vehicles/${id}/`); setVehicle(v);
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setVehicleCondBusy(false); }
  }

  async function saveVehicleSettings() {
    const st = locationState.trim().toUpperCase();
    const zip = locationZip.trim();
    if (!st || !zip) {
      toast.warning("State and ZIP are required for shipping quotes.");
      return;
    }
    if (st.length !== 2) {
      toast.warning("State must be a 2-letter code (e.g. WA).");
      return;
    }
    setVehicleSettingsBusy(true);
    try {
      await apiFetch(`/vehicles/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          location_state: st,
          location_zip: zip,
          pickup_allowed: pickupAllowed,
          pickup_address: pickupAddress,
          return_policy_default: vehicleReturnPolicy,
        }),
      });
      toast.success("Vehicle settings saved.");
      const v = await apiFetch(`/vehicles/${id}/`);
      setVehicle(v);
      setLocationState((v?.location_state || "").trim().toUpperCase());
      setLocationZip((v?.location_zip || "").trim());
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setVehicleSettingsBusy(false); }
  }

  async function applyReturnPolicyToParts(scope) {
    const ids = scope === "selected" ? selectedPartIds : parts.map((p) => p.id);
    if (ids.length === 0) return;
    const ok = window.confirm(`Apply return policy to ${ids.length} part(s)?`);
    if (!ok) return;
    setBulkBusy(true);
    try {
      const r = await apiFetch(`/vehicles/${id}/parts/bulk_update/`, { method: "POST", body: JSON.stringify({ part_ids: ids, return_policy: vehicleReturnPolicy }) });
      toast.success(`Updated return policy for ${r.updated} part(s).`);
      await reloadParts();
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setBulkBusy(false); }
  }

  async function applyPriceTemplate() {
    const text = priceTemplateText.trim();
    if (!text) return;
    setTemplateBusy(true);
    try {
      const r = await apiFetch(`/vehicles/${id}/apply_price_template/`, { method: "POST", body: JSON.stringify({ template_text: text }) });
      const nf = r.part_families_created != null ? `, ${r.part_families_created} new part types` : "";
      toast.success(`Template applied: ${r.created} created, ${r.updated} updated, ${r.skipped} skipped${nf}.`);
      await reloadParts();
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setTemplateBusy(false); }
  }

  async function uploadPhoto(kind, file) {
    if (!file) return;
    setPhotoBusy(true);
    try {
      const fd = new FormData(); fd.append("kind", kind); fd.append("image", file);
      await apiFetch(`/vehicles/${id}/upload_photo/`, { method: "POST", body: fd });
      const v = await apiFetch(`/vehicles/${id}/`); setVehicle(v);
      toast.success("Vehicle photo uploaded.");
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setPhotoBusy(false); }
  }

  async function uploadPartPhoto(partId, file) {
    if (!file) return;
    setPhotoBusy(true);
    try {
      const fd = new FormData(); fd.append("image", file);
      await apiFetch(`/vehicles/${id}/parts/${partId}/upload_photo/`, { method: "POST", body: fd });
      await reloadParts(); toast.success("Part photo uploaded.");
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setPhotoBusy(false); }
  }

  async function deletePhoto(photoId) {
    setPhotoBusy(true);
    try {
      await apiFetch(`/vehicles/${id}/photos/${photoId}/`, { method: "DELETE" });
      const v = await apiFetch(`/vehicles/${id}/`); setVehicle(v);
      toast.success("Photo removed.");
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setPhotoBusy(false); }
  }

  async function saveDamage() {
    setDamageSaving(true);
    try {
      await apiFetch(`/vehicles/${id}/`, { method: "PATCH", body: JSON.stringify({ has_damage: hasDamage, damage_items: hasDamage ? damageItems : [] }) });
      const v = await apiFetch(`/vehicles/${id}/`); setVehicle(v); toast.success("Damage info saved.");
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setDamageSaving(false); }
  }

  function toggleDamageItem(item) {
    setDamageItems((prev) => prev.includes(item) ? prev.filter((x) => x !== item) : [...prev, item]);
  }
  function addCustomDamage() {
    const val = customDamageInput.trim(); if (!val) return;
    if (!damageItems.includes(val)) setDamageItems((prev) => [...prev, val]);
    setCustomDamageInput("");
  }

  const photosByKind = (kind) => (vehicle?.photos || []).filter((p) => p.kind === kind);

  if (authLoading || !user) return <div className="mx-auto max-w-7xl px-6 py-16"><p style={{ color: "var(--text-muted)", fontSize: 14 }}>Loading…</p></div>;
  if (loading && !vehicle) return <div className="mx-auto max-w-7xl px-6 py-16"><p style={{ color: "var(--text-muted)", fontSize: 14 }}>Loading vehicle…</p></div>;
  if (!vehicle) return (
    <div className="mx-auto max-w-7xl px-6 py-16">
      <p style={{ color: "var(--danger)", fontSize: 14 }}>Vehicle not found.</p>
      <Link href="/vehicles" style={{ color: "var(--primary)", fontSize: 14, marginTop: 16, display: "inline-block" }}>← Back to vehicles</Link>
    </div>
  );

  const headline = [vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(" ") || "Vehicle";

  const btnSecondary = {
    borderRadius: "var(--radius-md)", padding: "8px 16px",
    fontSize: 13, fontWeight: 600, fontFamily: "var(--ff-display)",
    background: "var(--bg-elevated)", border: "1px solid var(--border)",
    color: "var(--text-secondary)", cursor: "pointer", transition: "all 0.12s",
  };

  const partsPagerEntries = partsTotalPages > 1 ? vehiclePartsPaginationEntries(partsTotalPages, page - 1) : [];
  const partsRangeLabel =
    partsCount === 0 ? "0 parts" : `Showing ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, partsCount)} of ${partsCount}`;
  const partsPaginationInner = partsTotalPages > 1 ? (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-center sm:gap-3">
      <span style={{ fontSize: 11, color: "var(--text-muted)", textAlign: "center", fontFamily: "var(--ff-body)" }}>{partsRangeLabel}</span>
      <div className="flex flex-wrap items-center justify-center gap-1">
        <button
          type="button"
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1}
          className="rounded-[8px] px-3 py-1.5 text-sm font-medium transition-all disabled:opacity-40"
          style={{ border: "1px solid var(--border)", color: "var(--text-secondary)", fontFamily: "var(--ff-body)" }}
          onMouseEnter={(e) => !e.currentTarget.disabled && (e.currentTarget.style.borderColor = "var(--border-strong)")}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
        >
          ← Prev
        </button>
        {partsPagerEntries.map((entry, idx) =>
          entry === "ellipsis" ? (
            <span
              key={`e-${idx}`}
              className="px-1.5 py-1.5 text-sm font-medium"
              style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)", letterSpacing: "0.06em" }}
              aria-hidden
            >
              …
            </span>
          ) : (
            <button
              key={entry}
              type="button"
              onClick={() => setPage(entry + 1)}
              className="rounded-[8px] min-w-[2.25rem] px-2.5 py-1.5 text-sm font-medium transition-all"
              style={{
                background: entry === page - 1 ? "var(--primary-muted)" : "transparent",
                border: `1px solid ${entry === page - 1 ? "rgba(255,92,26,0.3)" : "var(--border)"}`,
                color: entry === page - 1 ? "var(--primary)" : "var(--text-muted)",
              }}
            >
              {entry + 1}
            </button>
          )
        )}
        <button
          type="button"
          onClick={() => setPage((p) => Math.min(partsTotalPages, p + 1))}
          disabled={page >= partsTotalPages}
          className="rounded-[8px] px-3 py-1.5 text-sm font-medium transition-all disabled:opacity-40"
          style={{ border: "1px solid var(--border)", color: "var(--text-secondary)", fontFamily: "var(--ff-body)" }}
          onMouseEnter={(e) => !e.currentTarget.disabled && (e.currentTarget.style.borderColor = "var(--border-strong)")}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
        >
          Next →
        </button>
      </div>
    </div>
  ) : null;

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-10">

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-2">
        <div>
          <p className="section-label mb-1">Vehicle dashboard</p>
          <h1 className="heading-display text-2xl">{headline}</h1>
          <div className="flex flex-wrap items-center gap-3 mt-1">
            <p style={{ fontFamily: "var(--ff-mono)", fontSize: 12, color: "var(--text-muted)" }}>{vehicle.vin}</p>
            {vehicle.location_state && vehicle.location_zip && (
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{vehicle.location_state} {vehicle.location_zip}</span>
            )}
            <span style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "2px 8px", fontSize: 11, fontFamily: "var(--ff-display)", fontWeight: 600, color: "var(--text-secondary)" }}>
              analytics: {vehicle.analytics_status}
            </span>
          </div>
        </div>
        <Link href="/vehicles" style={{ color: "var(--primary)", fontSize: 13, fontWeight: 500, textDecoration: "none" }}
          onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
          onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}>
          ← All vehicles
        </Link>
      </div>

      {/* Status banners */}
      {vehicle.analytics_status === "processing" && (
        <div className="mt-4 rounded-[12px] px-4 py-3 text-sm"
          style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.25)", color: "#fbbf24" }}>
          Market data is processing… refreshing every few seconds.
        </div>
      )}
      {vehicle.analytics_status === "ready" && (
        <div className="mt-4 rounded-[12px] px-4 py-3 text-sm"
          style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.25)", color: "#4ade80" }}>
          Vehicle market analytics are ready — see the snapshot below.
        </div>
      )}
      {vehicle.analytics_status === "failed" && (
        <div className="mt-4 rounded-[12px] px-4 py-3 text-sm"
          style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", color: "var(--danger)" }}>
          Processing failed. Try &quot;Refresh market data&quot; below.
        </div>
      )}
      {/* Edit mode toggle */}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-[14px] px-4 py-3"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
        <p style={{ fontSize: 13, color: "var(--text-muted)", maxWidth: 500 }}>
          {vehicleEditMode
            ? "Editing vehicle details. Save each section, or Cancel to discard unsaved changes."
            : "View mode — Edit vehicle details to modify photos, condition, ship-from location, pickup, damage, and bulk tools."}
        </p>
        <div className="flex flex-wrap gap-2">
          {!vehicleEditMode ? (
            <button type="button" onClick={() => setVehicleEditMode(true)} className="btn-forge" style={{ padding: "8px 18px", fontSize: 13 }}>
              Edit vehicle details
            </button>
          ) : (
            <>
              <button type="button" onClick={() => { resetVehicleFormFromServer(); setVehicleEditMode(false); }} style={btnSecondary}>
                Cancel
              </button>
              <button type="button" onClick={() => setVehicleEditMode(false)} className="btn-forge" style={{ padding: "8px 18px", fontSize: 13 }}>
                Done
              </button>
            </>
          )}
        </div>
      </div>

      {/* Market snapshot */}
      <div style={sectionStyle}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p style={sectionHeader}>eBay market snapshot</p>
            <p style={sectionSub}>Scraped active + sold listings; estimates are indicative only.</p>
          </div>
          <button
            type="button"
            disabled={busy || vehicle.analytics_status === "processing" || !vehicle.can_refresh_market_analytics}
            onClick={() => void refreshMarket()}
            style={{ ...btnSecondary, opacity: (busy || vehicle.analytics_status === "processing" || !vehicle.can_refresh_market_analytics) ? 0.5 : 1 }}
          >
            Refresh market data
          </button>
        </div>
        {vehicle.analytics_next_refresh_at && !vehicle.can_refresh_market_analytics && (
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            Next refresh: {new Date(vehicle.analytics_next_refresh_at).toLocaleString()}
          </p>
        )}
        {vehicle.market_analysis_summary ? (
          <dl className="mt-4 grid gap-3 sm:grid-cols-4">
            {[
              ["Est. part-out (net)", vehicle.market_analysis_summary.estimated_total_net != null
                ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(vehicle.market_analysis_summary.estimated_total_net)) : "—"],
              ["Kept listings",  vehicle.market_analysis_summary.counts?.kept?.total ?? "—"],
              ["Median price",   vehicle.market_analysis_summary.stats_combined?.median_price != null
                ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(vehicle.market_analysis_summary.stats_combined.median_price) : "—"],
              ["Scraped at",     vehicle.market_analysis_summary.scraped_at
                ? new Date(vehicle.market_analysis_summary.scraped_at).toLocaleDateString() : "—"],
            ].map(([dt, dd]) => (
              <div key={dt} style={{ background: "var(--bg-elevated)", borderRadius: "var(--radius-md)", padding: "12px 14px" }}>
                <dt style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 4 }}>{dt}</dt>
                <dd className="price-mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--primary-bright)" }}>{dd}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p style={{ marginTop: 16, fontSize: 13, color: "var(--text-muted)" }}>
            {vehicle.analytics_status === "processing" ? "Summary will appear when processing completes." : "No market snapshot yet."}
          </p>
        )}
      </div>

      {/* Photos */}
      <div style={sectionStyle}>
        <div className="flex items-center justify-between">
          <div>
            <p style={sectionHeader}>Vehicle photos</p>
            <p style={sectionSub}>
              {vehicleEditMode ? "Upload multiple photos per category." : "Gallery view — Edit vehicle details to add or remove photos."}
            </p>
          </div>
          {photoBusy && <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Uploading…</span>}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {PHOTO_KINDS.map((k) => {
            const photos = photosByKind(k.value);
            return (
              <div key={k.value} style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "14px" }}>
                <div className="flex items-center justify-between mb-3">
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{k.label}</span>
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{photos.length} photo{photos.length !== 1 ? "s" : ""}</span>
                </div>
                {photos.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {photos.map((ph) => (
                      <div key={ph.id} className="group relative">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={ph.image} alt="" style={{ width: 80, height: 64, objectFit: "cover", borderRadius: "var(--radius-md)", border: "1px solid var(--border)" }} />
                        {vehicleEditMode && (
                          <button
                            type="button"
                            disabled={photoBusy}
                            onClick={() => void deletePhoto(ph.id)}
                            aria-label="Delete photo"
                            style={{ position: "absolute", top: -6, right: -6, width: 18, height: 18, borderRadius: "50%", background: "var(--danger)", color: "#fff", border: "none", fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", opacity: 0 }}
                            className="group-hover:opacity-100"
                          >×</button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {vehicleEditMode && (
                  <label style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 12, fontWeight: 500, color: "var(--text-muted)", border: "1px dashed var(--border)", borderRadius: "var(--radius-md)", padding: "6px 12px", transition: "all 0.12s" }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(255,92,26,0.4)"; e.currentTarget.style.color = "var(--primary)"; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-muted)"; }}>
                    + Add photo
                    <input type="file" accept="image/*" disabled={photoBusy} className="sr-only"
                      onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; void uploadPhoto(k.value, f); }} />
                  </label>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Condition notes */}
      <div style={sectionStyle}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p style={sectionHeader}>Vehicle condition notes</p>
            <p style={sectionSub}>Free-form notes buyers will see (engine, mileage, issues, etc.).</p>
          </div>
          {vehicleEditMode && (
            <button type="button" disabled={vehicleCondBusy} onClick={() => void saveVehicleCondition()}
              className="btn-forge" style={{ padding: "8px 18px", fontSize: 13, opacity: vehicleCondBusy ? 0.5 : 1 }}>
              {vehicleCondBusy ? "Saving…" : "Save notes"}
            </button>
          )}
        </div>
        {vehicleEditMode ? (
          <textarea
            value={vehicleConditionDesc}
            onChange={(e) => setVehicleConditionDesc(e.target.value)}
            rows={4}
            placeholder="Example: Runs but has a misfire on cylinder 2. 162k miles. Transmission shifts smooth."
            style={{ ...inputStyle, marginTop: 12, resize: "vertical", lineHeight: 1.5 }}
          />
        ) : (
          <div style={{ marginTop: 12, background: "var(--bg-elevated)", borderRadius: "var(--radius-md)", padding: "12px 14px" }}>
            {(vehicle.condition_description || "").trim()
              ? <p style={{ fontSize: 13, color: "var(--text-secondary)", whiteSpace: "pre-wrap" }}>{vehicle.condition_description}</p>
              : <p style={{ fontSize: 13, color: "var(--text-muted)" }}>No condition notes yet.</p>}
          </div>
        )}
      </div>

      {/* Pickup & defaults */}
      <div style={sectionStyle}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p style={sectionHeader}>Shipping origin, pickup &amp; defaults</p>
            <p style={sectionSub}>State and ZIP are used for shipping quotes. Pickup address is shown only when pickup is enabled.</p>
          </div>
          {vehicleEditMode && (
            <button type="button" disabled={vehicleSettingsBusy} onClick={() => void saveVehicleSettings()}
              className="btn-forge" style={{ padding: "8px 18px", fontSize: 13, opacity: vehicleSettingsBusy ? 0.5 : 1 }}>
              {vehicleSettingsBusy ? "Saving…" : "Save location & defaults"}
            </button>
          )}
        </div>

        {!vehicleEditMode ? (
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Ship-from (quotes)", [vehicle.location_state, vehicle.location_zip].filter(Boolean).join(" ").trim() || "—"],
              ["Pickup",          vehicle.pickup_allowed ? "Yes — offered" : "No"],
              ["Pickup address",         (vehicle.pickup_address || "").trim() || "—"],
              ["Return policy",   (vehicle.return_policy_default === "green" ? "Green — 30-day" : vehicle.return_policy_default === "yellow" ? "Yellow — restocking fee" : "Red — final sale")],
            ].map(([dt, dd]) => (
              <div key={dt} style={{ background: "var(--bg-elevated)", borderRadius: "var(--radius-md)", padding: "12px 14px" }}>
                <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 4 }}>{dt}</p>
                <p style={{ fontSize: 13, color: "var(--text-primary)" }}>{dd}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-3 space-y-4">
            <div>
              <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 8 }}>
                Part shipping origin
              </p>
              <div className="flex flex-wrap gap-3">
                <div style={{ flex: "1 1 100px", minWidth: 80 }}>
                  <label style={{ display: "block", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 4 }} htmlFor="veh-loc-state">State *</label>
                  <input
                    id="veh-loc-state"
                    type="text"
                    maxLength={2}
                    value={locationState}
                    onChange={(e) => setLocationState(e.target.value.toUpperCase().replace(/[^A-Za-z]/g, "").slice(0, 2))}
                    placeholder="WA"
                    style={inputStyle}
                  />
                </div>
                <div style={{ flex: "2 1 140px", minWidth: 120 }}>
                  <label style={{ display: "block", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 4 }} htmlFor="veh-loc-zip">ZIP *</label>
                  <input
                    id="veh-loc-zip"
                    type="text"
                    inputMode="numeric"
                    value={locationZip}
                    onChange={(e) => setLocationZip(e.target.value.replace(/[^\d\-]/g, "").slice(0, 10))}
                    placeholder="98101"
                    style={inputStyle}
                  />
                </div>
              </div>
              <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>Used for buyer shipping quotes on your listings (same as when you added the vehicle).</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Offer local pickup?</span>
              <div style={{ display: "inline-flex", borderRadius: "var(--radius-md)", overflow: "hidden", border: "1px solid var(--border)" }}>
                {[["Yes", true], ["No", false]].map(([lbl, val]) => (
                  <button key={lbl} type="button" onClick={() => setPickupAllowed(val)}
                    style={{
                      padding: "7px 20px", fontSize: 13, fontWeight: 600, fontFamily: "var(--ff-display)", cursor: "pointer", transition: "all 0.12s",
                      background: pickupAllowed === val ? "var(--primary)" : "var(--bg-elevated)",
                      color: pickupAllowed === val ? "#fff" : "var(--text-secondary)",
                      border: "none",
                    }}>
                    {lbl}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label style={{ display: "block", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 4 }}>
                Pickup address
              </label>
              <input type="text" value={pickupAddress} onChange={(e) => setPickupAddress(e.target.value)}
                placeholder="Street, city, state, ZIP" disabled={!pickupAllowed}
                style={{ ...inputStyle, opacity: pickupAllowed ? 1 : 0.4 }} />
            </div>
            <div>
              <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 8 }}>
                Default return policy
              </p>
              <div className="grid gap-2 sm:grid-cols-3">
                {[{ v: "green", t: "Green", d: "30-day protection" }, { v: "yellow", t: "Yellow", d: "Restocking fee" }, { v: "red", t: "Red", d: "Final sale" }].map((opt) => (
                  <button key={opt.v} type="button" onClick={() => setVehicleReturnPolicy(opt.v)} style={{
                    borderRadius: "var(--radius-md)", padding: "12px 14px", textAlign: "left", cursor: "pointer",
                    border: vehicleReturnPolicy === opt.v ? "2px solid rgba(255,92,26,0.5)" : "1px solid var(--border)",
                    background: vehicleReturnPolicy === opt.v ? "rgba(255,92,26,0.08)" : "var(--bg-elevated)",
                    transition: "all 0.12s",
                  }}>
                    <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{opt.t}</p>
                    <p style={{ fontSize: 11, color: "var(--text-muted)" }}>{opt.d}</p>
                  </button>
                ))}
              </div>
            </div>
            <div style={{ background: "var(--bg-elevated)", border: "1px dashed var(--border)", borderRadius: "var(--radius-md)", padding: "12px 14px" }}>
              <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>Apply this return policy to existing parts</p>
              <div className="flex flex-wrap gap-2">
                {[["This page", "page", parts.length], ["Selected", "selected", selectedPartIds.length]].map(([lbl, scope, count]) => (
                  <button key={scope} type="button" disabled={bulkBusy || count === 0}
                    onClick={() => void applyReturnPolicyToParts(scope)}
                    style={{ ...btnSecondary, fontSize: 12, padding: "6px 12px", opacity: (bulkBusy || count === 0) ? 0.5 : 1 }}>
                    {lbl} ({count})
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Damage */}
      <div style={sectionStyle}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p style={sectionHeader}>Vehicle damage</p>
            <p style={sectionSub}>Accurate damage info helps buyers make confident decisions and reduces disputes.</p>
          </div>
          {vehicleEditMode && (
            <button type="button" disabled={damageSaving} onClick={() => void saveDamage()}
              className="btn-forge" style={{ padding: "8px 18px", fontSize: 13, opacity: damageSaving ? 0.5 : 1 }}>
              {damageSaving ? "Saving…" : "Save damage"}
            </button>
          )}
        </div>

        {!vehicleEditMode ? (
          <div style={{ marginTop: 12, background: "var(--bg-elevated)", borderRadius: "var(--radius-md)", padding: "12px 14px" }}>
            <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
              {vehicle.has_damage ? "Has reported damage" : "No damage reported"}
            </p>
            {vehicle.has_damage && Array.isArray(vehicle.damage_items) && vehicle.damage_items.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {vehicle.damage_items.map((item) => (
                  <span key={item} style={{ background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: "999px", padding: "2px 10px", fontSize: 11, fontWeight: 500, color: "#f87171" }}>
                    {item}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="mt-3 flex gap-2">
              {[["No damage", false], ["Has damage", true]].map(([lbl, val]) => (
                <button key={lbl} type="button" onClick={() => { setHasDamage(val); if (!val) setDamageItems([]); }}
                  style={{
                    borderRadius: "var(--radius-md)", padding: "8px 16px", fontSize: 13, fontWeight: 600, fontFamily: "var(--ff-display)", cursor: "pointer", transition: "all 0.12s",
                    background: hasDamage === val ? (val ? "rgba(239,68,68,0.12)" : "rgba(34,197,94,0.12)") : "var(--bg-elevated)",
                    border: hasDamage === val ? `1px solid ${val ? "rgba(239,68,68,0.35)" : "rgba(34,197,94,0.35)"}` : "1px solid var(--border)",
                    color: hasDamage === val ? (val ? "#f87171" : "#4ade80") : "var(--text-secondary)",
                  }}>
                  {lbl}
                </button>
              ))}
            </div>
            {hasDamage && (
              <div className="mt-4">
                <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 8 }}>
                  Select all that apply
                </p>
                <div className="flex flex-wrap gap-2 mb-4">
                  {DAMAGE_OPTIONS.map((opt) => {
                    const sel = damageItems.includes(opt);
                    return (
                      <button key={opt} type="button" onClick={() => toggleDamageItem(opt)}
                        style={{
                          borderRadius: "999px", padding: "5px 12px", fontSize: 12, fontWeight: 500, cursor: "pointer", transition: "all 0.12s",
                          background: sel ? "rgba(239,68,68,0.12)" : "var(--bg-elevated)",
                          border: sel ? "1px solid rgba(239,68,68,0.35)" : "1px solid var(--border)",
                          color: sel ? "#f87171" : "var(--text-secondary)",
                        }}>
                        {sel && "✓ "}{opt}
                      </button>
                    );
                  })}
                </div>
                <div className="flex gap-2">
                  <input type="text" placeholder="Other damage…" value={customDamageInput}
                    onChange={(e) => setCustomDamageInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustomDamage(); } }}
                    style={{ ...inputStyle, flex: 1 }} />
                  <button type="button" disabled={!customDamageInput.trim()} onClick={addCustomDamage}
                    style={{ ...btnSecondary, opacity: !customDamageInput.trim() ? 0.4 : 1 }}>
                    Add
                  </button>
                </div>
                {damageItems.filter((x) => !DAMAGE_OPTIONS.includes(x)).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {damageItems.filter((x) => !DAMAGE_OPTIONS.includes(x)).map((item) => (
                      <span key={item} style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: "999px", padding: "4px 12px", fontSize: 11, color: "#f87171" }}>
                        {item}
                        <button type="button" onClick={() => setDamageItems((prev) => prev.filter((x) => x !== item))}
                          style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", fontSize: 14, padding: 0, lineHeight: 1 }} aria-label={`Remove ${item}`}>
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Parts section */}
      <div className="mt-6">
        {vehicleEditMode && (
          <>
            {/* Price template */}
            <div style={{ ...sectionStyle, marginTop: 0, marginBottom: 12 }}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p style={sectionHeader}>Price template</p>
                  <p style={sectionSub}>Paste lines like <span style={{ fontFamily: "var(--ff-mono)" }}>ENGINE COMPLETE $519.99</span>. Matching parts will be set to Buy Now.</p>
                </div>
                <button type="button" disabled={templateBusy || busy || !priceTemplateText.trim()} onClick={() => void applyPriceTemplate()}
                  className="btn-forge" style={{ padding: "8px 18px", fontSize: 13, opacity: (templateBusy || busy || !priceTemplateText.trim()) ? 0.5 : 1 }}>
                  {templateBusy ? "Applying…" : "Apply template"}
                </button>
              </div>
              <textarea value={priceTemplateText} onChange={(e) => setPriceTemplateText(e.target.value)} rows={7}
                placeholder={"ENGINE COMPLETE $519.99\nENGINE DIESEL COMPLETE $727.99\nMOTOR MOUNT $24.69"}
                style={{ ...inputStyle, marginTop: 12, fontFamily: "var(--ff-mono)", resize: "vertical" }} />
              <div className="mt-2 flex gap-3">
                <button type="button" disabled={!priceTemplateText.trim()} onClick={() => setPriceTemplateText("")}
                  style={{ fontSize: 12, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline", opacity: !priceTemplateText.trim() ? 0.4 : 1 }}>
                  Clear
                </button>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Unmatched lines will create new part types automatically.</span>
              </div>
            </div>

            {/* Custom part */}
            <div style={{ ...sectionStyle, marginTop: 0, marginBottom: 12 }}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p style={sectionHeader}>Add custom part</p>
                  <p style={sectionSub}>Create a new part name for this vehicle.</p>
                </div>
                <button type="button" disabled={customPartBusy || busy || !customPartName.trim() || !customPartCategoryId}
                  onClick={() => void addCustomPart()} className="btn-forge"
                  style={{ padding: "8px 18px", fontSize: 13, opacity: (customPartBusy || busy || !customPartName.trim() || !customPartCategoryId) ? 0.5 : 1 }}>
                  {customPartBusy ? "Adding…" : "Add part"}
                </button>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <input value={customPartName} onChange={(e) => setCustomPartName(e.target.value)}
                  placeholder="e.g. Custom bracket" style={{ ...inputStyle, gridColumn: "span 2" }} className="sm:col-span-2" />
                <select value={customPartCategoryId} onChange={(e) => setCustomPartCategoryId(e.target.value)} style={selectStyle}>
                  <option value="">Category…</option>
                  {categories.map((c) => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
                </select>
              </div>
            </div>
          </>
        )}

        {!vehicleEditMode && (
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 12 }}>
            Turn on <span style={{ fontWeight: 600, color: "var(--text-secondary)" }}>Edit vehicle details</span> above to use price template import and add custom parts.
          </p>
        )}

        {/* Parts controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{partsCount} parts</span>
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={partSearchInput}
              onChange={(e) => setPartSearchInput(e.target.value)}
              placeholder="Search by name or part type…"
              style={{ ...inputStyle, width: "auto", minWidth: 180 }}
              aria-label="Search parts"
            />
            <select value={ordering} onChange={(e) => { setPage(1); setOrdering(e.target.value); }} style={{ ...selectStyle, width: "auto" }}>
              <option value="updated">Sort: Recently updated</option>
              <option value="price_asc">Price low → high</option>
              <option value="price_desc">Price high → low</option>
              <option value="label_asc">Name A → Z</option>
              <option value="label_desc">Name Z → A</option>
            </select>
            <select value={categoryFilter} onChange={(e) => { setPage(1); setCategoryFilter(e.target.value); }} style={{ ...selectStyle, width: "auto" }}>
              <option value="">All categories</option>
              {categories.map((c) => <option key={c.id} value={c.slug}>{c.name}</option>)}
            </select>
          </div>
        </div>

        {/* Listing tabs */}
        <div className="flex flex-wrap gap-2 mb-3">
          {[{ key: "buy_now", label: "Buy now" }, { key: "draft", label: "Draft" }, { key: "sold", label: "Sold" }, { key: "sold_elsewhere", label: "Sold elsewhere" }, { key: "unavailable", label: "Unavailable" }, { key: "", label: "All" }].map((t) => {
            const active = listingTab === t.key;
            return (
              <button key={t.key} type="button" onClick={() => { setPage(1); setListingTab(t.key); }}
                style={{
                  borderRadius: "999px", padding: "6px 14px", fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)", cursor: "pointer", transition: "all 0.12s",
                  background: active ? "var(--primary)" : "var(--bg-elevated)",
                  border: active ? "none" : "1px solid var(--border)",
                  color: active ? "#fff" : "var(--text-secondary)",
                }}>
                {t.label}
              </button>
            );
          })}
          <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-muted)", alignSelf: "center" }}>
            Sold/Unavailable hides entries older than 90 days.
          </span>
        </div>

        {/* Bulk actions */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <button type="button" disabled={bulkBusy || selectedPartIds.length === 0} onClick={() => void bulkDeleteSelected()}
            style={{
              borderRadius: "var(--radius-md)", padding: "7px 14px", fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)", cursor: "pointer", transition: "all 0.12s",
              background: "transparent", border: "1px solid rgba(239,68,68,0.3)", color: "#f87171",
              opacity: (bulkBusy || selectedPartIds.length === 0) ? 0.4 : 1,
            }}>
            {bulkBusy ? "Deleting…" : `Delete selected (${selectedPartIds.length})`}
          </button>
          {selectedPartIds.length > 0 && (
            <button type="button" disabled={bulkBusy} onClick={() => setSelectedPartIds([])}
              style={{ fontSize: 12, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}>
              Clear selection
            </button>
          )}
        </div>

        {partsPaginationInner ? <div className="mb-4">{partsPaginationInner}</div> : null}

        <div className="flex flex-col gap-3">
          {parts.map((p) => (
            <PartListingCard key={p.id} part={p} vehicle={vehicle} disabled={busy}
              onSave={(partId, payload) => patchPart(partId, payload)}
              onDelete={(partId) => void deletePart(partId)}
              onUploadPhoto={(partId, file) => uploadPartPhoto(partId, file)}
              selected={selectedPartIds.includes(p.id)}
              onToggleSelected={toggleSelectedPart} />
          ))}
        </div>

        {partsPaginationInner ? (
          <div className="mt-5 border-t pt-5" style={{ borderColor: "var(--border)" }}>
            {partsPaginationInner}
          </div>
        ) : null}

        {parts.length === 0 && (
          <p style={{ marginTop: 24, textAlign: "center", fontSize: 13, color: "var(--text-muted)" }}>No parts for this filter.</p>
        )}
      </div>

      <p className="mt-10 text-sm">
        <Link href="/dashboard" style={{ color: "var(--primary)", textDecoration: "none" }}
          onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
          onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}>
          ← Account
        </Link>
      </p>
    </div>
  );
}
