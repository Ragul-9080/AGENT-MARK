import Link from "next/link";

import { Badge, EmptyState, PageHeading, Section, StatCard } from "@/components/ui";
import { formatDate, titleCase } from "@/lib/format";
import { serverApi } from "@/lib/server-api";
import type { DashboardSummary } from "@ama/shared-types";

export const metadata = { title: "Overview" };

function eventLabel(value: string): string {
  return titleCase(value.replaceAll(".", " "));
}

export default async function DashboardPage() {
  const summary = await serverApi<DashboardSummary>("/dashboard/summary", "/");

  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow="Overview"
        title="Your marketing workspace"
        description="Contacts, campaigns and cross-module activity. Voice, SEO and email agents run on the same consent and suppression rules."
        action={
          <div className="flex gap-2">
            <Link
              href="/contacts/import"
              className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Import contacts
            </Link>
            <Link
              href="/campaigns"
              className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              View campaigns
            </Link>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Contacts" value={summary.contacts} hint="In this workspace" />
        <StatCard label="Calls" value={summary.calls} hint="Logged by the voice agent" />
        <StatCard label="Emails sent" value={summary.emails_sent} hint="Delivery tracked by events" />
        <StatCard
          label="Running campaigns"
          value={summary.running_campaigns}
          hint="Live right now"
        />
        <StatCard
          label="Latest SEO score"
          value={summary.latest_seo_score ?? "—"}
          hint={summary.latest_seo_score === null ? "No completed audit yet" : "Out of 100"}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          title="Active campaigns"
          description="Draft, scheduled, running and paused campaigns."
          action={
            <Link href="/campaigns" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">
              All campaigns
            </Link>
          }
        >
          {summary.active_campaigns.length === 0 ? (
            <EmptyState
              title="No active campaigns"
              description="Create a campaign, add consenting contacts, then start it."
              href="/campaigns"
              actionLabel="Create a campaign"
            />
          ) : (
            <ul className="divide-y divide-slate-100">
              {summary.active_campaigns.map((campaign) => (
                <li key={campaign.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div>
                    <Link
                      href={`/campaigns/${campaign.id}`}
                      className="text-sm font-medium text-slate-900 hover:text-indigo-600"
                    >
                      {campaign.name}
                    </Link>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {titleCase(campaign.type)} · updated {formatDate(campaign.updated_at)}
                    </p>
                  </div>
                  <Badge status={campaign.status} />
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section
          title="Recent activity"
          description="The shared event timeline across system, voice, email and SEO."
          action={
            <Link href="/contacts" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">
              Contacts
            </Link>
          }
        >
          {summary.recent_events.length === 0 ? (
            <EmptyState
              title="No activity yet"
              description="Import contacts or create a campaign to start the timeline."
              href="/contacts/import"
              actionLabel="Import contacts"
            />
          ) : (
            <ol className="relative space-y-4 border-l border-slate-200 pl-4">
              {summary.recent_events.map((event) => (
                <li key={event.id} className="relative">
                  <span className="absolute -left-[21px] top-1.5 size-2 rounded-full bg-indigo-500 ring-4 ring-white" />
                  <p className="text-sm font-medium text-slate-900">{eventLabel(event.type)}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {titleCase(event.source_module)} · {formatDate(event.occurred_at)}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </Section>
      </div>
    </div>
  );
}
