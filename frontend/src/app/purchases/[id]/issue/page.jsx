"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

const REASONS = [
  { id: "not_as_described", label: "Not as described" },
  { id: "wrong_part", label: "Wrong part received" },
  { id: "not_received", label: "Item not received" },
  { id: "damaged", label: "Arrived damaged" },
  { id: "other", label: "Other" },
];

function MessageBubble({ msg }) {
  const isSupport = msg.sender_role === "support";
  const isSeller = msg.sender_role === "seller";
  const roleLabel = isSupport ? "Support" : isSeller ? "Seller" : "You";
  const roleColor = isSupport ? "var(--primary)" : isSeller ? "#38bdf8" : "var(--text-primary)";

  return (
    <div className={`flex ${msg.sender_role === "buyer" ? "justify-end" : "justify-start"}`}>
      <div
        style={{
          maxWidth: "80%",
          borderRadius: 12,
          padding: "10px 14px",
          background: msg.sender_role === "buyer" ? "var(--primary)" : "var(--bg-elevated)",
          border: "1px solid var(--border)",
        }}
      >
        <p style={{ fontSize: 10, fontWeight: 700, color: msg.sender_role === "buyer" ? "rgba(255,255,255,0.7)" : roleColor, marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {roleLabel}
        </p>
        <p style={{ fontSize: 13, color: msg.sender_role === "buyer" ? "#fff" : "var(--text-primary)", lineHeight: 1.55, whiteSpace: "pre-wrap" }}>
          {msg.body}
        </p>
        <p style={{ fontSize: 10, color: msg.sender_role === "buyer" ? "rgba(255,255,255,0.5)" : "var(--text-muted)", marginTop: 4, textAlign: "right" }}>
          {msg.sent_at ? new Date(msg.sent_at).toLocaleString() : ""}
        </p>
      </div>
    </div>
  );
}

export default function PurchaseIssuePage() {
  const { id: rawId } = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const id = Number(rawId);
  const preselectedItemId = searchParams.get("item");

  const [order, setOrder] = useState(null);
  const [dispute, setDispute] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState("not_as_described");
  const [description, setDescription] = useState("");
  const [selectedItemId, setSelectedItemId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [newMessage, setNewMessage] = useState("");
  const [sendingMessage, setSendingMessage] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace(`/login?next=%2Fpurchases%2F${id}%2Fissue`);
  }, [authLoading, user, router, id]);

  useEffect(() => {
    if (authLoading || !user || !Number.isFinite(id) || id < 1) return;
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const [orderData, disputesData] = await Promise.all([
          apiFetch(`/orders/${id}/`),
          apiFetch("/disputes/"),
        ]);
        if (cancelled) return;

        setOrder(orderData);

        const orderItemIds = new Set((orderData.order_items || []).map((oi) => oi.id));
        const matchingDispute = (Array.isArray(disputesData) ? disputesData : [])
          .find((d) => orderItemIds.has(d.order_item));

        if (matchingDispute) {
          setDispute(matchingDispute);
        } else {
          // Pre-select item if passed in URL
          const pId = preselectedItemId ? Number(preselectedItemId) : null;
          const firstItem = orderData.order_items?.[0];
          setSelectedItemId(
            pId && orderItemIds.has(pId) ? pId : (firstItem?.id || null)
          );
        }
      } catch (e) {
        if (!cancelled && e instanceof ApiError) toast.error(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [authLoading, user, id, preselectedItemId, toast]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [dispute?.messages?.length]);

  async function submitDispute(e) {
    e.preventDefault();
    if (!selectedItemId || !description.trim()) return;
    setSubmitting(true);
    try {
      const d = await apiFetch(`/disputes/order-item/${selectedItemId}/`, {
        method: "POST",
        body: JSON.stringify({ reason, description: description.trim() }),
      });
      setDispute(d);
      toast.success("Dispute opened. Our team will follow up.");
    } catch (err) {
      if (err instanceof ApiError) toast.error(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function sendMessage(e) {
    e.preventDefault();
    if (!newMessage.trim() || !dispute?.id) return;
    setSendingMessage(true);
    try {
      const msg = await apiFetch(`/disputes/${dispute.id}/messages/`, {
        method: "POST",
        body: JSON.stringify({ body: newMessage.trim() }),
      });
      setDispute((prev) => ({
        ...prev,
        messages: [...(prev?.messages || []), msg],
      }));
      setNewMessage("");
    } catch (err) {
      if (err instanceof ApiError) toast.error(err.message);
    } finally {
      setSendingMessage(false);
    }
  }

  if (authLoading || !user || loading) {
    return (
      <div className="mx-auto max-w-lg px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  const statusStyle = {
    open:        { color: "#fbbf24", background: "rgba(251,191,36,0.1)", border: "1px solid rgba(251,191,36,0.3)" },
    under_review:{ color: "#38bdf8", background: "rgba(56,189,248,0.1)", border: "1px solid rgba(56,189,248,0.3)" },
    resolved_refund:      { color: "#4ade80", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.3)" },
    resolved_return:      { color: "#a78bfa", background: "rgba(167,139,250,0.1)", border: "1px solid rgba(167,139,250,0.25)" },
    resolved_no_action:   { color: "var(--text-muted)", background: "var(--bg-elevated)", border: "1px solid var(--border)" },
    closed:               { color: "var(--text-muted)", background: "var(--bg-elevated)", border: "1px solid var(--border)" },
  };

  // Show dispute thread if one exists
  if (dispute) {
    const snap = dispute.item_snapshot || {};
    const dsStyle = statusStyle[dispute.status] || statusStyle.closed;
    return (
      <div className="mx-auto max-w-lg px-4 sm:px-6 py-12 space-y-5">
        <Link href={`/purchases/${id}`} className="text-sm" style={{ color: "var(--primary)" }}>← Order #{id}</Link>

        <div>
          <p className="section-label mb-1">Dispute #{dispute.id}</p>
          <div className="flex items-center gap-3 flex-wrap">
            <span style={{ ...dsStyle, borderRadius: 999, padding: "3px 12px", fontSize: 11, fontWeight: 600, fontFamily: "var(--ff-display)" }}>
              {dispute.status.replace(/_/g, " ")}
            </span>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
              Reason: {REASONS.find((r) => r.id === dispute.reason)?.label || dispute.reason}
            </span>
          </div>
        </div>

        {/* Item snapshot */}
        {snap.title && (
          <div className="rounded-lg px-3 py-2" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
            <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 2 }}>Item in dispute</p>
            <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{snap.title}</p>
            {snap.price && <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
              ${snap.price} · {snap.condition?.replace(/_/g, " ")}
            </p>}
          </div>
        )}

        {/* Original description */}
        {dispute.description && (
          <div className="rounded-lg px-3 py-2" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>Your description</p>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.55 }}>{dispute.description}</p>
          </div>
        )}

        {/* Resolution */}
        {dispute.resolution && (
          <div className="rounded-lg px-3 py-2" style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.25)" }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: "#4ade80", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>Resolution</p>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.55 }}>{dispute.resolution}</p>
            {dispute.refund_amount && (
              <p style={{ fontSize: 12, color: "#4ade80", marginTop: 4, fontWeight: 600 }}>
                Refund: ${dispute.refund_amount}
              </p>
            )}
          </div>
        )}

        {/* Messages */}
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <div style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border)", padding: "8px 14px" }}>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)" }}>
              Messages
            </p>
          </div>
          <div className="space-y-3 p-4" style={{ background: "var(--bg-surface)", minHeight: 120 }}>
            {(dispute.messages || []).length === 0 ? (
              <p style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", padding: "20px 0" }}>
                No messages yet. Add one below.
              </p>
            ) : (
              (dispute.messages || []).map((msg) => (
                <MessageBubble key={msg.id} msg={msg} />
              ))
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Reply (only if not resolved/closed) */}
        {!["resolved_refund", "resolved_return", "resolved_no_action", "closed"].includes(dispute.status) && (
          <form onSubmit={sendMessage} className="space-y-2">
            <textarea
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              rows={3}
              required
              placeholder="Add a message or update…"
              className="w-full rounded-lg px-3 py-2 text-sm"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)", resize: "vertical" }}
              disabled={sendingMessage}
            />
            <button
              type="submit"
              disabled={sendingMessage || !newMessage.trim()}
              className="btn-forge w-full justify-center"
              style={{ padding: "10px 0", fontSize: 13 }}
            >
              {sendingMessage ? "Sending…" : "Send message"}
            </button>
          </form>
        )}
      </div>
    );
  }

  // Show create form
  const orderItems = order?.order_items || [];
  return (
    <div className="mx-auto max-w-lg px-4 sm:px-6 py-12 space-y-5">
      <Link href={`/purchases/${id}`} className="text-sm" style={{ color: "var(--primary)" }}>← Order #{id}</Link>

      <div>
        <p className="section-label mb-1">Open a dispute</p>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Describe the issue and our team will review it. You can exchange messages with the seller throughout the process.
        </p>
      </div>

      <form onSubmit={submitDispute} className="space-y-4">
        {/* Item selection (if multiple items) */}
        {orderItems.length > 1 && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
              Which item?
            </label>
            <div className="space-y-2">
              {orderItems.map((oi) => {
                const title = oi.item_title || oi.item_snapshot?.title || `Item #${oi.item_id}`;
                const selected = selectedItemId === oi.id;
                return (
                  <button
                    key={oi.id}
                    type="button"
                    onClick={() => setSelectedItemId(oi.id)}
                    className="w-full text-left rounded-lg px-3 py-2 text-sm"
                    style={{
                      background: selected ? "rgba(255,92,26,0.08)" : "var(--bg-elevated)",
                      border: selected ? "1px solid rgba(255,92,26,0.35)" : "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                  >
                    {title}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Reason
          </label>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full rounded-lg px-3 py-2 text-sm"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            {REASONS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Description
          </label>
          <textarea
            required
            minLength={10}
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-lg px-3 py-2 text-sm"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)", resize: "vertical" }}
            placeholder="Describe the issue in detail. Include photos of the problem if possible — you can attach them after opening the dispute."
          />
        </div>

        <button
          type="submit"
          disabled={submitting || !description.trim() || !selectedItemId}
          className="btn-forge w-full justify-center"
          style={{ padding: "12px 0", fontSize: 14 }}
        >
          {submitting ? "Opening dispute…" : "Open dispute"}
        </button>
      </form>
    </div>
  );
}
