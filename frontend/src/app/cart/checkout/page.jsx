"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { lookupUsZip } from "@/lib/us-zip-lookup";

const LABELS = { standard: "Standard", next_day: "Next day", pickup: "Pickup" };

const inputStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "8px 10px",
  fontSize: 13,
  outline: "none",
  fontFamily: "var(--ff-body)",
  width: "100%",
};

export default function CartCheckoutFlowPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();

  const [step, setStep] = useState(1);
  const [addresses, setAddresses] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);

  const [buyerState, setBuyerState] = useState("WA");
  const [buyerZip, setBuyerZip] = useState("");
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [city, setCity] = useState("");
  const [label, setLabel] = useState("Home");
  const [recipientName, setRecipientName] = useState("");
  const [showNewForm, setShowNewForm] = useState(false);
  const [editingId, setEditingId] = useState(null);

  const [zipLookupBusy, setZipLookupBusy] = useState(false);
  const [zipLookupNote, setZipLookupNote] = useState("");
  const [zipPlaces, setZipPlaces] = useState([]);
  const lastLookupZipRef = useRef(null);

  const [preview, setPreview] = useState(null);
  const [summaryAddress, setSummaryAddress] = useState(null);

  const loadAddresses = useCallback(async () => {
    const data = await apiFetch("/shipping-addresses/");
    const list = Array.isArray(data) ? data : [];
    setAddresses(list);
    const def = list.find((a) => a.is_default) || list[0];
    if (def) {
      setSelectedId(def.id);
      setBuyerState(def.state || "WA");
      setBuyerZip(def.postal_code || "");
    } else {
      setShowNewForm(true);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    void (async () => {
      try {
        await loadAddresses();
      } catch (e) {
        if (e instanceof ApiError) toast.error(e.message);
      }
    })();
  }, [authLoading, user, loadAddresses, toast]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=%2Fcart%2Fcheckout");
  }, [authLoading, user, router]);

  function buildAddressSnapshot() {
    if (showNewForm) {
      return {
        id: editingId,
        label: label.trim() || "Home",
        recipient_name: recipientName.trim(),
        line1: line1.trim(),
        line2: line2.trim(),
        city: city.trim(),
        state: (buyerState || "").trim().toUpperCase().slice(0, 2),
        postal_code: (buyerZip || "").trim(),
      };
    }
    const sel = addresses.find((a) => a.id === selectedId);
    if (sel) return { ...sel };
    return {
      label: label.trim() || "Home",
      recipient_name: recipientName.trim(),
      line1: line1.trim(),
      line2: line2.trim(),
      city: city.trim(),
      state: (buyerState || "").trim().toUpperCase().slice(0, 2),
      postal_code: (buyerZip || "").trim(),
    };
  }

  const tryLookupZip = useCallback(async () => {
    const digits = (buyerZip || "").replace(/\D/g, "").slice(0, 5);
    if (digits.length !== 5) {
      setZipLookupNote("");
      setZipPlaces([]);
      lastLookupZipRef.current = null;
      return;
    }
    if (lastLookupZipRef.current === digits) return;
    setZipLookupBusy(true);
    try {
      const data = await lookupUsZip(digits);
      if (data?.city && data?.state) {
        lastLookupZipRef.current = digits;
        setCity(data.city);
        setBuyerState(data.state);
        if (data.postal_code) setBuyerZip(String(data.postal_code).replace(/\D/g, "").slice(0, 5));
        const places = Array.isArray(data.places) ? data.places : [];
        setZipPlaces(places.length > 1 ? places : []);
        const alt = places.length > 1;
        setZipLookupNote(
          alt
            ? `${data.city}, ${data.state} — this ZIP covers multiple cities; pick the right one below if needed.`
            : `${data.city}, ${data.state} — adjust if your street is in a different town for this ZIP.`,
        );
      }
    } catch (e) {
      lastLookupZipRef.current = null;
      setZipPlaces([]);
      setZipLookupNote("ZIP not found — enter city and state manually.");
      if (e instanceof ApiError) {
        if (e.status === 404) toast.warning("Could not look up that ZIP — enter city and state manually.");
        else toast.error(e.message);
      }
    } finally {
      setZipLookupBusy(false);
    }
  }, [buyerZip, toast]);

  useEffect(() => {
    const digits = (buyerZip || "").replace(/\D/g, "").slice(0, 5);
    if (digits.length < 5) {
      lastLookupZipRef.current = null;
    }
  }, [buyerZip]);

  useEffect(() => {
    if (!showNewForm) return;
    const digits = (buyerZip || "").replace(/\D/g, "").slice(0, 5);
    if (digits.length !== 5) return;
    const t = setTimeout(() => {
      void tryLookupZip();
    }, 500);
    return () => clearTimeout(t);
  }, [buyerZip, showNewForm, tryLookupZip]);

  function startEdit(a) {
    setEditingId(a.id);
    setSelectedId(a.id);
    setShowNewForm(true);
    setLabel(a.label || "");
    setRecipientName(a.recipient_name || "");
    setLine1(a.line1 || "");
    setLine2(a.line2 || "");
    setCity(a.city || "");
    setBuyerState((a.state || "WA").toUpperCase().slice(0, 2));
    setBuyerZip(a.postal_code || "");
    setZipLookupNote(`${a.city || ""}, ${a.state || ""} — edit if needed`.replace(/^[\s,—]+/, ""));
    setZipPlaces([]);
    lastLookupZipRef.current = null;
  }

  function cancelEdit() {
    setEditingId(null);
    setShowNewForm(false);
    setZipLookupNote("");
    setZipPlaces([]);
    void loadAddresses();
  }

  async function saveNewAddress(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = {
        label: label.trim() || "Home",
        recipient_name: recipientName.trim(),
        line1: line1.trim(),
        line2: line2.trim(),
        city: city.trim(),
        state: buyerState.trim().toUpperCase().slice(0, 2),
        postal_code: buyerZip.trim(),
      };
      if (editingId) {
        await apiFetch(`/shipping-addresses/${editingId}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        await loadAddresses();
        setSelectedId(editingId);
        setEditingId(null);
        setShowNewForm(false);
        toast.success("Address updated.");
      } else {
        const r = await apiFetch("/shipping-addresses/", {
          method: "POST",
          body: JSON.stringify({
            ...payload,
            is_default: addresses.length === 0,
          }),
        });
        await loadAddresses();
        setSelectedId(r.id);
        setShowNewForm(false);
        toast.success("Address saved.");
      }
    } catch (e2) {
      if (e2 instanceof ApiError) toast.error(e2.message);
    } finally {
      setBusy(false);
    }
  }

  async function goToSummary() {
    const st = (buyerState || "").trim().toUpperCase().slice(0, 2);
    const zip = (buyerZip || "").trim();
    if (!st || st.length !== 2) {
      toast.error("Enter a valid 2-letter state.");
      return;
    }
    if (!zip) {
      toast.error("Enter a ZIP/postal code for shipping quotes.");
      return;
    }
    setBusy(true);
    try {
      const r = await apiFetch("/cart/preview-checkout/", {
        method: "POST",
        body: JSON.stringify({ buyer_state: st, buyer_zip: zip }),
      });
      setSummaryAddress(buildAddressSnapshot());
      setPreview(r);
      setStep(2);
    } catch (e2) {
      if (e2 instanceof ApiError) {
        const u = e2.body?.unavailable;
        if (Array.isArray(u) && u.length) {
          toast.error(`Remove unavailable: ${u.map((x) => x.label).join(", ")}`);
        } else toast.error(e2.message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function placeOrders() {
    if (!preview) return;
    setBusy(true);
    try {
      const r = await apiFetch("/cart/checkout/", {
        method: "POST",
        body: JSON.stringify({
          buyer_state: preview.buyer_state,
          buyer_zip: preview.buyer_zip,
        }),
      });
      const checkoutUrl = r?.stripe_checkout_url;
      if (typeof checkoutUrl === "string" && checkoutUrl.startsWith("http")) {
        window.location.href = checkoutUrl;
        return;
      }
      toast.success(`${r.orders_created} order(s) placed — complete payment on the Orders page.`);
      router.push("/orders");
    } catch (e2) {
      if (e2 instanceof ApiError) {
        const u = e2.body?.unavailable;
        if (Array.isArray(u) && u.length) {
          toast.error(`Remove unavailable: ${u.map((x) => x.label).join(", ")}`);
        } else toast.error(e2.message);
      }
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10"
      >
        <div className="mb-6 flex items-center justify-between gap-3">
          <div>
            <p className="section-label mb-1">Checkout</p>
            <h1 className="heading-display text-2xl">{step === 1 ? "Ship to" : "Review & place"}</h1>
            <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
              Step {step} of 2
            </p>
          </div>
          <Link
            href="/cart"
            className="text-sm font-medium"
            style={{ color: "var(--primary)" }}
          >
            ← Cart
          </Link>
        </div>

        {step === 1 && (
          <div
            className="space-y-4"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-xl)",
              padding: "20px",
            }}
          >
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Choose a saved address or add one. Enter a ZIP in the form and we will fill city and state automatically — you can still edit them. Use <strong>Edit</strong> on a saved address to fix mistakes.
            </p>

            {addresses.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                  Address book
                </p>
                {addresses.map((a) => (
                  <div
                    key={a.id}
                    className="flex gap-2 items-stretch"
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedId(a.id);
                        setBuyerState(a.state);
                        setBuyerZip(a.postal_code);
                        setShowNewForm(false);
                        setEditingId(null);
                        setZipLookupNote("");
                        setZipPlaces([]);
                      }}
                      className="flex-1 text-left rounded-lg px-3 py-2.5 transition-colors"
                      style={{
                        border: selectedId === a.id ? "1px solid var(--primary-border-strong)" : "1px solid var(--border)",
                        background: selectedId === a.id ? "var(--primary-muted)" : "var(--bg-elevated)",
                      }}
                    >
                      <span className="text-sm font-semibold" style={{ color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                        {a.label}{a.is_default ? " · Default" : ""}
                      </span>
                      <span className="mt-0.5 block text-xs" style={{ color: "var(--text-muted)" }}>
                        {[a.line1, a.line2].filter(Boolean).join(", ")}
                        <br />
                        {a.city}, {a.state} {a.postal_code}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => startEdit(a)}
                      className="shrink-0 self-center rounded-lg px-3 py-2 text-xs font-semibold"
                      style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", color: "var(--primary)" }}
                    >
                      Edit
                    </button>
                  </div>
                ))}
              </div>
            )}

            <button
              type="button"
              onClick={() => {
                setShowNewForm((v) => {
                  const next = !v;
                  if (next) {
                    setSelectedId(null);
                    setEditingId(null);
                    setZipLookupNote("");
                    setZipPlaces([]);
                    lastLookupZipRef.current = null;
                  } else {
                    setEditingId(null);
                    setZipLookupNote("");
                    setZipPlaces([]);
                  }
                  return next;
                });
              }}
              className="text-sm font-semibold"
              style={{ color: "var(--primary)" }}
            >
              {showNewForm ? "Hide new address form" : "+ Add new address"}
            </button>

            {showNewForm && (
              <form onSubmit={saveNewAddress} className="space-y-3 pt-2" style={{ borderTop: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                    {editingId ? "Edit address" : "New address"}
                  </p>
                  {editingId ? (
                    <button type="button" className="text-xs font-medium" style={{ color: "var(--text-muted)" }} onClick={cancelEdit}>
                      Cancel
                    </button>
                  ) : null}
                </div>
                <input style={inputStyle} placeholder="Label (e.g. Home)" value={label} onChange={(e) => setLabel(e.target.value)} />
                <input style={inputStyle} placeholder="Recipient name (optional)" value={recipientName} onChange={(e) => setRecipientName(e.target.value)} />
                <input style={inputStyle} placeholder="Street line 1" value={line1} onChange={(e) => setLine1(e.target.value)} required />
                <input style={inputStyle} placeholder="Street line 2 (optional)" value={line2} onChange={(e) => setLine2(e.target.value)} />
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>
                    ZIP code (we fill city and state)
                  </label>
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      style={{ ...inputStyle, maxWidth: 120 }}
                      placeholder="ZIP"
                      value={buyerZip}
                      onChange={(e) => setBuyerZip(e.target.value)}
                      onBlur={() => void tryLookupZip()}
                      required
                    />
                    {zipLookupBusy ? (
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>Looking up…</span>
                    ) : null}
                  </div>
                  {zipLookupNote ? (
                    <p className="mt-1.5 text-xs leading-snug" style={{ color: "var(--text-secondary)" }}>{zipLookupNote}</p>
                  ) : null}
                </div>
                {zipPlaces.length > 1 ? (
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>
                      City for this ZIP
                    </label>
                    <select
                      className="w-full rounded-md px-2 py-2 text-sm"
                      style={{ ...inputStyle, cursor: "pointer" }}
                      value={zipPlaces.findIndex((p) => p.city === city && p.state === buyerState) >= 0
                        ? String(zipPlaces.findIndex((p) => p.city === city && p.state === buyerState))
                        : "0"}
                      onChange={(e) => {
                        const p = zipPlaces[Number(e.target.value)];
                        if (p) {
                          setCity(p.city);
                          setBuyerState(p.state);
                        }
                      }}
                    >
                      {zipPlaces.map((p, idx) => (
                        <option key={`${p.city}-${p.state}-${idx}`} value={String(idx)}>
                          {p.city}, {p.state}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}
                <div className="grid grid-cols-2 gap-2">
                  <input
                    style={inputStyle}
                    placeholder="City"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    required
                  />
                  <input
                    style={inputStyle}
                    placeholder="ST"
                    maxLength={2}
                    value={buyerState}
                    onChange={(e) => setBuyerState(e.target.value.toUpperCase())}
                    required
                  />
                </div>
                <button type="submit" disabled={busy} className="btn-forge w-full" style={{ padding: "10px 0", fontSize: 13 }}>
                  {editingId ? "Save changes" : "Save address"}
                </button>
              </form>
            )}

            {addresses.length > 0 && (selectedId || showNewForm) ? (
              <p className="text-xs rounded-lg px-3 py-2" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                <span className="font-semibold" style={{ color: "var(--text-primary)" }}>Using for shipping quote:</span>{" "}
                {selectedId && !showNewForm
                  ? (() => {
                      const a = addresses.find((x) => x.id === selectedId);
                      return a ? `${a.city}, ${a.state} ${a.postal_code}` : "";
                    })()
                  : `${city || "—"}, ${buyerState} ${buyerZip || ""}`.trim()}
                . Continue when ready — you will see the full address on the next step.
              </p>
            ) : null}

            <button
              type="button"
              disabled={busy}
              onClick={() => void goToSummary()}
              className="btn-forge w-full"
              style={{ padding: "12px 0", fontSize: 14, justifyContent: "center" }}
            >
              {busy ? "Calculating…" : "Continue to summary →"}
            </button>
          </div>
        )}

        {step === 2 && preview && (
          <div
            className="space-y-4"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-xl)",
              padding: "20px",
            }}
          >
            {summaryAddress ? (
              <div
                className="rounded-lg p-3 space-y-1"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
              >
                <p className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                  Ship to
                </p>
                {summaryAddress.label ? (
                  <p className="text-sm font-semibold" style={{ fontFamily: "var(--ff-display)", color: "var(--text-primary)" }}>
                    {summaryAddress.label}
                  </p>
                ) : null}
                {summaryAddress.recipient_name ? (
                  <p className="text-sm" style={{ color: "var(--text-primary)" }}>{summaryAddress.recipient_name}</p>
                ) : null}
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-primary)" }}>
                  {summaryAddress.line1 || "(Address on file)"}
                  {summaryAddress.line2 ? (
                    <>
                      <br />
                      {summaryAddress.line2}
                    </>
                  ) : null}
                  <br />
                  {summaryAddress.city}, {summaryAddress.state} {summaryAddress.postal_code}
                </p>
                <p className="text-xs pt-1" style={{ color: "var(--text-muted)" }}>
                  Rates use destination {preview.buyer_state} {preview.buyer_zip}. If anything looks wrong, go back and choose another address or edit it.
                </p>
              </div>
            ) : (
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                Ship to: {preview.buyer_state} {preview.buyer_zip}
              </p>
            )}

            <div className="space-y-2">
              {preview.lines.map((ln) => (
                <div
                  key={ln.cart_item_id}
                  className="rounded-lg px-3 py-2"
                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
                >
                  <p className="text-sm font-semibold" style={{ fontFamily: "var(--ff-display)", color: "var(--text-primary)" }}>
                    {ln.label}
                  </p>
                  <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                    {LABELS[ln.shipping_mode] || ln.shipping_mode} · Qty {ln.quantity}
                  </p>
                  <div className="mt-1 flex justify-between text-xs">
                    <span style={{ color: "var(--text-muted)" }}>Parts</span>
                    <span className="price-mono">${Number(ln.parts_subtotal).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span style={{ color: "var(--text-muted)" }}>Shipping</span>
                    <span className="price-mono">${Number(ln.shipping_quoted_usd).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm mt-1 pt-1" style={{ borderTop: "1px solid var(--border)" }}>
                    <span style={{ fontWeight: 600 }}>Line total</span>
                    <span className="price-mono" style={{ color: "var(--primary-bright)" }}>${Number(ln.line_total_usd).toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="rounded-lg p-3 space-y-1" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
              <div className="flex justify-between text-sm">
                <span style={{ color: "var(--text-muted)" }}>Parts</span>
                <span className="price-mono">${Number(preview.parts_total).toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span style={{ color: "var(--text-muted)" }}>Shipping</span>
                <span className="price-mono">${Number(preview.shipping_total).toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-base font-bold pt-2" style={{ borderTop: "1px solid var(--border)" }}>
                <span style={{ fontFamily: "var(--ff-display)" }}>Total</span>
                <span className="price-mono" style={{ color: "var(--primary-bright)" }}>${Number(preview.grand_total).toFixed(2)}</span>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => { setStep(1); setPreview(null); setSummaryAddress(null); }}
                className="flex-1 rounded-lg py-2.5 text-sm font-semibold"
                style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", color: "var(--text-secondary)" }}
              >
                Back
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void placeOrders()}
                className="btn-forge flex-[2] justify-center py-2.5 text-sm"
              >
                {busy ? "Placing…" : "Place orders"}
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
