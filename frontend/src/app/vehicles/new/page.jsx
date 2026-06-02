"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { isApprovedSeller } from "@/lib/roles";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch, getMakes, getModels, getGenerations, getModifications } from "@/lib/api";

const inputStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "9px 12px",
  fontSize: 14,
  outline: "none",
  fontFamily: "var(--ff-body)",
  width: "100%",
  transition: "border-color 0.12s",
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

export default function NewVehiclePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();

  const [makes, setMakes] = useState([]);
  const [models, setModels] = useState([]);
  const [generations, setGenerations] = useState([]);
  const [modifications, setModifications] = useState([]);

  const [makeId, setMakeId] = useState("");
  const [modelId, setModelId] = useState("");
  const [generationId, setGenerationId] = useState("");
  const [modificationId, setModificationId] = useState("");

  const [form, setForm] = useState({
    vin: "",
    year: "",
    color: "",
    mileage: "",
    condition: "good",
    seller_zip: "",
  });

  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!authLoading && user && !isApprovedSeller(user)) router.replace("/seller/apply");
  }, [authLoading, user, router]);

  useEffect(() => {
    getMakes().then((data) => setMakes(Array.isArray(data) ? data : data.results || [])).catch(() => {});
  }, []);

  useEffect(() => {
    setModelId("");
    setGenerationId("");
    setModificationId("");
    setModels([]);
    setGenerations([]);
    setModifications([]);
    if (!makeId) return;
    getModels(makeId).then((data) => setModels(Array.isArray(data) ? data : data.results || [])).catch(() => {});
  }, [makeId]);

  useEffect(() => {
    setGenerationId("");
    setModificationId("");
    setGenerations([]);
    setModifications([]);
    if (!modelId) return;
    getGenerations(modelId).then((data) => setGenerations(Array.isArray(data) ? data : data.results || [])).catch(() => {});
  }, [modelId]);

  useEffect(() => {
    setModificationId("");
    setModifications([]);
    if (!generationId) return;
    getModifications(generationId).then((data) => setModifications(Array.isArray(data) ? data : data.results || [])).catch(() => {});
  }, [generationId]);

  function update(name, value) {
    setForm((f) => ({ ...f, [name]: value }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!generationId) { toast.warning("Select a generation."); return; }
    if (!form.seller_zip.trim()) { toast.warning("ZIP code is required for shipping."); return; }
    setPending(true);
    try {
      const body = {
        generation: parseInt(generationId, 10),
        vin: form.vin.trim().toUpperCase() || undefined,
        color: form.color.trim() || undefined,
        seller_zip: form.seller_zip.trim(),
        condition: form.condition,
      };
      if (form.year) body.year = parseInt(form.year, 10);
      if (form.mileage) body.mileage = parseInt(form.mileage, 10);
      if (modificationId) body.modification = parseInt(modificationId, 10);

      const created = await apiFetch("/vehicles/", { method: "POST", body: JSON.stringify(body) });
      router.push(`/vehicles/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.body;
        if (typeof d.detail === "string") toast.error(d.detail);
        else if (d.generation) toast.error(Array.isArray(d.generation) ? d.generation[0] : String(d.generation));
        else toast.error(err.message);
      } else toast.error("Could not save vehicle.");
    } finally {
      setPending(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="mx-auto max-w-lg px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        <div className="mb-8">
          <p className="section-label mb-1">Inventory</p>
          <h1 className="heading-display text-2xl">Add a vehicle</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            Select the exact vehicle from the catalog, then fill in its details.
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "24px" }}
          className="space-y-4"
        >
          {/* Make */}
          <div>
            <label style={labelStyle}>Make *</label>
            <select value={makeId} onChange={(e) => setMakeId(e.target.value)} required style={inputStyle}>
              <option value="">Select make…</option>
              {makes.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </div>

          {/* Model */}
          <div>
            <label style={labelStyle}>Model *</label>
            <select value={modelId} onChange={(e) => setModelId(e.target.value)} required disabled={!makeId} style={inputStyle}>
              <option value="">Select model…</option>
              {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </div>

          {/* Generation */}
          <div>
            <label style={labelStyle}>Generation / Chassis *</label>
            <select value={generationId} onChange={(e) => setGenerationId(e.target.value)} required disabled={!modelId} style={inputStyle}>
              <option value="">Select generation…</option>
              {generations.map((g) => (
                <option key={g.id} value={g.id}>{g.display_label || `${g.name || g.chassis_codes?.join(", ") || g.id}`}</option>
              ))}
            </select>
          </div>

          {/* Modification (optional) */}
          {modifications.length > 0 && (
            <div>
              <label style={labelStyle}>Trim / Modification <span style={{ fontWeight: 400 }}>(optional)</span></label>
              <select value={modificationId} onChange={(e) => setModificationId(e.target.value)} style={inputStyle}>
                <option value="">Unknown / any</option>
                {modifications.map((m) => (
                  <option key={m.id} value={m.id}>{m.display_label || m.code}</option>
                ))}
              </select>
            </div>
          )}

          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "4px 0" }} />

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label style={labelStyle}>Year</label>
              <input
                type="number"
                value={form.year}
                onChange={(e) => update("year", e.target.value)}
                min={1900}
                max={new Date().getFullYear() + 1}
                placeholder="e.g. 2006"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Mileage</label>
              <input
                type="number"
                value={form.mileage}
                onChange={(e) => update("mileage", e.target.value)}
                min={0}
                placeholder="e.g. 120000"
                style={inputStyle}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label style={labelStyle}>Condition *</label>
              <select value={form.condition} onChange={(e) => update("condition", e.target.value)} required style={inputStyle}>
                <option value="excellent">Excellent</option>
                <option value="good">Good</option>
                <option value="fair">Fair</option>
                <option value="for_parts">For parts</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Color</label>
              <input value={form.color} onChange={(e) => update("color", e.target.value)} placeholder="e.g. Alpine White" style={inputStyle} />
            </div>
          </div>

          <div>
            <label style={labelStyle}>VIN <span style={{ fontWeight: 400 }}>(optional)</span></label>
            <input
              value={form.vin}
              onChange={(e) => update("vin", e.target.value.toUpperCase())}
              maxLength={17}
              style={{ ...inputStyle, fontFamily: "var(--ff-mono)", textTransform: "uppercase" }}
              placeholder="17-character VIN"
            />
          </div>

          <div>
            <label style={labelStyle}>Origin ZIP * <span style={{ fontWeight: 400 }}>(used for shipping cost estimates)</span></label>
            <input
              value={form.seller_zip}
              onChange={(e) => update("seller_zip", e.target.value)}
              required
              maxLength={10}
              placeholder="e.g. 98101"
              style={inputStyle}
            />
          </div>

          <button
            type="submit"
            disabled={pending}
            className="btn-forge w-full"
            style={{ padding: "12px 0", fontSize: 14, justifyContent: "center", opacity: pending ? 0.6 : 1 }}
          >
            {pending ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Saving…
              </span>
            ) : "Save vehicle →"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm">
          <Link
            href="/vehicles"
            style={{ color: "var(--primary)", textDecoration: "none" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--primary-bright)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--primary)")}
          >
            Cancel
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
