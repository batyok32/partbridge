"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { isApprovedSeller } from "@/lib/roles";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch, createVehicleItem, getCategories } from "@/lib/api";

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

const sectionStyle = {
  background: "var(--bg-surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-xl)",
  padding: "20px",
  marginTop: 20,
};

const labelStyle = {
  display: "block",
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "var(--text-muted)",
  fontFamily: "var(--ff-display)",
  marginBottom: 4,
};

const STATUS_COLORS = {
  pending_research: { bg: "rgba(251,191,36,0.12)", border: "rgba(251,191,36,0.3)", color: "#fbbf24" },
  researching:      { bg: "rgba(56,189,248,0.12)",  border: "rgba(56,189,248,0.3)",  color: "#38bdf8" },
  active:           { bg: "rgba(74,222,128,0.12)",  border: "rgba(74,222,128,0.3)",  color: "#4ade80" },
  archived:         { bg: "rgba(148,163,184,0.12)", border: "rgba(148,163,184,0.3)", color: "#94a3b8" },
};

const ITEM_STATUS_COLORS = {
  active:             { bg: "rgba(74,222,128,0.1)",  border: "rgba(74,222,128,0.3)",  color: "#4ade80" },
  sold:               { bg: "rgba(251,191,36,0.1)",  border: "rgba(251,191,36,0.3)",  color: "#fbbf24" },
  removed:            { bg: "rgba(148,163,184,0.1)", border: "rgba(148,163,184,0.3)", color: "#94a3b8" },
  hidden_in_assembly: { bg: "rgba(99,102,241,0.1)",  border: "rgba(99,102,241,0.3)",  color: "#818cf8" },
};

function StatusBadge({ status }) {
  const c = STATUS_COLORS[status] || STATUS_COLORS.archived;
  return (
    <span style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.color, borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 600, fontFamily: "var(--ff-display)" }}>
      {status?.replace(/_/g, " ")}
    </span>
  );
}

function ItemStatusBadge({ status }) {
  const c = ITEM_STATUS_COLORS[status] || ITEM_STATUS_COLORS.removed;
  return (
    <span style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.color, borderRadius: 999, padding: "1px 8px", fontSize: 10, fontWeight: 600, fontFamily: "var(--ff-display)", display: "inline-block" }}>
      {status?.replace(/_/g, " ")}
    </span>
  );
}

export default function VehicleDashboardPage() {
  const { id } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();

  const [vehicle, setVehicle] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  // Vehicle settings form
  const [photoFile, setPhotoFile] = useState(null);
  const [photoLabel, setPhotoLabel] = useState("");
  const [photoBusy, setPhotoBusy] = useState(false);
  const photoFileRef = useRef(null);
  const [editZip, setEditZip] = useState("");
  const [editColor, setEditColor] = useState("");
  const [editMileage, setEditMileage] = useState("");
  const [editCondition, setEditCondition] = useState("good");
  const [savingSettings, setSavingSettings] = useState(false);

  // Add item form
  const [showAddItem, setShowAddItem] = useState(false);
  const [categories, setCategories] = useState([]);
  const [newCategory, setNewCategory] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [newCondition, setNewCondition] = useState("good");
  const [newOem, setNewOem] = useState("");
  const [addingItem, setAddingItem] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!authLoading && user && !isApprovedSeller(user)) router.replace("/seller/apply");
  }, [authLoading, user, router]);

  const loadVehicle = useCallback(async () => {
    if (!user || !id) return;
    setLoading(true);
    try {
      const [v, its] = await Promise.all([
        apiFetch(`/vehicles/${id}/`),
        apiFetch(`/vehicles/${id}/items/`),
      ]);
      setVehicle(v);
      setEditZip(v?.seller_zip || "");
      setEditColor(v?.color || "");
      setEditMileage(v?.mileage != null ? String(v.mileage) : "");
      setEditCondition(v?.condition || "good");
      setItems(Array.isArray(its) ? its : []);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }, [user, id, toast]);

  useEffect(() => {
    void loadVehicle();
  }, [loadVehicle]);

  async function saveSettings() {
    setSavingSettings(true);
    try {
      const body = {
        seller_zip: editZip.trim(),
        // Send empty string to allow clearing; omit only if the field wasn't touched
        color: editColor.trim(),
        condition: editCondition,
      };
      if (editMileage !== "") body.mileage = parseInt(editMileage, 10);
      const updated = await apiFetch(`/vehicles/${id}/`, { method: "PATCH", body: JSON.stringify(body) });
      setVehicle(updated);
      toast.success("Vehicle updated.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setSavingSettings(false);
    }
  }

  async function addPhoto() {
    if (!photoFile) { toast.warning("Select a photo file."); return; }
    setPhotoBusy(true);
    try {
      const existingOrders = (vehicle?.photos || []).map((p) => p.sort_order);
      const nextOrder = existingOrders.length ? Math.max(...existingOrders) + 1 : 0;
      const fd = new FormData();
      fd.append("image", photoFile);
      if (photoLabel.trim()) fd.append("label", photoLabel.trim());
      fd.append("sort_order", String(nextOrder));
      const res = await apiFetch(`/vehicles/${id}/photos/`, { method: "POST", body: fd });
      setVehicle((v) => ({ ...v, photos: [...(v?.photos || []), res] }));
      setPhotoFile(null);
      setPhotoLabel("");
      if (photoFileRef.current) photoFileRef.current.value = "";
      toast.success("Photo added.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setPhotoBusy(false);
    }
  }

  async function deletePhoto(photoId) {
    try {
      await apiFetch(`/vehicles/${id}/photos/${photoId}/`, { method: "DELETE" });
      setVehicle((v) => ({ ...v, photos: (v?.photos || []).filter((p) => p.id !== photoId) }));
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  }

  async function openAddItem() {
    setShowAddItem(true);
    if (categories.length === 0) {
      try {
        const data = await getCategories();
        const list = Array.isArray(data) ? data : data?.results || [];
        setCategories(list);
        if (list.length > 0 && !newCategory) setNewCategory(String(list[0].id));
      } catch (e) {
        if (e instanceof ApiError) toast.error(e.message);
      }
    }
  }

  async function submitAddItem(e) {
    e.preventDefault();
    if (!newCategory || !newTitle.trim() || !newPrice) { toast.warning("Fill in all required fields."); return; }
    setAddingItem(true);
    try {
      const item = await createVehicleItem(id, {
        category: Number(newCategory),
        title: newTitle.trim(),
        price: newPrice,
        condition: newCondition,
        oem_part_number: newOem.trim(),
      });
      setItems((prev) => [item, ...prev]);
      setShowAddItem(false);
      setNewTitle(""); setNewPrice(""); setNewOem(""); setNewCondition("good");
      toast.success("Item created.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setAddingItem(false);
    }
  }

  if (authLoading || !user) {
    return <div className="mx-auto max-w-3xl px-6 py-16"><p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p></div>;
  }

  const gen = vehicle?.generation_detail;
  const mod = vehicle?.modification_detail;
  // Graceful fallback: prefer generation detail, fall back to top-level fields, then VIN
  const displayName = gen
    ? [gen.make_name, gen.car_model_name, gen.name].filter(Boolean).join(" ")
    : [vehicle?.year, vehicle?.make_name, vehicle?.model_name].filter(Boolean).join(" ") || vehicle?.vin || "Vehicle";

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4 mb-2">
          <div>
            <p className="section-label mb-1">Inventory</p>
            <h1 className="heading-display text-2xl">
              {loading ? "Loading…" : displayName}
            </h1>
          </div>
          <Link href="/vehicles" style={{ color: "var(--text-muted)", fontSize: 13, textDecoration: "none", marginTop: 4 }}>← All vehicles</Link>
        </div>

        {loading && (
          <div style={{ marginTop: 40, textAlign: "center" }}>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading vehicle…</p>
          </div>
        )}

        {!loading && !vehicle && (
          <p className="text-sm mt-8" style={{ color: "var(--text-muted)" }}>Vehicle not found.</p>
        )}

        {!loading && vehicle && (
          <>
            {/* Status + summary */}
            <div style={sectionStyle}>
              <div className="flex flex-wrap items-center gap-3 mb-3">
                <StatusBadge status={vehicle.status} />
                {vehicle.year && <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Year {vehicle.year}</span>}
                {vehicle.vin && <span style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "var(--ff-mono)" }}>{vehicle.vin}</span>}
              </div>

              {gen && (
                <div className="grid grid-cols-2 gap-x-6 gap-y-1" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                  <div><span style={{ color: "var(--text-muted)" }}>Make</span> — {gen.make_name}</div>
                  <div><span style={{ color: "var(--text-muted)" }}>Model</span> — {gen.car_model_name}</div>
                  {gen.name && <div><span style={{ color: "var(--text-muted)" }}>Generation</span> — {gen.name}</div>}
                  {gen.chassis_codes?.length > 0 && <div><span style={{ color: "var(--text-muted)" }}>Chassis</span> — {gen.chassis_codes.join(", ")}</div>}
                  {gen.body_style && <div><span style={{ color: "var(--text-muted)" }}>Body</span> — {gen.body_style}</div>}
                  {gen.production_start && <div><span style={{ color: "var(--text-muted)" }}>Produced</span> — {gen.production_start?.slice(0, 4)}–{gen.production_end?.slice(0, 4) || "present"}</div>}
                  {mod?.engine_code && <div><span style={{ color: "var(--text-muted)" }}>Engine</span> — {mod.engine_code}</div>}
                  {mod?.transmission_type && <div><span style={{ color: "var(--text-muted)" }}>Transmission</span> — {mod.transmission_type}</div>}
                </div>
              )}
            </div>

            {/* Editable settings */}
            <div style={sectionStyle}>
              <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 12 }}>Vehicle details</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label style={labelStyle}>Condition</label>
                  <select value={editCondition} onChange={(e) => setEditCondition(e.target.value)} style={inputStyle}>
                    <option value="excellent">Excellent</option>
                    <option value="good">Good</option>
                    <option value="fair">Fair</option>
                    <option value="for_parts">For parts</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Color</label>
                  <input
                    value={editColor}
                    onChange={(e) => setEditColor(e.target.value)}
                    style={inputStyle}
                    placeholder="e.g. Alpine White (leave blank to clear)"
                  />
                </div>
                <div>
                  <label style={labelStyle}>Mileage</label>
                  <input type="number" min={0} value={editMileage} onChange={(e) => setEditMileage(e.target.value)} style={inputStyle} placeholder="miles" />
                </div>
                <div>
                  <label style={labelStyle}>Origin ZIP *</label>
                  <input value={editZip} onChange={(e) => setEditZip(e.target.value)} required maxLength={10} style={inputStyle} placeholder="98101" />
                </div>
              </div>
              <button
                type="button"
                onClick={saveSettings}
                disabled={savingSettings}
                className="btn-forge mt-3"
                style={{ padding: "8px 20px", fontSize: 13, opacity: savingSettings ? 0.6 : 1 }}
              >
                {savingSettings ? "Saving…" : "Save"}
              </button>
            </div>

            {/* Photos */}
            <div style={sectionStyle}>
              <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 12 }}>
                Photos ({vehicle.photos?.length || 0})
              </p>
              {vehicle.photos?.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {vehicle.photos.map((ph) => (
                    <div key={ph.id} style={{ position: "relative", width: 80, height: 80, borderRadius: 8, overflow: "hidden", border: "1px solid var(--border)" }}>
                      <img src={ph.url} alt={ph.label || "photo"} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      <button
                        type="button"
                        onClick={() => deletePhoto(ph.id)}
                        style={{ position: "absolute", top: 2, right: 2, background: "rgba(0,0,0,0.6)", border: "none", borderRadius: 4, color: "#fff", fontSize: 10, padding: "1px 4px", cursor: "pointer" }}
                      >✕</button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-2 flex-wrap">
                <input
                  ref={photoFileRef}
                  type="file"
                  accept="image/*"
                  onChange={(e) => setPhotoFile(e.target.files[0] || null)}
                  style={{ ...inputStyle, flex: 1, cursor: "pointer" }}
                />
                <input value={photoLabel} onChange={(e) => setPhotoLabel(e.target.value)} style={{ ...inputStyle, width: 110 }} placeholder="Label (optional)" />
                <button type="button" onClick={addPhoto} disabled={photoBusy || !photoFile} className="btn-forge" style={{ flexShrink: 0, padding: "8px 14px", fontSize: 13, opacity: (photoBusy || !photoFile) ? 0.6 : 1 }}>
                  {photoBusy ? "…" : "Upload"}
                </button>
              </div>
            </div>

            {/* Items (Parts) */}
            <div style={sectionStyle}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                  Parts / Items ({items.length})
                </p>
                <button
                  type="button"
                  onClick={showAddItem ? () => setShowAddItem(false) : openAddItem}
                  className="btn-forge"
                  style={{ padding: "6px 14px", fontSize: 12 }}
                >
                  {showAddItem ? "Cancel" : "+ Add item"}
                </button>
              </div>

              {/* Inline create form */}
              {showAddItem && (
                <form onSubmit={submitAddItem} style={{ marginBottom: 16, padding: 14, background: "var(--bg-elevated)", border: "1px solid var(--primary-border-strong, var(--border))", borderRadius: "var(--radius-lg)" }}>
                  <p style={{ fontSize: 11, fontWeight: 700, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>New item</p>
                  <div className="grid grid-cols-2 gap-2 mb-2">
                    <div>
                      <label style={labelStyle}>Category *</label>
                      <select value={newCategory} onChange={(e) => setNewCategory(e.target.value)} required style={{ ...inputStyle, cursor: "pointer" }}>
                        {categories.length === 0 && <option value="">Loading…</option>}
                        {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </div>
                    <div>
                      <label style={labelStyle}>Condition *</label>
                      <select value={newCondition} onChange={(e) => setNewCondition(e.target.value)} style={{ ...inputStyle, cursor: "pointer" }}>
                        <option value="excellent">Excellent</option>
                        <option value="good">Good</option>
                        <option value="fair">Fair</option>
                        <option value="for_parts">For parts</option>
                      </select>
                    </div>
                    <div className="col-span-2">
                      <label style={labelStyle}>Title *</label>
                      <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} required style={inputStyle} placeholder="e.g. Front bumper — E46 M3" />
                    </div>
                    <div>
                      <label style={labelStyle}>Price (USD) *</label>
                      <input type="number" min={0} step="0.01" value={newPrice} onChange={(e) => setNewPrice(e.target.value)} required style={inputStyle} placeholder="0.00" />
                    </div>
                    <div>
                      <label style={labelStyle}>OEM Part #</label>
                      <input value={newOem} onChange={(e) => setNewOem(e.target.value)} style={inputStyle} placeholder="Optional" />
                    </div>
                  </div>
                  <button type="submit" disabled={addingItem} className="btn-forge" style={{ padding: "8px 20px", fontSize: 13, opacity: addingItem ? 0.6 : 1 }}>
                    {addingItem ? "Creating…" : "Create item"}
                  </button>
                </form>
              )}

              {items.length === 0 ? (
                <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  No items yet. Add one above or wait for the AI research process to run.
                </p>
              ) : (
                <div className="space-y-2">
                  {items.map((item) => (
                    <div key={item.id} style={{ background: "var(--bg-elevated)", borderRadius: 8, border: "1px solid var(--border)", overflow: "hidden" }}>
                      {/* Clickable main row */}
                      <Link
                        href={`/vehicles/${id}/items/${item.id}`}
                        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "10px 12px", textDecoration: "none" }}
                      >
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{item.title}</p>
                          <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 1 }}>
                            {item.category_name}{item.oem_part_number ? ` · ${item.oem_part_number}` : ""}
                          </p>
                        </div>
                        <div style={{ textAlign: "right", flexShrink: 0 }}>
                          <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
                            ${parseFloat(item.price).toFixed(2)}
                          </p>
                          <ItemStatusBadge status={item.status} />
                        </div>
                        <span style={{ fontSize: 11, color: "var(--primary)", fontWeight: 600, flexShrink: 0 }}>Edit →</span>
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </motion.div>
    </div>
  );
}
