"use client";

import type { Contact } from "@ama/shared-types";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ClientApiError, apiRequest } from "@/lib/api-client";

export function ContactForm({ contact }: { contact?: Contact }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);

    const form = new FormData(event.currentTarget);
    const tags = String(form.get("tags") ?? "")
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);

    const payload = {
      name: text(form.get("name")),
      phone: text(form.get("phone")),
      email: text(form.get("email")),
      language: text(form.get("language")),
      source: text(form.get("source")),
      tags,
    };

    try {
      if (contact) {
        await apiRequest<Contact>(`/contacts/${contact.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        setSaved(true);
        router.refresh();
      } else {
        const created = await apiRequest<Contact>("/contacts", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        router.push(`/contacts/${created.id}`);
      }
    } catch (cause) {
      setError(cause instanceof ClientApiError ? cause.message : "Could not save this contact.");
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
          Contact saved.
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" name="name" defaultValue={contact?.name ?? ""} />
        <Field label="Phone" name="phone" defaultValue={contact?.phone ?? ""} />
        <Field label="Email" name="email" type="email" defaultValue={contact?.email ?? ""} />
        <Field label="Language" name="language" defaultValue={contact?.language ?? ""} />
        <Field label="Source" name="source" defaultValue={contact?.source ?? ""} />
        <Field
          label="Tags"
          name="tags"
          defaultValue={(contact?.tags ?? []).join(", ")}
          hint="Comma separated."
        />
      </div>

      <p className="text-xs text-slate-500">
        A contact needs a phone number or an email address. Consent is recorded separately.
      </p>

      <button
        type="submit"
        disabled={busy}
        className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-60"
      >
        {busy ? "Saving…" : contact ? "Save changes" : "Create contact"}
      </button>
    </form>
  );
}

function text(value: FormDataEntryValue | null): string | null {
  const trimmed = String(value ?? "").trim();
  return trimmed.length > 0 ? trimmed : null;
}

function Field({
  label,
  name,
  type = "text",
  defaultValue,
  hint,
}: {
  label: string;
  name: string;
  type?: string;
  defaultValue?: string;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        name={name}
        type={type}
        defaultValue={defaultValue}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm placeholder:text-slate-400"
        placeholder={label}
      />
      {hint ? <span className="mt-1 block text-xs text-slate-500">{hint}</span> : null}
    </label>
  );
}
