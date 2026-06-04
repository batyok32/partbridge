"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { isApprovedSeller } from "@/lib/roles";
import { useToast } from "@/context/toast-context";
import { ApiError, addItemPhoto, deleteItemPhoto, deleteVehicleItem, getCategories, getVehicleItem, updateVehicleItem } from "@/lib/api";

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

const sectionStyle = {
  background: "var(--bg-surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-xl)",
  padding: "20px",
  marginBottom: 16,
};

export default function ItemEditPage() {
  const { id: vehicleId, itemId } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();

  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);

  // Editable fields
  const [title, setTitle] = useState("");
  const [price, setPrice] = useState("");
  const [condition, setCondition] = useState("good");
  const [status, setStatus] = useState("active");
  const [description, setDescription] = useState("");
  const [oem, setOem] = useState("");
  const [shippingSize, setShippingSize] = useState("medium");
  const [weightLbs, setWeightLbs] = useState("");
  const [dimL, setDimL] = useState("");
  const [dimW, setDimW] = useState("");
  const [dimH, setDimH] = useState("");

  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Photos
  const [photos, setPhotos] = useState([]);
  const [photoFile, setPhotoFile] = useState(null);
  const [photoLabel, setPhotoLabel] = useState("");
  const [photoBusy, setPhotoBusy] = useState(false);
  const photoFileRef = useRef(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!authLoading && user && !isApprovedSeller(user)) router.replace("/seller/apply");
  }, [authLoading, user, router]);

  const loadItem = useCallback(async () => {
    if (!user || !vehicleId || !itemId) return;
    setLoading(true);
    try {
      const [it, cats] = await Promise.all([
        getVehicleItem(vehicleId, itemId),
        getCategories(),
      ]);
      setItem(it);
      setTitle(it.title || "");
      setPrice(it.price != null ? String(it.price) : "");
      setCondition(it.condition || "good");
      setStatus(it.status || "active");
      setDescription(it.description || "");
      setOem(it.oem_part_number || "");
      setShippingSize(it.shipping_size || "medium");
      setWeightLbs(it.weight_lbs != null ? String(it.weight_lbs) : "");
      setDimL(it.dim_l_in != null ? String(it.dim_l_in) : "");
      setDimW(it.dim_w_in != null ? String(it.dim_w_in) : "");
      setDimH(it.dim_h_in != null ? String(it.dim_h_in) : "");
      setPhotos(Array.isArray(it.photos) ? it.photos : []);
      const catList = Array.isArray(cats) ? cats : cats?.results || [];
      setCategories(catList);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }, [user, vehicleId, itemId, toast]);

  useEffect(() => {
    void loadItem();
  }, [loadItem]);

  async function saveItem(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const body = {
        title: title.trim(),
        price,
        condition,
        status,
        description: description.trim(),
        oem_part_number: oem.trim(),
        shipping_size: shippingSize,
      };
      if (weightLbs !== "") body.weight_lbs = weightLbs;
      if (dimL !== "") body.dim_l_in = dimL;
      if (dimW !== "") body.dim_w_in = dimW;
      if (dimH !== "") body.dim_h_in = dimH;

      const updated = await updateVehicleItem(vehicleId, itemId, body);
      setItem(updated);
      setShippingSize(updated.shipping_size || shippingSize);
      toast.success("Item saved.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    setDeleting(true);
    try {
      await deleteVehicleItem(vehicleId, itemId);
      toast.success("Item deleted.");
      router.replace(`/vehicles/${vehicleId}`);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleAddPhoto(e) {
    e.preventDefault();
    if (!photoFile) { toast.warning("Select a photo file."); return; }
    setPhotoBusy(true);
    try {
      const fd = new FormData();
      fd.append("image", photoFile);
      if (photoLabel.trim()) fd.append("label", photoLabel.trim());
      const photo = await addItemPhoto(vehicleId, itemId, fd);
      setPhotos((prev) => [...prev, photo]);
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

  async function handleDeletePhoto(photoId) {
    try {
      await deleteItemPhoto(vehicleId, itemId, photoId);
      setPhotos((prev) => prev.filter((p) => p.id !== photoId));
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  }

  if (authLoading || !user) {
    return <div className="mx-auto max-w-2xl px-6 py-16"><p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p></div>;
  }

  const hasDimensions = weightLbs !== "" || dimL !== "" || dimW !== "" || dimH !== "";

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
          <div>
            <p className="section-label mb-1">Inventory</p>
            <h1 className="heading-display text-2xl">
              {loading ? "Loading…" : (item?.title || "Edit item")}
            </h1>
          </div>
          <Link
            href={`/vehicles/${vehicleId}`}
            style={{ color: "var(--text-muted)", fontSize: 13, textDecoration: "none", marginTop: 4 }}
          >
            ← Vehicle
          </Link>
        </div>

        {loading && (
          <div style={{ textAlign: "center", paddingTop: 40 }}>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading item…</p>
          </div>
        )}

        {!loading && !item && (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Item not found.</p>
        )}

        {!loading && item && (
          <form onSubmit={saveItem}>
            {/* ── Core fields ── */}
            <div style={sectionStyle}>
              <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 12 }}>Core details</p>
              <div className="space-y-3">
                <div>
                  <label style={labelStyle}>Title *</label>
                  <input value={title} onChange={(e) => setTitle(e.target.value)} required style={inputStyle} placeholder="e.g. Front bumper — E46 M3" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label style={labelStyle}>Price (USD) *</label>
                    <input type="number" min={0} step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} required style={inputStyle} placeholder="0.00" />
                  </div>
                  <div>
                    <label style={labelStyle}>Condition *</label>
                    <select value={condition} onChange={(e) => setCondition(e.target.value)} style={{ ...inputStyle, cursor: "pointer" }}>
                      <option value="excellent">Excellent</option>
                      <option value="good">Good</option>
                      <option value="fair">Fair</option>
                      <option value="for_parts">For parts</option>
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Status</label>
                    <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ ...inputStyle, cursor: "pointer" }}>
                      <option value="active">Active</option>
                      <option value="removed">Removed</option>
                      <option value="sold">Sold</option>
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Category</label>
                    <p style={{ fontSize: 13, color: "var(--text-secondary)", padding: "8px 0" }}>
                      {item.category_name || "—"}
                    </p>
                  </div>
                </div>
                <div>
                  <label style={labelStyle}>OEM Part #</label>
                  <input value={oem} onChange={(e) => setOem(e.target.value)} style={inputStyle} placeholder="e.g. 51117030748" />
                </div>
                <div>
                  <label style={labelStyle}>Description</label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={3}
                    style={{ ...inputStyle, resize: "vertical" }}
                    placeholder="Describe condition, fitment notes, included hardware…"
                  />
                </div>
              </div>
            </div>

            {/* ── Shipping ── */}
            <div style={sectionStyle}>
              <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 4 }}>Shipping</p>
              <p style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 12 }}>
                Fill in dimensions and weight to auto-compute size on save. Or set it manually.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label style={labelStyle}>Shipping size</label>
                  <select value={shippingSize} onChange={(e) => setShippingSize(e.target.value)} style={{ ...inputStyle, cursor: "pointer" }}>
                    <option value="small">Small ({"<"}12″, {"<"}10 lb)</option>
                    <option value="medium">Medium ({"<"}48″, {"<"}40 lb)</option>
                    <option value="large">Large (freight)</option>
                    <option value="xl">XL (heavy freight)</option>
                  </select>
                  {hasDimensions && (
                    <p style={{ fontSize: 10, color: "var(--primary)", marginTop: 4 }}>
                      Will be recomputed from dimensions on save.
                    </p>
                  )}
                </div>
                <div>
                  <label style={labelStyle}>Weight (lbs)</label>
                  <input type="number" min={0} step="0.1" value={weightLbs} onChange={(e) => setWeightLbs(e.target.value)} style={inputStyle} placeholder="optional" />
                </div>
                <div>
                  <label style={labelStyle}>Length (in)</label>
                  <input type="number" min={0} step="0.1" value={dimL} onChange={(e) => setDimL(e.target.value)} style={inputStyle} placeholder="optional" />
                </div>
                <div>
                  <label style={labelStyle}>Width (in)</label>
                  <input type="number" min={0} step="0.1" value={dimW} onChange={(e) => setDimW(e.target.value)} style={inputStyle} placeholder="optional" />
                </div>
                <div>
                  <label style={labelStyle}>Height (in)</label>
                  <input type="number" min={0} step="0.1" value={dimH} onChange={(e) => setDimH(e.target.value)} style={inputStyle} placeholder="optional" />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="btn-forge w-full justify-center mb-4"
              style={{ padding: "12px 0", fontSize: 14, opacity: saving ? 0.6 : 1 }}
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
          </form>
        )}

        {/* ── Photos ── */}
        {!loading && item && (
          <div style={sectionStyle}>
            <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 12 }}>
              Photos ({photos.length})
            </p>
            {photos.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {photos.map((ph) => (
                  <div key={ph.id} style={{ position: "relative", width: 88, height: 88, borderRadius: 8, overflow: "hidden", border: ph.is_primary ? "2px solid var(--primary)" : "1px solid var(--border)" }}>
                    <img src={ph.url} alt={ph.label || "photo"} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    {ph.is_primary && (
                      <span style={{ position: "absolute", bottom: 2, left: 2, fontSize: 9, fontWeight: 700, background: "var(--primary)", color: "#fff", padding: "1px 4px", borderRadius: 3 }}>
                        PRIMARY
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDeletePhoto(ph.id)}
                      style={{ position: "absolute", top: 2, right: 2, background: "rgba(0,0,0,0.65)", border: "none", borderRadius: 4, color: "#fff", fontSize: 10, padding: "1px 5px", cursor: "pointer" }}
                    >✕</button>
                  </div>
                ))}
              </div>
            )}
            <form onSubmit={handleAddPhoto} className="flex gap-2 flex-wrap">
              <input
                ref={photoFileRef}
                type="file"
                accept="image/*"
                onChange={(e) => setPhotoFile(e.target.files[0] || null)}
                style={{ ...inputStyle, flex: 1, cursor: "pointer" }}
              />
              <input value={photoLabel} onChange={(e) => setPhotoLabel(e.target.value)} style={{ ...inputStyle, width: 110 }} placeholder="Label (optional)" />
              <button type="submit" disabled={photoBusy || !photoFile} className="btn-forge" style={{ flexShrink: 0, padding: "8px 14px", fontSize: 13, opacity: (photoBusy || !photoFile) ? 0.6 : 1 }}>
                {photoBusy ? "…" : "Upload"}
              </button>
            </form>
          </div>
        )}

        {/* ── Danger zone ── */}
        {!loading && item && (
          <div style={{ ...sectionStyle, border: "1px solid rgba(239,68,68,0.25)", background: "rgba(239,68,68,0.04)" }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: "#f87171", fontFamily: "var(--ff-display)", marginBottom: 6 }}>Danger zone</p>
            <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>
              Deleting this item is permanent. Sold items with orders attached cannot be deleted.
            </p>
            {confirmDelete ? (
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deleting}
                  style={{ padding: "8px 18px", fontSize: 13, fontWeight: 700, background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.4)", color: "#f87171", borderRadius: "var(--radius-md)", cursor: "pointer", opacity: deleting ? 0.6 : 1 }}
                >
                  {deleting ? "Deleting…" : "Yes, delete item"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  style={{ padding: "8px 14px", fontSize: 13, background: "transparent", border: "1px solid var(--border)", color: "var(--text-muted)", borderRadius: "var(--radius-md)", cursor: "pointer" }}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={handleDelete}
                style={{ padding: "8px 18px", fontSize: 13, fontWeight: 600, background: "transparent", border: "1px solid rgba(239,68,68,0.35)", color: "#f87171", borderRadius: "var(--radius-md)", cursor: "pointer" }}
              >
                Delete item
              </button>
            )}
          </div>
        )}
      </motion.div>
    </div>
  );
}
