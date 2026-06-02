"use client";

import Link from "next/link";
import { useState } from "react";

import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

export default function ForgotPasswordPage() {
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setPending(true);
    try {
      await apiFetch("/auth/password-reset", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email }),
      });
      toast.success("If an account exists for that email, we sent reset instructions.");
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(typeof err.body.detail === "string" ? err.body.detail : err.message);
      } else toast.error("Something went wrong.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Reset password</h1>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        We will email you a link to choose a new password.
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
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-60"
        >
          {pending ? "Sending…" : "Send reset link"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-zinc-600 dark:text-zinc-400">
        <Link className="font-medium text-emerald-700 hover:underline dark:text-emerald-400" href="/login">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}
