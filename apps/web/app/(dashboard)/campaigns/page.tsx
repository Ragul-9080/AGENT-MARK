import type { Campaign, Page } from "@ama/shared-types";
import Link from "next/link";

import { CampaignForm } from "@/components/campaign-form";
import { Pagination } from "@/components/pagination";
import { Badge, EmptyState, PageHeading, Section } from "@/components/ui";
import { formatDate, titleCase } from "@/lib/format";
import { serverApi } from "@/lib/server-api";

export const metadata = { title: "Campaigns" };

const PAGE_SIZE = 25;
const STATUSES = ["draft", "scheduled", "running", "paused", "completed", "failed"] as const;

type SearchParams = Record<string, string | string[] | undefined>;

function single(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

export default async function CampaignsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const type = single(params.type);
  const status = single(params.status);
  const offset = Math.max(Number.parseInt(single(params.offset) || "0", 10) || 0, 0);

  const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (type) query.set("type", type);
  if (status) query.set("status", status);

  const page = await serverApi<Page<Campaign>>(`/campaigns?${query.toString()}`, "/campaigns");

  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow="Outreach"
        title="Campaigns"
        description="A campaign is a list of consenting recipients plus the settings your voice or email agent uses."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Section
            title="Campaigns"
            description={`${page.total} campaign${page.total === 1 ? "" : "s"} in this workspace.`}
            action={
              <form method="get" action="/campaigns" className="flex items-end gap-2">
                <label className="block">
                  <span className="sr-only">Type</span>
                  <select
                    name="type"
                    defaultValue={type}
                    className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm"
                  >
                    <option value="">All types</option>
                    <option value="voice">Voice</option>
                    <option value="email">Email</option>
                  </select>
                </label>
                <label className="block">
                  <span className="sr-only">Status</span>
                  <select
                    name="status"
                    defaultValue={status}
                    className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm"
                  >
                    <option value="">All statuses</option>
                    {STATUSES.map((item) => (
                      <option key={item} value={item}>
                        {titleCase(item)}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="submit"
                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Filter
                </button>
              </form>
            }
          >
            {page.items.length === 0 ? (
              <EmptyState
                title="No campaigns yet"
                description="Create a campaign, add consenting contacts, then start it. Nothing sends on its own."
              />
            ) : (
              <div className="space-y-4">
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-3 py-2">Campaign</th>
                        <th className="px-3 py-2">Type</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Schedule</th>
                        <th className="px-3 py-2">Updated</th>
                        <th className="px-3 py-2" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {page.items.map((campaign) => (
                        <tr key={campaign.id} className="hover:bg-slate-50">
                          <td className="px-3 py-2">
                            <Link
                              href={`/campaigns/${campaign.id}`}
                              className="font-medium text-slate-900 hover:text-indigo-600"
                            >
                              {campaign.name}
                            </Link>
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-600">
                            {titleCase(campaign.type)}
                          </td>
                          <td className="px-3 py-2">
                            <Badge status={campaign.status} />
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-500">
                            {campaign.scheduled_at ? formatDate(campaign.scheduled_at) : "Manual"}
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-500">
                            {formatDate(campaign.updated_at)}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <Link
                              href={`/campaigns/${campaign.id}`}
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
                  basePath="/campaigns"
                  params={{ type, status }}
                  total={page.total}
                  limit={page.limit}
                  offset={page.offset}
                />
              </div>
            )}
          </Section>
        </div>

        <Section
          title="New campaign"
          description="Draft first. Add recipients, then start it."
        >
          <CampaignForm />
        </Section>
      </div>
    </div>
  );
}
