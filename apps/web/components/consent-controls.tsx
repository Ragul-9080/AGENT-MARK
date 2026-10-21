"use client";

import type {
  Consent,
  ConsentChannel,
  ConsentStatus,
  Eligibility,
  SuppressionReason,
} from "@ama/shared-types";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ClientApiError, apiRequest } from "@/lib/api-client";
import { Badge } from "@/components/ui";

export function ConsentControls({
  contactId,
  consents,
  eligibility,
  phone,
  email,
}: {
  contactId: string;
  consents: Consent[];
  eligibility: Eligibility;
  phone: string | null;
  email: string | null;
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const channels: { channel: ConsentChannel; label: string; value: string | null }[] = [
    { channel: "voice", label: "Voice calls", value: phone },
    { channel: "email", label: "Email", value: email },
  ];

  function consentFor(channel: ConsentChannel): Consent | undefined {
    return consents.find((item) => item.channel === channel);
  }

  async function saveConsent(channel: ConsentChannel, form: HTMLFormElement) {
    const data = new FormData(form);
    setBusy(`consent-${channel}`);
    setError(null);
    try {
      await apiRequest<Consent>(`/contacts/${contactId}/consents/${channel}`, {
        method: "PUT",
        body: JSON.stringify({
          status: String(data.get("status") ?? "granted") as ConsentStatus,
          proof: String(data.get("proof") ?? "").trim() || null,
        }),
      });
      router.refresh();
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "Could not record consent.");
    } finally {
      setBusy(null);
    }
  }

  async function suppress(channel: ConsentChannel) {
    const value = channel === "voice" ? phone : email;
    const reason: SuppressionReason = channel === "voice" ? "dnd" : "unsubscribe";
    if (!value) return;

    setBusy(`suppress-${channel}`);
    setError(null);
    try {
      await apiRequest("/suppressions", {
        method: "POST",
        body: JSON.stringify({ channel, value, reason }),
      });
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof ClientApiError ? cause.message : "Could not add the suppression.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-5">
      {error ? (
        <p
          role="alert"
          className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200"
        >
          {error}
        </p>
      ) : null}

      {channels.map(({ channel, label, value }) => {
        const consent = consentFor(channel);
        const state = eligibility[channel];
        return (
          <div key={channel} className="rounded-lg border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-slate-900">{label}</p>
                {consent ? <Badge status={consent.status} /> : <Badge status="pending" />}
              </div>
              <p
                className={`text-xs font-medium ${state.allowed ? "text-emerald-700" : "text-amber-700"}`}
              >
                {state.message}
              </p>
            </div>

            <p className="mt-1 text-xs text-slate-500">
              {value ? `On file: ${value}` : `No ${channel === "voice" ? "phone number" : "email"} on this contact.`}
            </p>

            <form
              className="mt-3 flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                void saveConsent(channel, event.currentTarget);
              }}
            >
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Status</span>
                <select
                  name="status"
                  defaultValue={consent?.status ?? "granted"}
                  className="mt-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm"
                >
                  <option value="granted">Granted</option>
                  <option value="revoked">Revoked</option>
                </select>
              </label>
              <label className="block grow">
                <span className="text-xs font-medium text-slate-600">Proof reference</span>
                <input
                  name="proof"
                  defaultValue={consent?.proof ?? ""}
                  placeholder="Form URL, signup page, call ID…"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                />
              </label>
              <button
                type="submit"
                disabled={busy !== null}
                className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
              >
                {busy === `consent-${channel}` ? "Saving…" : "Record consent"}
              </button>
              <button
                type="button"
                onClick={() => void suppress(channel)}
                disabled={busy !== null || !value}
                className="rounded-lg border border-rose-200 px-3 py-1.5 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
              >
                {busy === `suppress-${channel}` ? "Adding…" : "Add to suppression list"}
              </button>
            </form>

            {consent ? (
              <p className="mt-2 text-xs text-slate-500">
                Last recorded {new Date(consent.recorded_at).toLocaleString("en-IN", {
                  timeZone: "Asia/Kolkata",
                })}
              </p>
            ) : null}
          </div>
        );
      })}

      <p className="text-xs text-slate-500">
        Consent is checked before every call and every send. A suppression entry always wins over
        a granted consent.
      </p>
    </div>
  );
}
