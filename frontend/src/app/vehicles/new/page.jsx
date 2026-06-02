"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
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
  const [pending, setPending] = useState(false);
  const [decoding, setDecoding] = useState(false);
  const [form, setForm] = useState({
    vin: "",
    year: "",
    make: "",
    model: "",
    trim: "",
    engine: "",
    transmission: "",
    drivetrain: "",
    body_style: "",
    color: "",
    location_state: "WA",
    location_zip: "",
    notes: "",
  });

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!authLoading && user && !isApprovedSeller(user)) router.replace("/seller/apply");
  }, [authLoading, user, router]);

  function update(name, value) {
    setForm((f) => ({ ...f, [name]: value }));
  }

  function applySuggested(s) {
    if (!s) return;
    setForm((f) => ({
      ...f,
      year: s.year != null ? String(s.year) : f.year,
      make: s.make || f.make,
      model: s.model || f.model,
      trim: s.trim || f.trim,
      engine: s.engine || f.engine,
      transmission: s.transmission || f.transmission,
      drivetrain: s.drivetrain || f.drivetrain,
      body_style: s.body_style || f.body_style,
      color: s.color || f.color,
    }));
  }

  async function decodeVin() {
    const vin = form.vin.trim().toUpperCase();
    if (vin.length !== 17) { toast.warning("Enter a full 17-character VIN first."); return; }
    setDecoding(true);
    try {
      const res = await apiFetch("/vin/decode/", { method: "POST", body: JSON.stringify({ vin }) });
      applySuggested(res.suggested);
      if (res.nhtsa_warning && res.nhtsa_error_text) {
        toast.warning(`NHTSA note: ${res.nhtsa_error_text} — you can still edit fields manually.`);
      } else {
        toast.success("Filled from NHTSA. Review and correct if needed.");
      }
    } catch (err) {
      if (err instanceof ApiError) toast.error(err.message);
      else toast.error("Decode failed.");
    } finally {
      setDecoding(false);
    }
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!form.location_state.trim() || !form.location_zip.trim()) {
      toast.warning("State and ZIP are required (shipping rules).");
      return;
    }
    setPending(true);
    try {
      const body = {
        vin: form.vin.trim().toUpperCase(),
        make: form.make.trim(),
        model: form.model.trim(),
        trim: form.trim.trim(),
        engine: form.engine.trim(),
        transmission: form.transmission.trim(),
        drivetrain: form.drivetrain.trim(),
        body_style: form.body_style.trim(),
        color: form.color.trim(),
        location_state: form.location_state.trim().toUpperCase(),
        location_zip: form.location_zip.trim(),
        notes: form.notes.trim(),
      };
      if (form.year) body.year = parseInt(form.year, 10);
      const created = await apiFetch("/vehicles/", { method: "POST", body: JSON.stringify(body) });
      router.push(`/vehicles/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.body;
        if (typeof d.detail === "string") toast.error(d.detail);
        else if (d.vin) toast.error(Array.isArray(d.vin) ? d.vin[0] : String(d.vin));
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
            Decode the VIN with NHTSA, fix anything wrong, then add location.
          </p>
        </div>

        <form onSubmit={onSubmit}
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "24px" }}
          className="space-y-4">

          {/* VIN + Decode */}
          <div>
            <label style={labelStyle} htmlFor="vin">VIN (17 characters)</label>
            <div className="flex gap-2">
              <input
                id="vin"
                value={form.vin}
                onChange={(e) => update("vin", e.target.value.toUpperCase())}
                required
                minLength={17}
                maxLength={17}
                style={{ ...inputStyle, fontFamily: "var(--ff-mono)", textTransform: "uppercase" }}
                placeholder="1HGBH41JXMN109186"
              />
              <button
                type="button"
                onClick={() => void decodeVin()}
                disabled={decoding}
                style={{
                  flexShrink: 0,
                  borderRadius: "var(--radius-md)", padding: "9px 16px",
                  fontSize: 13, fontWeight: 600, fontFamily: "var(--ff-display)",
                  background: "var(--bg-elevated)", border: "1px solid var(--border)",
                  color: "var(--text-secondary)", cursor: "pointer", whiteSpace: "nowrap",
                  transition: "all 0.12s", opacity: decoding ? 0.5 : 1,
                }}
              >
                {decoding ? "…" : "Decode"}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {[["year","Year","number"],["make","Make","text"]].map(([name, lbl, type]) => (
              <div key={name}>
                <label style={labelStyle} htmlFor={name}>{lbl}</label>
                <input id={name} type={type} value={form[name]} onChange={(e) => update(name, e.target.value)} style={inputStyle} />
              </div>
            ))}
          </div>

          {[["model","Model"],["trim","Trim"],["engine","Engine"]].map(([name, lbl]) => (
            <div key={name}>
              <label style={labelStyle} htmlFor={name}>{lbl}</label>
              <input id={name} value={form[name]} onChange={(e) => update(name, e.target.value)} style={inputStyle} />
            </div>
          ))}

          <div className="grid grid-cols-2 gap-3">
            {[["transmission","Transmission"],["drivetrain","Drivetrain"],["body_style","Body style"],["color","Color"]].map(([name, lbl]) => (
              <div key={name}>
                <label style={labelStyle} htmlFor={name}>{lbl}</label>
                <input id={name} value={form[name]} onChange={(e) => update(name, e.target.value)} style={inputStyle} />
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label style={labelStyle} htmlFor="location_state">State *</label>
              <input
                id="location_state"
                value={form.location_state}
                onChange={(e) => update("location_state", e.target.value)}
                maxLength={2}
                required
                style={{ ...inputStyle, textTransform: "uppercase" }}
              />
            </div>
            <div>
              <label style={labelStyle} htmlFor="location_zip">ZIP *</label>
              <input
                id="location_zip"
                value={form.location_zip}
                onChange={(e) => update("location_zip", e.target.value)}
                required
                style={inputStyle}
              />
            </div>
          </div>

          <div>
            <label style={labelStyle} htmlFor="notes">Notes</label>
            <textarea
              id="notes"
              rows={3}
              value={form.notes}
              onChange={(e) => update("notes", e.target.value)}
              style={{ ...inputStyle, resize: "vertical" }}
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
          <Link href="/vehicles"
            style={{ color: "var(--primary)", textDecoration: "none" }}
            onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
            onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}>
            Cancel
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
