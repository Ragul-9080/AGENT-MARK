"use client";

import type { ConsentChannel, Suppression, SuppressionReason } from "@ama/shared-types";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ClientApiError, apiRequest } from "@/lib/api-client";
import { formatDate, titleCase } from "@/lib/format";

const REASONS: SuppressionReason[] = ["dnd", "unsubscribe", "bounce", "complaint", "manual"];

export function SuppressionPanel({ suppressions }: { suppressions: Suppression[] }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await apiRequest<Suppression>("/suppressions", {
        method: "POST",
        body: JSON.stringify({
          channel: String(data.get("channel") ?? "voice") as ConsentChannel,
          value: String(data.get("value") ?? "").trim(),
          reason: String(data.get("reason") ?? "manual") as SuppressionReason,
        }),
      });
      form.reset();
      setNotice("Added to the suppression list. This contact will not be contacted on that channel.");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "Could not add the entry.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await apiRequest(`/suppressions/${id}`, { method: "DELETE" });
      router.refresh();
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "Could not remove the entry.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
        <label className="block">
          <span className="text-xs font-medium text-slate-600">Channel</span>
          <select
            name="channel"
            className="mt-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm"
          >
            <option value="voice">Voice</option>
            <option value="email">Email</option>
          </select>
        </label>
        <label className="block grow">
          <span className="text-xs font-medium text-slate-600">Phone or email</span>
          <input
            name="value"
            required
            placeholder="+919876543210 or name@example.com"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-600">Reason</span>
          <select
            name="reason"
            className="mt-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm"
          >
            {REASONS.map((reason) => (
              <option key={reason} value={reason}>
                {titleCase(reason)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          Add entry
        </button>
      </form>

      {error ? (
        <p
          role="alert"
          className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200"
        >
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 ring-1 ring-emerald-200">
          {notice}
        </p>
      ) : null}

      {suppressions.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
          No suppressions yet.
        </p>
      ) : (
        <div className="divide-y divide-slate-100">
          {suppressions.map((item) => (
            <div key={item.id} className="flex items-center justify-between gap-3 py-2">
              <div>
                <p className="text-sm font-medium text-slate-800">{item.value}</p>
                <p className="text-xs text-slate-500">
                  {titleCase(item.channel)} · {titleCase(item.reason)} · {formatDate(item.created_at)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void remove(item.id)}
                disabled={busy}
                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
