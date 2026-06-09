"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/context/auth-context";
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

function InboxContent() {
  const router = useRouter();
  const search = useSearchParams();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();

  const [threads, setThreads] = useState([]);
  const [selectedThreadId, setSelectedThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draftBody, setDraftBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [mobileView, setMobileView] = useState("list"); // "list" | "messages"

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=%2Finbox");
  }, [authLoading, user, router]);

  async function loadThreads() {
    const data = await apiFetch("/messages/threads/");
    const list = Array.isArray(data) ? data : [];
    setThreads(list);
    const threadParam = search.get("thread");
    if (threadParam) {
      setSelectedThreadId(Number(threadParam));
      setMobileView("messages");
    } else if (!selectedThreadId && list.length > 0) {
      setSelectedThreadId(list[0].id);
    }
  }

  async function loadMessages(threadId) {
    const data = await apiFetch(`/messages/threads/${threadId}/messages/`);
    setMessages(Array.isArray(data) ? data : []);
    apiFetch(`/messages/threads/${threadId}/mark-read/`, { method: "POST", body: JSON.stringify({}) }).catch(() => {});
  }

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      try {
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
    loadMessages(selectedThreadId).catch(() => {});
    const poll = setInterval(() => {
      if (!cancelled) loadMessages(selectedThreadId).catch(() => {});
    }, 5000);
    return () => { cancelled = true; clearInterval(poll); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, selectedThreadId]);

  function selectThread(id) {
    setSelectedThreadId(id);
    setMobileView("messages");
  }

  async function sendMessage(e) {
    e.preventDefault();
    const body = draftBody.trim();
    if (!selectedThreadId || !body) return;
    setBusy(true);
    try {
      await apiFetch(`/messages/threads/${selectedThreadId}/messages/`, {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      setDraftBody("");
      await loadMessages(selectedThreadId);
      await loadThreads();
    } catch (e2) {
      if (e2 instanceof ApiError) toast.error(e2.message);
    } finally {
      setBusy(false);
    }
  }

  const selectedThread = useMemo(() => threads.find((t) => t.id === selectedThreadId), [threads, selectedThreadId]);

  if (authLoading || !user) {
    return <div className="mx-auto max-w-5xl px-6 py-16"><p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</p></div>;
  }

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-6 sm:py-10">
      {/* Header — hidden on mobile when viewing messages */}
      <div className={`mb-4 sm:mb-6 ${mobileView === "messages" ? "hidden sm:block" : "block"}`}>
        <p className="section-label mb-1">Communication</p>
        <h1 className="heading-display text-2xl">Inbox</h1>
      </div>

      {/* Mobile back bar — only visible on mobile when viewing messages */}
      {mobileView === "messages" && (
        <div className="flex items-center gap-3 mb-4 sm:hidden">
          <button
            type="button"
            onClick={() => setMobileView("list")}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: "var(--bg-elevated)", border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)", padding: "6px 12px",
              fontSize: 13, fontWeight: 600, color: "var(--text-primary)",
              cursor: "pointer",
            }}
          >
            ← Back
          </button>
          <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
            {selectedThread && (
              user.id === selectedThread.buyer ? `Seller #${selectedThread.seller}` : `Buyer #${selectedThread.buyer}`
            )}
          </p>
        </div>
      )}

      {/* Two-column on desktop, single-pane on mobile */}
      <div className="grid grid-cols-1 sm:grid-cols-[280px_1fr] gap-4" style={{ minHeight: 500 }}>

        {/* Thread list */}
        <div
          className={mobileView === "messages" ? "hidden sm:block" : "block"}
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", overflow: "hidden" }}
        >
          {threads.length === 0 ? (
            <div style={{ padding: "24px 16px", textAlign: "center" }}>
              <p style={{ fontSize: 24, marginBottom: 8 }}>💬</p>
              <p style={{ fontSize: 12, color: "var(--text-muted)" }}>No messages yet.</p>
            </div>
          ) : (
            <div>
              {threads.map((t) => {
                const isActive = t.id === selectedThreadId;
                const isBuyer = user.id === t.buyer;
                const otherParty = isBuyer ? `Seller #${t.seller}` : `Buyer #${t.buyer}`;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => selectThread(t.id)}
                    style={{
                      display: "block", width: "100%", textAlign: "left",
                      padding: "14px 16px",
                      background: isActive ? "var(--bg-elevated)" : "transparent",
                      border: "none", borderBottom: "1px solid var(--border)",
                      cursor: "pointer",
                    }}
                  >
                    <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 2 }}>
                      {otherParty}
                      {t.unread_count > 0 && (
                        <span style={{ marginLeft: 6, background: "var(--primary)", color: "#fff", borderRadius: 999, fontSize: 9, padding: "1px 5px", fontWeight: 700 }}>
                          {t.unread_count}
                        </span>
                      )}
                    </p>
                    <p style={{ fontSize: 12, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.last_message?.body || "No messages yet"}
                    </p>
                    {t.last_message_at && (
                      <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                        {new Date(t.last_message_at).toLocaleDateString()}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Message pane */}
        <div
          className={mobileView === "list" ? "hidden sm:flex" : "flex"}
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", flexDirection: "column", overflow: "hidden", minHeight: 480 }}
        >
          {!selectedThreadId ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flex: 1 }}>
              <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Select a conversation.</p>
            </div>
          ) : (
            <>
              {/* Header — hidden on mobile (shown in back bar above instead) */}
              <div className="hidden sm:flex" style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", alignItems: "center", justifyContent: "space-between" }}>
                <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                  {selectedThread && (
                    user.id === selectedThread.buyer ? `Seller #${selectedThread.seller}` : `Buyer #${selectedThread.buyer}`
                  )}
                </p>
                {selectedThread?.item && (
                  <Link href={`/browse/parts/${selectedThread.item}`} style={{ fontSize: 11, color: "var(--primary)", textDecoration: "none" }}>
                    View part →
                  </Link>
                )}
              </div>

              {/* View part link on mobile */}
              {selectedThread?.item && (
                <div className="flex sm:hidden" style={{ padding: "8px 14px", borderBottom: "1px solid var(--border)", justifyContent: "flex-end" }}>
                  <Link href={`/browse/parts/${selectedThread.item}`} style={{ fontSize: 12, color: "var(--primary)", textDecoration: "none" }}>
                    View part →
                  </Link>
                </div>
              )}

              {/* Messages */}
              <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: 10 }}>
                {messages.length === 0 && (
                  <p style={{ color: "var(--text-muted)", fontSize: 12, textAlign: "center" }}>No messages yet.</p>
                )}
                {messages.map((msg) => {
                  const mine = msg.sender === user.id;
                  return (
                    <div key={msg.id} style={{ display: "flex", justifyContent: mine ? "flex-end" : "flex-start" }}>
                      <div
                        style={{
                          maxWidth: "80%", padding: "8px 12px", borderRadius: 12, fontSize: 14, lineHeight: 1.5,
                          background: mine ? "var(--primary)" : "var(--bg-elevated)",
                          color: mine ? "#fff" : "var(--text-primary)",
                          border: mine ? "none" : "1px solid var(--border)",
                        }}
                      >
                        <p>{msg.body}</p>
                        <p style={{ fontSize: 10, marginTop: 4, opacity: 0.6 }}>
                          {new Date(msg.sent_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Compose */}
              <form onSubmit={sendMessage} style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", display: "flex", gap: 8 }}>
                <textarea
                  value={draftBody}
                  onChange={(e) => setDraftBody(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendMessage(e); } }}
                  rows={2}
                  placeholder="Write a message…"
                  disabled={busy}
                  style={{ ...inputStyle, resize: "none", flex: 1 }}
                />
                <button
                  type="submit"
                  disabled={busy || !draftBody.trim()}
                  style={{
                    padding: "8px 16px", fontSize: 13, fontWeight: 700, borderRadius: 8,
                    background: "var(--primary)", color: "#fff", border: "none",
                    cursor: "pointer", opacity: (busy || !draftBody.trim()) ? 0.5 : 1, alignSelf: "flex-end",
                  }}
                >
                  {busy ? "…" : "Send"}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function InboxPage() {
  return (
    <Suspense fallback={<div className="p-10 text-sm" style={{ color: "var(--text-muted)" }}>Loading…</div>}>
      <InboxContent />
    </Suspense>
  );
}
