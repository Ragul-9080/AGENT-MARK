"use client";

import type { Campaign, CampaignStatus } from "@ama/shared-types";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ClientApiError, apiRequest } from "@/lib/api-client";

type Action = "start" | "pause" | "resume" | "stop" | "delete";

const LABELS: Record<Action, string> = {
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  stop: "Stop",
  delete: "Delete",
};

function actionsFor(status: CampaignStatus): Action[] {
  switch (status) {
    case "draft":
      return ["start", "stop", "delete"];
    case "scheduled":
      return ["start", "stop", "delete"];
    case "running":
      return ["pause", "stop"];
    case "paused":
      return ["resume", "stop", "delete"];
    case "completed":
      return ["delete"];
    case "failed":
      return ["delete"];
    default:
      return [];
  }
}

export function CampaignActions({ campaign }: { campaign: Campaign }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Action | null>(null);

  async function run(action: Action) {
    if (action === "delete" && !window.confirm("Delete this campaign? This cannot be undone.")) {
      return;
    }

    setBusy(action);
    setError(null);
    try {
      if (action === "delete") {
        await apiRequest(`/campaigns/${campaign.id}`, { method: "DELETE" });
        router.push("/campaigns");
        router.refresh();
        return;
      }
      const updated = await apiRequest<Campaign>(`/campaigns/${campaign.id}/${action}`, {
        method: "POST",
      });
      if (action === "start" && updated.status === "scheduled") {
        setError("Scheduled for later. It starts automatically at that time.");
      }
      router.refresh();
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "That action did not work.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {actionsFor(campaign.status).map((action) => (
          <button
            key={action}
            type="button"
            onClick={() => void run(action)}
            disabled={busy !== null}
            className={
              action === "delete"
                ? "rounded-lg border border-rose-200 px-3 py-1.5 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                : "rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            }
          >
            {busy === action ? "Working…" : LABELS[action]}
          </button>
        ))}
      </div>
      {error ? (
        <p
          role="status"
          className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-amber-200"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}
