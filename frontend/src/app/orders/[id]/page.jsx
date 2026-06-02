"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { OrderTrackingStepper } from "@/components/OrderTrackingStepper";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

function Stars({ value, count }) {
  const n = Number(value) || 0;
  const filled = Math.round(n);
  return (
    <span className="text-sm" style={{ color: "var(--text-muted)" }}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ color: i < filled ? "#fbbf24" : "var(--border)" }}>★</span>
      ))}
      {count > 0 ? <span className="ml-1">({count})</span> : <span className="ml-1">No reviews yet</span>}
    </span>
  );
}

export default function SellerOrderDetailPage() {
  const { id: rawId } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);

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
          if (e.status === 403 || e.status === 404) router.replace("/orders");
        }
        setOrder(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, user, load, router, toast, id]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=%2Forders");
  }, [authLoading, user, router]);

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
        <Link href="/orders" className="btn-forge inline-flex mt-4">Back</Link>
      </div>
    );
  }

  if (order.seller !== user.id) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>This order is not in your sales.</p>
        <Link href="/orders" className="btn-forge inline-flex mt-4">Back</Link>
      </div>
    );
  }

  const payout = order.seller_payout_summary || {};
  const snap = order.vehicle_snapshot || {};

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-12">
      <Link href="/orders" className="text-sm" style={{ color: "var(--primary)" }}>← Sales</Link>
      <div
        className="mt-4 rounded-xl p-6 space-y-5"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
      >
        <div>
          <p className="section-label mb-1">Sale #{order.id}</p>
          <h1 className="heading-display text-xl mb-1">{order.vehicle_part_label}</h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            {order.vehicle_year} {order.vehicle_make} {order.vehicle_model}
            {order.vehicle_vin ? ` · VIN ${order.vehicle_vin}` : ""}
          </p>
          <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
            Placed {order.created_at ? String(order.created_at) : "—"}
          </p>
        </div>

        <div className="rounded-lg p-4" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Earnings snapshot
          </p>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Buyer paid total: <strong style={{ color: "var(--text-primary)" }}>${payout.buyer_paid_total_usd ?? order.amount_usd}</strong>
          </p>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            Shipping collected from buyer: <strong>${payout.shipping_line_usd ?? order.shipping_amount_usd}</strong>
          </p>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            Part subtotal (before label fees): <strong>${payout.part_subtotal_usd ?? "—"}</strong>
          </p>
          {payout.label_cost_usd ? (
            <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
              Label cost: <strong>${payout.label_cost_usd}</strong>
            </p>
          ) : null}
          <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
            Payout timing follows escrow rules until the buyer marks delivery complete in tracking.
          </p>
        </div>

        <div>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Item
          </p>
          <p className="text-sm" style={{ color: "var(--text-primary)" }}>{order.vehicle_part_label}</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>Listing ID #{order.vehicle_part}</p>
        </div>

        <div>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Vehicle (receipt snapshot)
          </p>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {snap.year} {snap.make} {snap.model} {snap.trim ? `· ${snap.trim}` : ""}
          </p>
          {snap.vin ? <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>VIN {snap.vin}</p> : null}
        </div>

        <div>
          <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Your public rating
          </p>
          <Stars value={order.seller_rating_avg} count={order.seller_rating_count} />
        </div>

        <div>
          <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
            Status
          </p>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{order.state?.replace(/_/g, " ")}</p>
        </div>

        <OrderTrackingStepper steps={order.tracking_steps} />

        <div className="text-sm space-y-1" style={{ color: "var(--text-secondary)" }}>
          {order.pickup_scheduled_summary ? (
            <p><strong>Pickup window:</strong> {order.pickup_scheduled_summary}</p>
          ) : order.pickup_scheduled_at ? (
            <p><strong>Pickup:</strong> {String(order.pickup_scheduled_at)}</p>
          ) : null}
          {order.pickup_completed_at ? (
            <p><strong>Pickup completed:</strong> {String(order.pickup_completed_at)}</p>
          ) : null}
          {order.tracking_number ? (
            <p><strong>Tracking:</strong> {order.tracking_carrier} {order.tracking_number}</p>
          ) : null}
        </div>

        <Link href="/orders" className="btn-forge inline-flex" style={{ padding: "8px 18px", fontSize: 13 }}>
          Back to sales list
        </Link>
      </div>
    </div>
  );
}
