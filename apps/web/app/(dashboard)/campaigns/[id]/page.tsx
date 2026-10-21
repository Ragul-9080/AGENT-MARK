import type {
  Campaign,
  CampaignContact,
  Contact,
  EventItem,
  Page,
} from "@ama/shared-types";
import Link from "next/link";

import { CampaignActions } from "@/components/campaign-actions";
import { ContactPicker } from "@/components/contact-picker";
import { Pagination } from "@/components/pagination";
import { Badge, EmptyState, PageHeading, Section, StatCard } from "@/components/ui";
import { formatDate, titleCase } from "@/lib/format";
import { serverApi } from "@/lib/server-api";

export const metadata = { title: "Campaign" };

const PAGE_SIZE = 25;

type SearchParams = Record<string, string | string[] | undefined>;

function single(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

export default async function CampaignDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  const offset = Math.max(Number.parseInt(single(query.offset) || "0", 10) || 0, 0);
  const base = `/campaigns/${id}`;

  const [campaign, recipients, events, contacts] = await Promise.all([
    serverApi<Campaign>(base, base),
    serverApi<Page<CampaignContact>>(
      `${base}/contacts?limit=${PAGE_SIZE}&offset=${offset}`,
      base,
    ),
    serverApi<Page<EventItem>>("/events?limit=200", base),
    serverApi<Page<Contact>>("/contacts?limit=25&offset=0", base),
  ]);

  const campaignEvents = events.items.filter(
    (event) => event.payload?.campaign_id === campaign.id,
  );

  const editable = campaign.status === "draft" || campaign.status === "paused";

  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow={`${titleCase(campaign.type)} campaign`}
        title={campaign.name}
        description={`Created ${formatDate(campaign.created_at)}. Last updated ${formatDate(campaign.updated_at)}.`}
        action={
          <div className="flex flex-wrap items-center gap-3">
            <Badge status={campaign.status} />
            <Link
              href="/campaigns"
              className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              All campaigns
            </Link>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Recipients" value={recipients.total} hint="Added to this campaign" />
        <StatCard
          label="Schedule"
          value={campaign.scheduled_at ? formatDate(campaign.scheduled_at) : "Manual"}
          hint={campaign.scheduled_at ? "Asia/Kolkata" : "Starts when you start it"}
        />
        <StatCard
          label="Type"
          value={titleCase(campaign.type)}
          hint={campaign.type === "voice" ? "Calls with AI disclosure" : "Email with unsubscribe"}
        />
        <StatCard
          label="Events"
          value={campaignEvents.length}
          hint="Recorded for this campaign"
        />
      </div>

      <Section
        title="Controls"
        description="Starting a campaign queues work for the module worker. Consent and suppression are re-checked per recipient."
      >
        <CampaignActions campaign={campaign} />
      </Section>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section
            title="Recipients"
            description={`${recipients.total} contact${recipients.total === 1 ? "" : "s"} in this campaign.`}
          >
            {recipients.items.length === 0 ? (
              <EmptyState
                title="No recipients yet"
                description="Search the workspace contacts and add the ones you want to contact."
              />
            ) : (
              <div className="space-y-4">
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-3 py-2">Contact</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Attempts</th>
                        <th className="px-3 py-2">Last attempt</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {recipients.items.map((item) => (
                        <tr key={item.id} className="hover:bg-slate-50">
                          <td className="px-3 py-2">
                            <Link
                              href={`/contacts/${item.contact_id}`}
                              className="font-medium text-slate-900 hover:text-indigo-600"
                            >
                              {item.contact.name ??
                                item.contact.email ??
                                item.contact.phone ??
                                "Unnamed"}
                            </Link>
                            <p className="text-xs text-slate-500">
                              {[item.contact.phone, item.contact.email]
                                .filter(Boolean)
                                .join(" · ")}
                            </p>
                          </td>
                          <td className="px-3 py-2">
                            <Badge status={item.status} />
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-600">{item.attempts}</td>
                          <td className="px-3 py-2 text-xs text-slate-500">
                            {item.last_attempt_at ? formatDate(item.last_attempt_at) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  basePath={base}
                  params={{}}
                  total={recipients.total}
                  limit={recipients.limit}
                  offset={recipients.offset}
                />
              </div>
            )}
          </Section>

          {editable ? (
            <Section
              title="Add recipients"
              description="Pick contacts from this workspace. Duplicates are skipped automatically."
            >
              <ContactPicker campaignId={campaign.id} initialContacts={contacts.items} />
            </Section>
          ) : (
            <Section
              title="Add recipients"
              description="Recipients can only be changed while the campaign is a draft or paused."
            >
              <p className="text-sm text-slate-500">
                This campaign is {titleCase(campaign.status)}. Stop or pause it before changing the
                recipient list.
              </p>
            </Section>
          )}
        </div>

        <div className="space-y-6">
          <Section title="Settings" description="Used by the module agent at run time.">
            {Object.keys(campaign.settings).length === 0 ? (
              <p className="text-sm text-slate-500">No settings recorded.</p>
            ) : (
              <dl className="space-y-2 text-sm">
                {Object.entries(campaign.settings).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs uppercase tracking-wide text-slate-500">{key}</dt>
                    <dd className="break-words text-slate-800">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Section>

          <Section title="Campaign activity" description="Events recorded against this campaign.">
            {campaignEvents.length === 0 ? (
              <p className="text-sm text-slate-500">Nothing recorded yet.</p>
            ) : (
              <ol className="relative space-y-4 border-l border-slate-200 pl-4">
                {campaignEvents.map((event) => (
                  <li key={event.id} className="relative">
                    <span className="absolute -left-[21px] top-1.5 size-2 rounded-full bg-slate-400 ring-4 ring-white" />
                    <p className="text-sm font-medium text-slate-900">
                      {titleCase(event.type.replaceAll(".", " "))}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">{formatDate(event.occurred_at)}</p>
                  </li>
                ))}
              </ol>
            )}
          </Section>

          <Section title="Compliance" description="Rules applied to every recipient.">
            <ul className="space-y-2 text-sm text-slate-600">
              <li>Consent must be granted for the campaign channel.</li>
              <li>Suppressed numbers and addresses are skipped.</li>
              <li>Voice calls only run inside the workspace calling window.</li>
              <li>Campaigns never start themselves unless scheduled.</li>
            </ul>
          </Section>
        </div>
      </div>
    </div>
  );
}
