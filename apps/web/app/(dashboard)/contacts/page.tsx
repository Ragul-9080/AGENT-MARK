import type { Contact, Page } from "@ama/shared-types";
import Link from "next/link";

import { ContactForm } from "@/components/contact-form";
import { Pagination } from "@/components/pagination";
import { EmptyState, PageHeading, Section } from "@/components/ui";
import { formatDay } from "@/lib/format";
import { serverApi } from "@/lib/server-api";

export const metadata = { title: "Contacts" };

const PAGE_SIZE = 25;

type SearchParams = Record<string, string | string[] | undefined>;

function single(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

export default async function ContactsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const search = single(params.search);
  const tag = single(params.tag);
  const language = single(params.language);
  const source = single(params.source);
  const offset = Math.max(Number.parseInt(single(params.offset) || "0", 10) || 0, 0);

  const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (search) query.set("search", search);
  if (tag) query.set("tag", tag);
  if (language) query.set("language", language);
  if (source) query.set("source", source);

  const page = await serverApi<Page<Contact>>(`/contacts?${query.toString()}`, "/contacts");

  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow="Audience"
        title="Contacts"
        description="Every contact belongs to this workspace. Consent and suppression are recorded per channel."
        action={
          <Link
            href="/contacts/import"
            className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Import CSV
          </Link>
        }
      />

      <Section
        title="Filter"
        description="Search across name, phone and email."
      >
        <form method="get" action="/contacts" className="flex flex-wrap items-end gap-3">
          <label className="block grow">
            <span className="text-xs font-medium text-slate-600">Search</span>
            <input
              name="search"
              defaultValue={search}
              placeholder="Name, phone or email"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Tag</span>
            <input
              name="tag"
              defaultValue={tag}
              className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Language</span>
            <input
              name="language"
              defaultValue={language}
              className="mt-1 w-28 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Source</span>
            <input
              name="source"
              defaultValue={source}
              className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            />
          </label>
          <button
            type="submit"
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Apply
          </button>
          <Link
            href="/contacts"
            className="rounded-lg px-3 py-2 text-sm font-medium text-slate-500 hover:text-slate-800"
          >
            Reset
          </Link>
        </form>
      </Section>

      <Section title="Directory" description={`${page.total} contact${page.total === 1 ? "" : "s"}`}>
        {page.items.length === 0 ? (
          <EmptyState
            title="No contacts yet"
            description="Import a CSV of consenting contacts to get started."
            href="/contacts/import"
            actionLabel="Import contacts"
          />
        ) : (
          <div className="space-y-4">
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Contact</th>
                    <th className="px-3 py-2">Tags</th>
                    <th className="px-3 py-2">Source</th>
                    <th className="px-3 py-2">Added</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {page.items.map((contact) => (
                    <tr key={contact.id} className="hover:bg-slate-50">
                      <td className="px-3 py-2">
                        <Link
                          href={`/contacts/${contact.id}`}
                          className="font-medium text-slate-900 hover:text-indigo-600"
                        >
                          {contact.name ?? contact.email ?? contact.phone ?? "Unnamed"}
                        </Link>
                        <p className="text-xs text-slate-500">
                          {[contact.phone, contact.email].filter(Boolean).join(" · ")}
                        </p>
                      </td>
                      <td className="px-3 py-2">
                        {contact.tags.length > 0 ? (
                          <span className="text-xs text-slate-600">{contact.tags.join(", ")}</span>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500">{contact.source ?? "—"}</td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        {formatDay(contact.created_at)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <Link
                          href={`/contacts/${contact.id}`}
                          className="text-xs font-medium text-indigo-600 hover:text-indigo-500"
                        >
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              basePath="/contacts"
              params={{ search, tag, language, source }}
              total={page.total}
              limit={page.limit}
              offset={page.offset}
            />
          </div>
        )}
      </Section>

      <Section
        title="Add a contact"
        description="Use this for one-off additions. CSV import handles larger lists."
      >
        <ContactForm />
      </Section>
    </div>
  );
}
