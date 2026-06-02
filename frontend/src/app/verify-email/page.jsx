"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

function VerifyEmailInner() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useToast();
  const qpEmail = params.get("email") ?? "";
  const qpToken = params.get("token");

  const [email, setEmail] = useState(qpEmail);
  const [code, setCode] = useState("");
  const [pending, setPending] = useState(false);
  const [autoTried, setAutoTried] = useState(false);

  useEffect(() => {
    if (qpEmail) setEmail(qpEmail);
  }, [qpEmail]);

  useEffect(() => {
    if (!qpToken || autoTried) return;
    setAutoTried(true);
    setPending(true);
    apiFetch("/auth/verify-email", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ token: qpToken }),
    })
      .then(() => {
        toast.success(
          <span>
            Email verified. You can{" "}
            <Link className="font-medium underline" href="/login">sign in</Link>.
          </span>
        );
        router.replace("/verify-email");
      })
      .catch((err) => {
        if (err instanceof ApiError) {
          toast.error(typeof err.body.detail === "string" ? err.body.detail : err.message);
        } else toast.error("Verification failed.");
      })
      .finally(() => setPending(false));
  }, [qpToken, autoTried, router, toast]);

  async function onSubmit(e) {
    e.preventDefault();
    setPending(true);
    try {
      await apiFetch("/auth/verify-email", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email, code }),
      });
      toast.success(
        <span>
          Email verified. You can{" "}
          <Link className="font-medium underline" href="/login">sign in</Link>.
        </span>
      );
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(typeof err.body.detail === "string" ? err.body.detail : err.message);
      } else toast.error("Verification failed.");
    } finally {
      setPending(false);
    }
  }

  async function resend() {
    setPending(true);
    try {
      await apiFetch("/auth/resend-verification", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email }),
      });
      toast.success("If an account exists for this email, a new code was sent.");
    } catch {
      toast.success("If an account exists for this email, a new code was sent.");
    } finally {
      setPending(false);
    }
  }

  if (qpToken && pending) {
    return (
      <div className="mx-auto max-w-md px-6 py-16">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Confirming your email…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Verify your email</h1>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        Enter the six-digit code from your email, or open the link we sent you.
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-900"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300" htmlFor="code">
            Verification code
          </label>
          <input
            id="code"
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm tracking-widest dark:border-zinc-600 dark:bg-zinc-900"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            required
            placeholder="000000"
          />
        </div>
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-60"
        >
          {pending ? "Checking…" : "Verify"}
        </button>
      </form>
      <button
        type="button"
        onClick={() => void resend()}
        disabled={pending || !email}
        className="mt-4 w-full rounded-lg border border-zinc-300 py-2.5 text-sm font-medium text-zinc-800 transition hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-600 dark:text-zinc-100 dark:hover:bg-zinc-900"
      >
        Resend code
      </button>
      <p className="mt-8 text-center text-sm text-zinc-600 dark:text-zinc-400">
        <Link className="font-medium text-emerald-700 hover:underline dark:text-emerald-400" href="/login">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-md px-6 py-16">
          <p className="text-sm text-zinc-500">Loading…</p>
        </div>
      }
    >
      <VerifyEmailInner />
    </Suspense>
  );
}
