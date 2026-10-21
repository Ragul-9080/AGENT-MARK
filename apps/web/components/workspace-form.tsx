"use client";

import type { Workspace } from "@ama/shared-types";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ClientApiError, apiRequest } from "@/lib/api-client";

const TIMEZONES = [
  "Asia/Kolkata",
  "Asia/Dubai",
  "Asia/Singapore",
  "Europe/London",
  "America/New_York",
  "America/Los_Angeles",
  "UTC",
];

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "Hindi" },
  { code: "ta", label: "Tamil" },
  { code: "te", label: "Telugu" },
  { code: "bn", label: "Bengali" },
  { code: "mr", label: "Marathi" },
];

type CallingHours = { start?: string; end?: string; timezone?: string };

function callingHours(settings: Record<string, unknown>): CallingHours {
  const value = settings.calling_hours;
  if (value && typeof value === "object") return value as CallingHours;
  return {};
}

export function WorkspaceForm({ workspace }: { workspace: Workspace }) {
  const router = useRouter();
  const hours = callingHours(workspace.settings);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);

    const data = new FormData(event.currentTarget);
    const start = String(data.get("start") ?? "09:00");
    const end = String(data.get("end") ?? "21:00");

    try {
      await apiRequest<Workspace>("/workspace", {
        method: "PATCH",
        body: JSON.stringify({
          name: String(data.get("name") ?? "").trim(),
          timezone: String(data.get("timezone") ?? ""),
          default_language: String(data.get("default_language") ?? ""),
          settings: {
            ...workspace.settings,
            calling_hours: { start, end, timezone: "contact" },
          },
        }),
      });
      setSaved(true);
      router.refresh();
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "Could not save the workspace.");
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
      {saved ? (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 ring-1 ring-emerald-200">
          Workspace settings saved.
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Workspace name</span>
          <input
            name="name"
            required
            maxLength={200}
            defaultValue={workspace.name}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Time zone</span>
          <select
            name="timezone"
            defaultValue={workspace.timezone}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {TIMEZONES.concat(TIMEZONES.includes(workspace.timezone) ? [] : [workspace.timezone]).map(
              (zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ),
            )}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Default language</span>
          <select
            name="default_language"
            defaultValue={workspace.default_language}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {LANGUAGES.concat(
              LANGUAGES.some((item) => item.code === workspace.default_language)
                ? []
                : [{ code: workspace.default_language, label: workspace.default_language }],
            ).map((language) => (
              <option key={language.code} value={language.code}>
                {language.label}
              </option>
            ))}
          </select>
        </label>
        <div className="flex gap-3">
          <label className="block grow">
            <span className="text-sm font-medium text-slate-700">Calling window start</span>
            <input
              name="start"
              type="time"
              defaultValue={hours.start ?? "09:00"}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block grow">
            <span className="text-sm font-medium text-slate-700">End</span>
            <input
              name="end"
              type="time"
              defaultValue={hours.end ?? "21:00"}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>
      </div>

      <p className="text-xs text-slate-500">
        Calls are only placed inside this window in the contact&apos;s local time. The voice worker
        re-checks it before every dial.
      </p>

      <button
        type="submit"
        disabled={busy}
        className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-60"
      >
        {busy ? "Saving…" : "Save settings"}
      </button>
    </form>
  );
}
