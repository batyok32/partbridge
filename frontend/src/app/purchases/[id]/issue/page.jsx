"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

const TOPICS = [
  { id: "contact_seller", label: "Contact seller" },
  { id: "return_item", label: "Return this item" },
  { id: "item_not_received", label: "I didn’t receive it" },
  { id: "cancel_order", label: "Cancel this order" },
];

export default function PurchaseIssuePage() {
  const { id: rawId } = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const id = Number(rawId);
  const initialTopic = searchParams.get("type") || "contact_seller";

  const [topic, setTopic] = useState(TOPICS.some((t) => t.id === initialTopic) ? initialTopic : "contact_seller");
  const [message, setMessage] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const t = searchParams.get("type");
    if (t && TOPICS.some((x) => x.id === t)) setTopic(t);
  }, [searchParams]);

  useEffect(() => {
    if (!authLoading && !user) router.replace(`/login?next=%2Fpurchases%2F${id}%2Fissue`);
  }, [authLoading, user, router, id]);

  async function submit(e) {
    e.preventDefault();
    if (!Number.isFinite(id) || id < 1) return;
    setSubmitting(true);
    try {
      await apiFetch(`/orders/${id}/buyer-inquiry/`, {
        method: "POST",
        body: JSON.stringify({ topic, message, phone }),
      });
      toast.success("Submitted. Our team will follow up by email.");
      router.replace(`/purchases/${id}`);
    } catch (err) {
      if (err instanceof ApiError) toast.error(err.message);
    } finally {
      setSubmitting(false);
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
      <Link href={`/purchases/${id}`} className="text-sm" style={{ color: "var(--primary)" }}>← Order</Link>
      <h1 className="heading-display text-xl mt-4 mb-2">Request help</h1>
      <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
        Describe the issue. An administrator receives this message by email.
      </p>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Topic
          </label>
          <select
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="w-full rounded-lg px-3 py-2 text-sm"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            {TOPICS.map((t) => (
              <option key={t.id} value={t.id}>{t.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Details (min 10 characters)
          </label>
          <textarea
            required
            minLength={10}
            rows={6}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="w-full rounded-lg px-3 py-2 text-sm"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            placeholder="Include order context, dates, and what you need."
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Phone (optional)
          </label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full rounded-lg px-3 py-2 text-sm"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
        </div>
        <button type="submit" disabled={submitting} className="btn-forge w-full justify-center">
          {submitting ? "Sending…" : "Submit to admin"}
        </button>
      </form>
    </div>
  );
}
