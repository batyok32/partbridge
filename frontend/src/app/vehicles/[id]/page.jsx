"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { isApprovedSeller } from "@/lib/roles";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

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

function StatusBadge({ status }) {
  const colors = {
    pending_research: { bg: "rgba(251,191,36,0.12)", border: "rgba(251,191,36,0.3)", color: "#fbbf24" },
    researching: { bg: "rgba(56,189,248,0.12)", border: "rgba(56,189,248,0.3)", color: "#38bdf8" },
    active: { bg: "rgba(74,222,128,0.12)", border: "rgba(74,222,128,0.3)", color: "#4ade80" },
    archived: { bg: "rgba(148,163,184,0.12)", border: "rgba(148,163,184,0.3)", color: "#94a3b8" },
  };
  const c = colors[status] || colors.archived;
  return (
    <span style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.color, borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 600, fontFamily: "var(--ff-display)" }}>
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
  const [photoUrl, setPhotoUrl] = useState("");
  const [photoLabel, setPhotoLabel] = useState("");
  const [photoBusy, setPhotoBusy] = useState(false);
  const [editZip, setEditZip] = useState("");
  const [editColor, setEditColor] = useState("");
  const [editMileage, setEditMileage] = useState("");
  const [editCondition, setEditCondition] = useState("good");
  const [savingSettings, setSavingSettings] = useState(false);

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
        const [v, its] = await Promise.all([
          apiFetch(`/vehicles/${id}/`),
          apiFetch(`/vehicles/${id}/items/`),
        ]);
        if (!cancelled) {
          setVehicle(v);
          setEditZip(v?.seller_zip || "");
          setEditColor(v?.color || "");
          setEditMileage(v?.mileage != null ? String(v.mileage) : "");
          setEditCondition(v?.condition || "good");
          setItems(Array.isArray(its) ? its : []);
        }
      } catch (e) {
        if (!cancelled && e instanceof ApiError) toast.error(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, id, toast]);

  async function saveSettings() {
    setSavingSettings(true);
    try {
      const body = {
        seller_zip: editZip.trim(),
        color: editColor.trim() || undefined,
        condition: editCondition,
      };
      if (editMileage) body.mileage = parseInt(editMileage, 10);
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
    if (!photoUrl.trim()) { toast.warning("Enter a photo URL."); return; }
    setPhotoBusy(true);
    try {
      const body = { url: photoUrl.trim(), label: photoLabel.trim(), sort_order: vehicle?.photos?.length || 0 };
      const res = await apiFetch(`/vehicles/${id}/photos/`, { method: "POST", body: JSON.stringify(body) });
      setVehicle((v) => ({ ...v, photos: [...(v?.photos || []), res] }));
      setPhotoUrl("");
      setPhotoLabel("");
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

  if (authLoading || !user) {
    return <div className="mx-auto max-w-3xl px-6 py-16"><p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p></div>;
  }

  if (!loading && !vehicle) {
    return <div className="mx-auto max-w-3xl px-6 py-16"><p className="text-sm" style={{ color: "var(--text-muted)" }}>Vehicle not found.</p></div>;
  }

  const gen = vehicle?.generation_detail;
  const mod = vehicle?.modification_detail;
  const displayName = gen
    ? [gen.make_name, gen.car_model_name, gen.name].filter(Boolean).join(" ")
    : "Vehicle";

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        <div className="flex flex-wrap items-start justify-between gap-4 mb-2">
          <div>
            <p className="section-label mb-1">Inventory</p>
            <h1 className="heading-display text-2xl">{loading ? "Loading…" : displayName}</h1>
          </div>
          <Link href="/vehicles" style={{ color: "var(--text-muted)", fontSize: 13, textDecoration: "none", marginTop: 4 }}>← All vehicles</Link>
        </div>

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
                  <label style={{ ...labelStyle, display: "block" }}>Condition</label>
                  <select value={editCondition} onChange={(e) => setEditCondition(e.target.value)} style={inputStyle}>
                    <option value="excellent">Excellent</option>
                    <option value="good">Good</option>
                    <option value="fair">Fair</option>
                    <option value="for_parts">For parts</option>
                  </select>
                </div>
                <div>
                  <label style={{ ...labelStyle, display: "block" }}>Color</label>
                  <input value={editColor} onChange={(e) => setEditColor(e.target.value)} style={inputStyle} placeholder="e.g. Alpine White" />
                </div>
                <div>
                  <label style={{ ...labelStyle, display: "block" }}>Mileage</label>
                  <input type="number" value={editMileage} onChange={(e) => setEditMileage(e.target.value)} style={inputStyle} placeholder="miles" />
                </div>
                <div>
                  <label style={{ ...labelStyle, display: "block" }}>Origin ZIP *</label>
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
              <div className="flex gap-2">
                <input value={photoUrl} onChange={(e) => setPhotoUrl(e.target.value)} style={{ ...inputStyle, flex: 1 }} placeholder="Photo URL (CDN)" />
                <input value={photoLabel} onChange={(e) => setPhotoLabel(e.target.value)} style={{ ...inputStyle, width: 120 }} placeholder="Label" />
                <button type="button" onClick={addPhoto} disabled={photoBusy} className="btn-forge" style={{ flexShrink: 0, padding: "8px 14px", fontSize: 13, opacity: photoBusy ? 0.6 : 1 }}>
                  {photoBusy ? "…" : "Add"}
                </button>
              </div>
            </div>

            {/* Items (Parts) */}
            <div style={sectionStyle}>
              <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 12 }}>
                Parts / Items ({items.length})
              </p>
              {items.length === 0 ? (
                <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  No items yet. Items are created automatically when the AI research process runs.
                </p>
              ) : (
                <div className="space-y-2">
                  {items.map((item) => (
                    <div key={item.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", background: "var(--bg-elevated)", borderRadius: 8, border: "1px solid var(--border)" }}>
                      <div>
                        <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{item.title}</p>
                        <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 1 }}>
                          {item.category_name} · {item.condition} · {item.shipping_size}
                        </p>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
                          ${parseFloat(item.price).toFixed(2)}
                        </p>
                        <span style={{
                          fontSize: 10, fontWeight: 600, borderRadius: 999, padding: "1px 7px", marginTop: 2, display: "inline-block",
                          background: item.status === "active" ? "rgba(74,222,128,0.1)" : "rgba(148,163,184,0.1)",
                          color: item.status === "active" ? "#4ade80" : "#94a3b8",
                          border: item.status === "active" ? "1px solid rgba(74,222,128,0.3)" : "1px solid rgba(148,163,184,0.3)",
                        }}>{item.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {loading && (
          <p className="text-sm mt-8" style={{ color: "var(--text-muted)" }}>Loading vehicle…</p>
        )}
      </motion.div>
    </div>
  );
}
