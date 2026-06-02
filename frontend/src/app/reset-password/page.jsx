"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

function firstFieldError(val) {
  if (!val) return null;
  return String(Array.isArray(val) ? val[0] : val);
}

function ResetPasswordInner() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useToast();
  const [uid, setUid] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const u = params.get("uid");
    const t = params.get("token");
    if (u) setUid(u);
    if (t) setToken(t);
  }, [params]);

  async function onSubmit(e) {
    e.preventDefault();
    setPending(true);
    try {
      await apiFetch("/auth/password-reset/confirm", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ uid, token, new_password: password }),
      });
      toast.success("Password updated. You can sign in.");
      router.push("/login");
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.body;
        if (typeof d.detail === "string") toast.error(d.detail);
        else if (d.token) toast.error(firstFieldError(d.token) || err.message);
        else if (d.uid) toast.error(firstFieldError(d.uid) || err.message);
        else if (d.new_password) toast.error(firstFieldError(d.new_password) || err.message);
        else toast.error(err.message);
      } else toast.error("Something went wrong.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Choose a new password</h1>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        Use the link from your email — the form is filled from the URL.
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300" htmlFor="password">
            New password
          </label>
          <input
            id="password"
            type="password"
            className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-900"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
        </div>
        <button
          type="submit"
          disabled={pending || !uid || !token}
          className="w-full rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-60"
        >
          {pending ? "Saving…" : "Update password"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-zinc-600 dark:text-zinc-400">
        <Link className="font-medium text-emerald-700 hover:underline dark:text-emerald-400" href="/login">
          Sign in
        </Link>
      </p>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-md px-6 py-16">
          <p className="text-sm text-zinc-500">Loading…</p>
        </div>
      }
    >
      <ResetPasswordInner />
    </Suspense>
  );
}
