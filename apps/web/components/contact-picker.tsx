"use client";

import type { CampaignAddContactsResult, Contact, Page } from "@ama/shared-types";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ClientApiError, apiRequest } from "@/lib/api-client";

export function ContactPicker({
  campaignId,
  initialContacts,
}: {
  campaignId: string;
  initialContacts: Contact[];
}) {
  const router = useRouter();
  const [term, setTerm] = useState("");
  const [contacts, setContacts] = useState<Contact[]>(initialContacts);
  const [searched, setSearched] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function search() {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const params = new URLSearchParams({ limit: "25", offset: "0" });
      if (term.trim()) params.set("search", term.trim());
      const page = await apiRequest<Page<Contact>>(`/contacts?${params.toString()}`);
      setContacts(page.items);
      setSearched(true);
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "Could not load contacts.");
    } finally {
      setLoading(false);
    }
  }

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function addSelected() {
    if (selected.size === 0) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiRequest<CampaignAddContactsResult>(
        `/campaigns/${campaignId}/contacts`,
        { method: "POST", body: JSON.stringify({ contact_ids: [...selected] }) },
      );
      setSelected(new Set());
      setNotice(
        `Added ${result.added}, skipped ${result.skipped} already in the campaign, ${result.missing} not found.`,
      );
      router.refresh();
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "Could not add recipients.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void search();
        }}
      >
        <label className="block grow">
          <span className="text-xs font-medium text-slate-600">Find contacts</span>
          <input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Name, phone or email"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          />
        </label>
        <button
          type="submit"
          className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Search
        </button>
        <button
          type="button"
          onClick={() => void addSelected()}
          disabled={busy || selected.size === 0}
          className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {busy ? "Adding…" : `Add ${selected.size || ""} selected`.trim()}
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

      {loading ? (
        <p className="text-sm text-slate-500">Loading contacts…</p>
      ) : contacts.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
          {searched ? "No contacts matched that search." : "No contacts in this workspace yet."}
        </p>
      ) : (
        <ul className="max-h-72 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200">
          {contacts.map((contact) => (
            <li key={contact.id}>
              <label className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-slate-50">
                <input
                  type="checkbox"
                  checked={selected.has(contact.id)}
                  onChange={() => toggle(contact.id)}
                  className="size-4 rounded border-slate-300"
                />
                <span className="text-sm text-slate-800">{contact.name ?? "Unnamed contact"}</span>
                <span className="text-xs text-slate-500">
                  {[contact.phone, contact.email].filter(Boolean).join(" · ")}
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-slate-500">
        Showing up to 25 contacts. Recipients are only added while a campaign is a draft or paused.
        Consent and suppression are checked again when the campaign runs.
      </p>
    </div>
  );
}
