"use client";

import type { ImportResult } from "@ama/shared-types";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { ClientApiError, apiRequest } from "@/lib/api-client";
import { statusClass, titleCase } from "@/lib/format";

export function ImportPanel() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"preview" | "commit" | null>(null);

  async function run(dryRun: boolean) {
    if (!file) {
      setError("Choose a CSV file first.");
      return;
    }

    setBusy(dryRun ? "preview" : "commit");
    setError(null);

    const body = new FormData();
    body.append("file", file);

    try {
      const result = await apiRequest<ImportResult>(`/contacts/import?dry_run=${dryRun}`, {
        method: "POST",
        body,
      });
      setPreview(result);
      if (!dryRun) {
        setFile(null);
        if (inputRef.current) inputRef.current.value = "";
        router.refresh();
      }
    } catch (cause) {
      setError(
        cause instanceof ClientApiError ? cause.message : "The import failed. Try again.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">CSV file</span>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setPreview(null);
              setError(null);
            }}
            className="mt-1 block w-full cursor-pointer rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white"
          />
        </label>
        <button
          type="button"
          onClick={() => run(true)}
          disabled={busy !== null || !file}
          className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {busy === "preview" ? "Checking…" : "Preview"}
        </button>
        <button
          type="button"
          onClick={() => run(false)}
          disabled={busy !== null || !file || preview?.dry_run !== true || preview.valid_rows === 0}
          className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {busy === "commit" ? "Importing…" : "Import valid rows"}
        </button>
      </div>

      {error ? (
        <p
          role="alert"
          className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200"
        >
          {error}
        </p>
      ) : null}

      {preview ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-4">
            <Tally label="Rows read" value={preview.total_rows} />
            <Tally label="Ready to import" value={preview.valid_rows} tone="good" />
            <Tally label="Duplicates skipped" value={preview.duplicate_rows} />
            <Tally label="Invalid rows" value={preview.invalid_rows} tone="bad" />
          </div>

          <p className="text-sm text-slate-600">
            {preview.dry_run
              ? "This is a dry run. Nothing was written. Import to create the valid rows."
              : `Imported ${preview.created} contact${preview.created === 1 ? "" : "s"}.`}
          </p>

          {preview.preview.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Row</th>
                    <th className="px-3 py-2">Name</th>
                    <th className="px-3 py-2">Phone</th>
                    <th className="px-3 py-2">Email</th>
                    <th className="px-3 py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {preview.preview.map((row) => (
                    <tr key={row.row}>
                      <td className="px-3 py-2 text-slate-500">{row.row}</td>
                      <td className="px-3 py-2 text-slate-800">{row.name ?? "—"}</td>
                      <td className="px-3 py-2 text-slate-600">{row.phone ?? "—"}</td>
                      <td className="px-3 py-2 text-slate-600">{row.email ?? "—"}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${statusClass(row.status)}`}
                        >
                          {titleCase(row.status)}
                        </span>
                        {row.message ? (
                          <span className="ml-2 text-xs text-slate-500">{row.message}</span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {preview.truncated ? (
            <p className="text-xs text-slate-500">
              The preview shows the first {preview.preview.length} rows only.
            </p>
          ) : null}

          {preview.errors.length > 0 ? (
            <details className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <summary className="cursor-pointer text-sm font-medium text-slate-700">
                {preview.errors.length} row issue{preview.errors.length === 1 ? "" : "s"}
              </summary>
              <ul className="mt-3 max-h-64 space-y-1 overflow-y-auto text-xs text-slate-600">
                {preview.errors.map((item, index) => (
                  <li key={`${item.row}-${item.code}-${index}`}>
                    <span className="font-medium text-slate-800">Row {item.row}</span>
                    {item.field ? ` · ${item.field}` : ""} · {item.message}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Tally({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "good" | "bad";
}) {
  const color =
    tone === "good" ? "text-emerald-700" : tone === "bad" ? "text-rose-700" : "text-slate-900";
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${color}`}>{value}</p>
    </div>
  );
}
