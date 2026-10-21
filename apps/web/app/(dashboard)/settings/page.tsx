import type { Member, Page, SessionResponse, Suppression } from "@ama/shared-types";

import { SuppressionPanel } from "@/components/suppression-panel";
import { Badge, PageHeading, Section } from "@/components/ui";
import { WorkspaceForm } from "@/components/workspace-form";
import { ApiError, serverApi } from "@/lib/server-api";

export const metadata = { title: "Settings" };

type MeResponse = SessionResponse;

export default async function SettingsPage() {
  const me = await serverApi<MeResponse>("/auth/me", "/settings");
  const canAdminister = me.user.role === "owner" || me.user.role === "admin";

  let members: Member[] | null = null;
  if (canAdminister) {
    try {
      members = await serverApi<Member[]>("/workspace/members", "/settings");
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 403)) throw error;
    }
  }

  const suppressions = await serverApi<Page<Suppression>>("/suppressions?limit=50", "/settings");
  const hours = me.workspace.settings.calling_hours;

  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow="Workspace"
        title="Settings"
        description="Workspace profile, calling window, team members and the suppression list."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {canAdminister ? (
            <Section
              title="Workspace"
              description="Time zone and calling window drive when the voice agent is allowed to dial."
            >
              <WorkspaceForm workspace={me.workspace} />
            </Section>
          ) : (
            <Section
              title="Workspace"
              description="Only owners and admins can change workspace settings."
            >
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-slate-500">Name</dt>
                  <dd className="text-slate-800">{me.workspace.name}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Time zone</dt>
                  <dd className="text-slate-800">{me.workspace.timezone}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Default language</dt>
                  <dd className="text-slate-800">{me.workspace.default_language}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Calling window</dt>
                  <dd className="text-slate-800">
                    {typeof hours === "object" && hours !== null
                      ? `${(hours as { start?: string }).start ?? "—"}–${(hours as { end?: string }).end ?? "—"}`
                      : "09:00–21:00"}
                  </dd>
                </div>
              </dl>
            </Section>
          )}

          <Section
            title="Suppression list"
            description="Numbers and addresses that must never be contacted on that channel."
          >
            <SuppressionPanel suppressions={suppressions.items} />
            {suppressions.total > suppressions.items.length ? (
              <p className="mt-3 text-xs text-slate-500">
                Showing {suppressions.items.length} of {suppressions.total} entries.
              </p>
            ) : null}
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Signed in as">
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-xs text-slate-500">Role</dt>
                <dd className="mt-0.5">
                  <Badge status={me.user.role} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Workspace ID</dt>
                <dd className="break-all font-mono text-xs text-slate-700">
                  {me.workspace.id}
                </dd>
              </div>
            </dl>
          </Section>

          <Section
            title="Team members"
            description={
              canAdminister ? "Everyone with access to this workspace." : "Owners and admins only."
            }
          >
            {members === null ? (
              <p className="text-sm text-slate-500">
                You do not have permission to view the member list.
              </p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {members.map((member) => (
                  <li key={member.id} className="flex items-center justify-between gap-3 py-2">
                    <div>
                      <p className="text-sm font-medium text-slate-800">{member.name}</p>
                      <p className="text-xs text-slate-500">{member.email}</p>
                    </div>
                    <Badge status={member.role} />
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Data residency" description="How records are handled.">
            <ul className="space-y-2 text-sm text-slate-600">
              <li>Every record carries a workspace id and is filtered by it on read and write.</li>
              <li>Logs exclude phone numbers, emails and message bodies.</li>
              <li>
                Consent and suppression history is kept with the contact so eligibility can be
                re-checked before every attempt.
              </li>
            </ul>
          </Section>
        </div>
      </div>
    </div>
  );
}
