"use client";

import type { Campaign, CampaignType } from "@ama/shared-types";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ClientApiError, apiRequest } from "@/lib/api-client";

export function CampaignForm() {
  const router = useRouter();
  const [type, setType] = useState<CampaignType>("voice");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    const data = new FormData(event.currentTarget);
    const scheduledRaw = String(data.get("scheduled_at") ?? "").trim();
    const note = String(data.get("note") ?? "").trim();

    const settings: Record<string, unknown> = {};
    if (type === "email" && note) settings.subject = note;
    if (type === "voice" && note) settings.objective = note;

    const payload: Record<string, unknown> = {
      type,
      name: String(data.get("name") ?? "").trim(),
      settings,
    };
    if (scheduledRaw) {
      const scheduled = new Date(scheduledRaw);
      if (Number.isNaN(scheduled.getTime())) {
        setError("That schedule date is not valid.");
        setBusy(false);
        return;
      }
      payload.scheduled_at = scheduled.toISOString();
    }

    try {
      const created = await apiRequest<Campaign>("/campaigns", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      router.push(`/campaigns/${created.id}`);
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "Could not create the campaign.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {error ? (
        <p
          role="alert"
          className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200"
        >
          {error}
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Type</span>
          <select
            name="type"
            value={type}
            onChange={(event) => setType(event.target.value as CampaignType)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="voice">Voice calls</option>
            <option value="email">Email</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Name</span>
          <input
            name="name"
            required
            maxLength={200}
            placeholder="March renewal reminder"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Schedule (optional)</span>
          <input
            name="scheduled_at"
            type="datetime-local"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <span className="mt-1 block text-xs text-slate-500">
            Local time. Leave empty to start manually.
          </span>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">
            {type === "email" ? "Subject line" : "Call objective"}
          </span>
          <input
            name="note"
            placeholder={type === "email" ? "Your renewal is due" : "Confirm renewal date"}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <span className="mt-1 block text-xs text-slate-500">
            Stored in campaign settings for the agent to pick up.
          </span>
        </label>
      </div>

      <button
        type="submit"
        disabled={busy}
        className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-60"
      >
        {busy ? "Creating…" : "Create campaign"}
      </button>
    </form>
  );
}
