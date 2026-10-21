import type { Consent, Contact, Eligibility, EventItem, Page } from "@ama/shared-types";
import Link from "next/link";

import { ConsentControls } from "@/components/consent-controls";
import { ContactForm } from "@/components/contact-form";
import { DeleteContactButton } from "@/components/delete-contact-button";
import { EmptyState, PageHeading, Section } from "@/components/ui";
import { formatDate, titleCase } from "@/lib/format";
import { serverApi } from "@/lib/server-api";

export const metadata = { title: "Contact" };

export default async function ContactDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const base = `/contacts/${id}`;

  const [contact, consents, eligibility, events] = await Promise.all([
    serverApi<Contact>(base, base),
    serverApi<Consent[]>(`${base}/consents`, base),
    serverApi<Eligibility>(`${base}/eligibility`, base),
    serverApi<Page<EventItem>>(`${base}/events?limit=25`, base),
  ]);

  const label = contact.name ?? contact.email ?? contact.phone ?? "this contact";

  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow="Contact"
        title={contact.name ?? "Unnamed contact"}
        description={[contact.phone, contact.email].filter(Boolean).join(" · ") || undefined}
        action={
          <Link
            href="/contacts"
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Back to contacts
          </Link>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section title="Profile" description="Contact details and custom fields.">
            <ContactForm contact={contact} />
            {Object.keys(contact.custom_fields).length > 0 ? (
              <div className="mt-5 border-t border-slate-100 pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Custom fields
                </p>
                <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                  {Object.entries(contact.custom_fields).map(([key, value]) => (
                    <div key={key} className="text-sm">
                      <dt className="text-xs text-slate-500">{key}</dt>
                      <dd className="text-slate-800">{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : null}
          </Section>

          <Section
            title="Consent and channel readiness"
            description="Consent is per channel. A suppression always blocks contact even when consent is granted."
          >
            <ConsentControls
              contactId={contact.id}
              consents={consents}
              eligibility={eligibility}
              phone={contact.phone}
              email={contact.email}
            />
          </Section>

          <Section title="Activity" description={`${events.total} event${events.total === 1 ? "" : "s"} recorded for this contact.`}>
            {events.items.length === 0 ? (
              <EmptyState
                title="No activity yet"
                description="Calls, emails and consent changes appear here as they are recorded."
              />
            ) : (
              <ol className="relative space-y-4 border-l border-slate-200 pl-4">
                {events.items.map((event) => (
                  <li key={event.id} className="relative">
                    <span className="absolute -left-[21px] top-1.5 size-2 rounded-full bg-indigo-500 ring-4 ring-white" />
                    <p className="text-sm font-medium text-slate-900">
                      {titleCase(event.type.replaceAll(".", " "))}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {titleCase(event.source_module)} · {formatDate(event.occurred_at)}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Channel readiness">
            <dl className="space-y-3 text-sm">
              {(["voice", "email"] as const).map((channel) => {
                const state = eligibility[channel];
                return (
                  <div key={channel}>
                    <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      {channel === "voice" ? "Voice" : "Email"}
                    </dt>
                    <dd
                      className={`mt-0.5 font-medium ${state.allowed ? "text-emerald-700" : "text-amber-700"}`}
                    >
                      {state.allowed ? "Ready" : "Blocked"}
                    </dd>
                    <dd className="text-xs text-slate-500">{state.message}</dd>
                  </div>
                );
              })}
            </dl>
          </Section>

          <Section title="Record" description="Workspace-level identifiers.">
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-xs text-slate-500">Contact ID</dt>
                <dd className="break-all font-mono text-xs text-slate-700">{contact.id}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Source</dt>
                <dd className="text-slate-800">{contact.source ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Language</dt>
                <dd className="text-slate-800">{contact.language ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Added</dt>
                <dd className="text-slate-800">{formatDate(contact.created_at)}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Updated</dt>
                <dd className="text-slate-800">{formatDate(contact.updated_at)}</dd>
              </div>
            </dl>
          </Section>

          <Section title="Danger zone" description="Deleting is permanent.">
            <DeleteContactButton contactId={contact.id} label={label} />
          </Section>
        </div>
      </div>
    </div>
  );
}
