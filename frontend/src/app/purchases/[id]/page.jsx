"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { OrderTrackingStepper } from "@/components/OrderTrackingStepper";
import { OrderPayCard } from "@/components/OrderPayCard";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch, apiFetchRaw } from "@/lib/api";

function Stars({ value }) {
  const n = Number(value) || 0;
  const filled = Math.round(n);
  return (
    <span className="text-base" style={{ color: "var(--text-muted)" }}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ color: i < filled ? "#fbbf24" : "var(--border)" }}>★</span>
      ))}
    </span>
  );
}

export default function PurchaseDetailPage() {
  const { id: rawId } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewComment, setReviewComment] = useState("");
  const [reviewBusy, setReviewBusy] = useState(false);

  const id = Number(rawId);

  const load = useCallback(async () => {
    if (!Number.isFinite(id) || id < 1) return;
    const data = await apiFetch(`/orders/${id}/detail/`);
    setOrder(data);
  }, [id]);

  useEffect(() => {
    if (authLoading || !user) return;
    void (async () => {
      setLoading(true);
      try {
        await load();
      } catch (e) {
        if (e instanceof ApiError) {
          toast.error(e.message);
          if (e.status === 403 || e.status === 404) router.replace("/purchases");
        }
        setOrder(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, user, load, router, toast, id]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=%2Fpurchases");
  }, [authLoading, user, router]);

  async function printReceipt() {
    try {
      const res = await apiFetchRaw(`/orders/${order.id}/receipt/`);
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Could not load receipt.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const iframe = document.createElement("iframe");
      iframe.style.position = "fixed";
      iframe.style.right = "0";
      iframe.style.bottom = "0";
      iframe.style.width = "0";
      iframe.style.height = "0";
      iframe.style.border = "0";
      iframe.src = url;
      document.body.appendChild(iframe);
      iframe.onload = () => {
        try {
          iframe.contentWindow?.focus();
          iframe.contentWindow?.print();
        } finally {
          setTimeout(() => {
            document.body.removeChild(iframe);
            URL.revokeObjectURL(url);
          }, 2000);
        }
      };
    } catch (e) {
      toast.error(e?.message || "Could not print receipt.");
    }
  }

  async function submitReview() {
    setReviewBusy(true);
    try {
      await apiFetch(`/orders/${order.id}/seller-review/`, {
        method: "POST",
        body: JSON.stringify({ rating: reviewRating, comment: reviewComment }),
      });
      toast.success("Thanks — your review was saved.");
      await load();
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setReviewBusy(false);
    }
  }

  if (authLoading || !user || loading) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Order not found.</p>
        <Link href="/purchases" className="btn-forge inline-flex mt-4">Back</Link>
      </div>
    );
  }

  if (order.buyer !== user.id) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>This purchase belongs to another account.</p>
        <Link href="/purchases" className="btn-forge inline-flex mt-4">Back</Link>
      </div>
    );
  }

  const delivered = order.state === "delivered";
  const contactHref = `/purchases/${order.id}/issue?type=contact_seller`;
  const inboxHref = `/inbox?part=${order.vehicle_part}&auto=1&msg=${encodeURIComponent(`Regarding order #${order.id}`)}`;

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-12">
      <Link href="/purchases" className="text-sm" style={{ color: "var(--primary)" }}>← Purchases</Link>

      <div
        className="mt-4 rounded-xl p-6 space-y-6"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
      >
        <header>
          <p className="section-label mb-1">Order #{order.id}</p>
          <h1 className="heading-display text-xl mb-1">{order.vehicle_part_label}</h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            {order.vehicle_year} {order.vehicle_make} {order.vehicle_model}
            {order.vehicle_vin ? ` · VIN ${order.vehicle_vin}` : ""}
          </p>
        </header>

        <section className="grid gap-3 sm:grid-cols-2 text-sm" style={{ color: "var(--text-secondary)" }}>
          <div>
            <p className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Time placed</p>
            <p>{order.created_at ? String(order.created_at) : "—"}</p>
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Order number</p>
            <p>#{order.id}</p>
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Total</p>
            <p>${order.amount_usd}</p>
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Sold by</p>
            <p>{order.seller_display_name || "Seller"}</p>
            <div className="flex items-center gap-2 mt-1">
              <Stars value={order.seller_rating_avg} />
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                ({order.seller_rating_count ?? 0} reviews)
              </span>
            </div>
          </div>
        </section>

        <section>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Delivery info</p>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Mode: <strong style={{ color: "var(--text-primary)" }}>{order.shipping_mode || "—"}</strong>
          </p>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            Ship to: <strong style={{ color: "var(--text-primary)" }}>{order.buyer_shipping_summary || "—"}</strong>
          </p>
        </section>

        <section>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Tracking</p>
          <OrderTrackingStepper steps={order.tracking_steps} />
          {order.tracking_number ? (
            <p className="text-sm mt-2" style={{ color: "var(--text-secondary)" }}>
              <strong style={{ color: "var(--text-primary)" }}>Carrier:</strong> {order.tracking_carrier}{" "}
              <strong style={{ color: "var(--text-primary)" }}>Number:</strong> {order.tracking_number}
            </p>
          ) : (
            <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>Tracking will appear when the seller ships.</p>
          )}
        </section>

        <section>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Item</p>
          <p className="text-sm" style={{ color: "var(--text-primary)" }}>{order.vehicle_part_label}</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>Part line subtotal (excl. shipping line): ${order.part_subtotal_usd}</p>
        </section>

        <section>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Seller</p>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{order.seller_display_name}</p>
          {order.seller_email ? (
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>{order.seller_email}</p>
          ) : null}
          <div className="flex flex-wrap gap-2 mt-2">
            <Link href={contactHref} className="btn-ghost inline-flex text-xs py-1.5 px-3" style={{ fontSize: 12 }}>
              Contact seller (admin form)
            </Link>
            <Link href={inboxHref} className="btn-ghost inline-flex text-xs py-1.5 px-3" style={{ fontSize: 12 }}>
              Message inbox
            </Link>
          </div>
        </section>

        <section>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Shipping address (ZIP / state)</p>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{order.buyer_shipping_summary || "—"}</p>
        </section>

        <section>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>Payment</p>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{order.payment_summary}</p>
        </section>

        {Array.isArray(order.delivery_photos) && order.delivery_photos.length > 0 && (
          <section>
            <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
              Delivery photos
            </p>
            <div className="flex flex-wrap gap-2">
              {order.delivery_photos.map((url) => (
                <a key={url} href={url} target="_blank" rel="noreferrer" className="text-xs underline" style={{ color: "var(--primary)" }}>
                  {url.slice(0, 48)}…
                </a>
              ))}
            </div>
            {order.delivery_notes ? (
              <p className="text-sm mt-2" style={{ color: "var(--text-secondary)" }}>{order.delivery_notes}</p>
            ) : null}
          </section>
        )}

        {delivered && (
          <section className="rounded-lg p-4" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
            <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
              Leave a review
            </p>
            {order.my_seller_review ? (
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                You rated this seller {order.my_seller_review.rating}★
                {order.my_seller_review.comment ? ` — “${order.my_seller_review.comment}”` : ""}
              </p>
            ) : (
              <div className="space-y-2">
                <label className="text-xs" style={{ color: "var(--text-muted)" }}>Rating</label>
                <select
                  value={reviewRating}
                  onChange={(e) => setReviewRating(Number(e.target.value))}
                  className="block w-full max-w-xs rounded-md px-2 py-1 text-sm"
                  style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                >
                  {[5, 4, 3, 2, 1].map((r) => (
                    <option key={r} value={r}>{r} stars</option>
                  ))}
                </select>
                <textarea
                  value={reviewComment}
                  onChange={(e) => setReviewComment(e.target.value)}
                  rows={3}
                  placeholder="Optional comment"
                  className="w-full rounded-md px-2 py-2 text-sm"
                  style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                />
                <button type="button" disabled={reviewBusy} className="btn-forge text-sm py-2 px-4" onClick={() => void submitReview()}>
                  {reviewBusy ? "Saving…" : "Submit review"}
                </button>
              </div>
            )}
          </section>
        )}

        {order.state === "payment_pending" && (
          <div className="rounded-lg p-3" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
            <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
              Pay with card
            </p>
            <OrderPayCard order={order} onSuccess={load} />
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Link href={contactHref} className="btn-ghost" style={{ padding: "8px 16px", fontSize: 13 }}>
            Contact seller (form)
          </Link>
          <Link href={inboxHref} className="btn-ghost" style={{ padding: "8px 16px", fontSize: 13 }}>
            Inbox
          </Link>
          <button type="button" className="btn-forge" style={{ padding: "8px 16px", fontSize: 13 }} onClick={() => void printReceipt()}>
            Print receipt (PDF)
          </button>
        </div>
      </div>
    </div>
  );
}
