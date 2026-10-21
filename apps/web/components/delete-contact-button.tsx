"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ClientApiError, apiRequest } from "@/lib/api-client";

export function DeleteContactButton({ contactId, label }: { contactId: string; label: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    if (
      !window.confirm(
        `Delete ${label}? Consent records, campaign recipients and events for this contact are removed too.`,
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiRequest(`/contacts/${contactId}`, { method: "DELETE" });
      router.push("/contacts");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "Could not delete the contact.");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => void remove()}
        disabled={busy}
        className="rounded-lg border border-rose-200 px-3.5 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
      >
        {busy ? "Deleting…" : "Delete contact"}
      </button>
      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
    </div>
  );
}
