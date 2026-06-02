"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

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

function InboxContent() {
  const router = useRouter();
  const search = useSearchParams();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();

  const [threads, setThreads] = useState([]);
  const [selectedThreadId, setSelectedThreadId] = useState(null);
  const [threadDetail, setThreadDetail] = useState(null);
  const [draftBody, setDraftBody] = useState("");
  const [quotePrice, setQuotePrice] = useState("");
  const [quoteNote, setQuoteNote] = useState("");
  const [busy, setBusy] = useState(false);

  const isSellerSide = useMemo(() => {
    if (!threadDetail || !user) return false;
    return user.id === threadDetail.seller_id;
  }, [threadDetail, user]);

  async function loadThreads() {
    const data = await apiFetch("/messages/threads/");
    setThreads(Array.isArray(data) ? data : []);
    if (!selectedThreadId && Array.isArray(data) && data.length > 0) {
      setSelectedThreadId(data[0].id);
    }
  }

  async function loadThreadDetail(threadId) {
    const data = await apiFetch(`/messages/threads/${threadId}/`);
    setThreadDetail(data);
    await apiFetch(`/messages/threads/${threadId}/mark-read/`, { method: "POST", body: JSON.stringify({}) });
  }

  async function maybeStartFromQuery() {
    const part = (search.get("part") || "").trim();
    const parts = (search.get("parts") || "").trim();
    const auto = (search.get("auto") || "").trim() === "1";
    const autoMsg = (search.get("msg") || "").trim();
    if (part) {
      const data = await apiFetch("/messages/start/", {
        method: "POST",
        body: JSON.stringify({ vehicle_part_id: Number(part), message: auto ? autoMsg || "Hi, is this still available?" : "" }),
      });
      setSelectedThreadId(data.id);
      return;
    }
    if (parts) {
      const ids = parts.split(",").map((x) => Number(x.trim())).filter((x) => Number.isFinite(x) && x > 0);
      if (ids.length === 0) return;
      await apiFetch("/messages/bulk-rfq/", {
        method: "POST",
        body: JSON.stringify({ vehicle_part_ids: ids, message: "Hi, I am interested in this part. Please share your best shipped quote." }),
      });
    }
  }

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=%2Finbox");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      try {
        await maybeStartFromQuery();
        if (cancelled) return;
        await loadThreads();
      } catch (e) {
        if (!cancelled && e instanceof ApiError) toast.error(e.message);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, toast]);

  useEffect(() => {
    if (!user || !selectedThreadId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await apiFetch(`/messages/threads/${selectedThreadId}/`);
        if (!cancelled) setThreadDetail(data);
      } catch (e) {
        if (!cancelled && e instanceof ApiError) toast.error(e.message);
      }
    })();
    const poll = setInterval(() => {
      void (async () => {
        try {
          const data = await apiFetch(`/messages/threads/${selectedThreadId}/`);
          if (!cancelled) setThreadDetail(data);
        } catch { /* ignore polling errors */ }
      })();
    }, 5000);
    return () => { cancelled = true; clearInterval(poll); };
  }, [user, selectedThreadId, toast]);

  async function sendMessage(e) {
    e.preventDefault();
    const body = draftBody.trim();
    if (!selectedThreadId || !body) return;
    setBusy(true);
    try {
      await apiFetch(`/messages/threads/${selectedThreadId}/messages/`, { method: "POST", body: JSON.stringify({ body }) });
      setDraftBody("");
      await loadThreadDetail(selectedThreadId);
      await loadThreads();
      toast.success("Message sent.");
    } catch (e2) { if (e2 instanceof ApiError) toast.error(e2.message); }
    finally { setBusy(false); }
  }

  async function sendQuote(e) {
    e.preventDefault();
    if (!selectedThreadId || !quotePrice.trim()) return;
    setBusy(true);
    try {
      await apiFetch(`/messages/threads/${selectedThreadId}/quote/`, {
        method: "POST",
        body: JSON.stringify({ price: quotePrice.trim(), note: quoteNote.trim() }),
      });
      setQuotePrice(""); setQuoteNote("");
      await loadThreadDetail(selectedThreadId);
      await loadThreads();
      toast.success("Quote sent.");
    } catch (e2) { if (e2 instanceof ApiError) toast.error(e2.message); }
    finally { setBusy(false); }
  }

  if (authLoading || !user) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading inbox…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-10">
      <div className="mb-5">
        <p className="section-label mb-1">Messaging</p>
        <h1 className="heading-display text-2xl">Inbox</h1>
      </div>

      <div className="grid gap-3 lg:grid-cols-[300px_1fr]">
        {/* Thread list */}
        <aside style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: 12, height: "fit-content" }}>
          <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 10 }}>
            Conversations
          </p>
          <div className="space-y-1.5">
            {threads.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setSelectedThreadId(t.id)}
                style={{
                  width: "100%", textAlign: "left", padding: "10px 12px",
                  borderRadius: "var(--radius-md)", cursor: "pointer", transition: "all 0.12s",
                  border: selectedThreadId === t.id ? "1px solid rgba(255,92,26,0.4)" : "1px solid transparent",
                  background: selectedThreadId === t.id ? "rgba(255,92,26,0.08)" : "transparent",
                }}
                onMouseEnter={e => { if (selectedThreadId !== t.id) e.currentTarget.style.background = "var(--bg-elevated)"; }}
                onMouseLeave={e => { if (selectedThreadId !== t.id) e.currentTarget.style.background = "transparent"; }}
              >
                <p className="line-clamp-1" style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                  {t.vehicle_part_label || "General inquiry"}
                </p>
                <p className="line-clamp-1" style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                  {t.last_message_preview || "—"}
                </p>
                {t.unread_count > 0 && (
                  <span style={{ display: "inline-flex", marginTop: 4, background: "var(--primary)", color: "#fff", borderRadius: "999px", padding: "1px 8px", fontSize: 10, fontWeight: 700 }}>
                    {t.unread_count} new
                  </span>
                )}
              </button>
            ))}
            {threads.length === 0 && (
              <p style={{ fontSize: 12, color: "var(--text-muted)", padding: "8px 4px" }}>No conversations yet.</p>
            )}
          </div>
        </aside>

        {/* Thread detail */}
        <section style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: 20, minHeight: 400 }}>
          {!threadDetail ? (
            <div className="flex h-full items-center justify-center" style={{ minHeight: 300 }}>
              <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Select a conversation to start messaging.</p>
            </div>
          ) : (
            <>
              <div className="mb-4 pb-4" style={{ borderBottom: "1px solid var(--border)" }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                  {threadDetail.vehicle_part_label || "General inquiry"}
                </h2>
                <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                  {threadDetail.counterparty?.name || threadDetail.counterparty?.email}
                </p>
                {user.id === threadDetail.buyer_id && threadDetail.seller_id && (
                  <p style={{ marginTop: 10 }}>
                    <Link
                      href={`/sellers/${threadDetail.seller_id}`}
                      className="text-sm font-semibold hover:underline"
                      style={{ color: "var(--primary)" }}
                    >
                      View seller profile →
                    </Link>
                  </p>
                )}
              </div>

              {/* Quotes — informational; Buy Now is on the listing */}
              {Array.isArray(threadDetail.quotes) && threadDetail.quotes.length > 0 && (
                <div className="mb-4 p-3" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }}>
                  <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 10 }}>
                    Quotes
                  </p>
                  {user.id === threadDetail.buyer_id && (
                    <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 10, lineHeight: 1.45 }}>
                      When the seller sends a price, it becomes the listing&apos;s Buy Now price for a limited time (about 48 hours). Open the vehicle listing to purchase — chat is only for messaging.
                    </p>
                  )}
                  <div className="space-y-2">
                    {threadDetail.quotes.map((q) => (
                      <div key={q.id} style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "10px 14px" }}>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="price-mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--primary-bright)" }}>{formatMoney(q.price)}</span>
                          {q.note && <span style={{ fontSize: 13, color: "var(--text-muted)" }}>{q.note}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                  {user.id === threadDetail.buyer_id && threadDetail.vehicle_id && (
                    <Link
                      href={`/browse/vehicles/${threadDetail.vehicle_id}`}
                      className="btn-forge mt-3 inline-flex"
                      style={{ padding: "8px 16px", fontSize: 13 }}
                    >
                      View listing & buy
                    </Link>
                  )}
                </div>
              )}

              {/* Messages */}
              <div className="mb-3 space-y-2 overflow-auto p-3" style={{ maxHeight: 400, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }}>
                {(threadDetail.messages || []).map((m) => {
                  const mine = m.sender?.id === user.id;
                  return (
                    <div
                      key={m.id}
                      style={{
                        maxWidth: "80%",
                        marginLeft: mine ? "auto" : 0,
                        borderRadius: "var(--radius-lg)",
                        padding: "8px 12px",
                        background: mine ? "var(--primary)" : "var(--bg-surface)",
                        border: mine ? "none" : "1px solid var(--border)",
                      }}
                    >
                      <p style={{ fontSize: 13, color: mine ? "#fff" : "var(--text-primary)" }}>{m.body}</p>
                      <p style={{ fontSize: 10, marginTop: 3, color: mine ? "rgba(255,255,255,0.6)" : "var(--text-muted)" }}>
                        {m.sender?.name || "User"} · {new Date(m.created_at).toLocaleString()}
                      </p>
                    </div>
                  );
                })}
                {(!threadDetail.messages || threadDetail.messages.length === 0) && (
                  <p style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", padding: "16px 0" }}>
                    No messages yet. Say hello!
                  </p>
                )}
              </div>

              {/* Send message */}
              <form onSubmit={sendMessage} className="flex gap-2">
                <input
                  value={draftBody}
                  onChange={(e) => setDraftBody(e.target.value)}
                  placeholder="Type a message…"
                  style={inputStyle}
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="btn-forge"
                  style={{ padding: "8px 18px", fontSize: 13, whiteSpace: "nowrap", opacity: busy ? 0.6 : 1 }}
                >
                  Send
                </button>
              </form>

              {/* Seller quote form */}
              {isSellerSide && (
                <form onSubmit={sendQuote} className="mt-3 p-3" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }}>
                  <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 8 }}>
                    Send a quote
                  </p>
                  <div className="flex gap-2">
                    <input
                      value={quotePrice}
                      onChange={(e) => setQuotePrice(e.target.value)}
                      placeholder="Price (USD)"
                      style={{ ...inputStyle, width: 140 }}
                    />
                    <input
                      value={quoteNote}
                      onChange={(e) => setQuoteNote(e.target.value)}
                      placeholder="Optional note"
                      style={inputStyle}
                    />
                    <button
                      type="submit"
                      disabled={busy}
                      style={{
                        borderRadius: "var(--radius-md)", padding: "8px 16px",
                        fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)",
                        background: "var(--bg-surface)", border: "1px solid var(--border)",
                        color: "var(--text-secondary)", cursor: "pointer", whiteSpace: "nowrap",
                        opacity: busy ? 0.5 : 1,
                      }}
                    >
                      Send quote
                    </button>
                  </div>
                </form>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

export default function InboxPage() {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-6xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading inbox…</p>
      </div>
    }>
      <InboxContent />
    </Suspense>
  );
}
