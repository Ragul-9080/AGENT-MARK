import Link from "next/link";

import { ImportPanel } from "@/components/import-panel";
import { PageHeading, Section } from "@/components/ui";

export const metadata = { title: "Import contacts" };

export default function ImportContactsPage() {
  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow="Audience"
        title="Import contacts from CSV"
        description="Preview runs a dry run first. Nothing is written until you import, and duplicates or invalid rows are skipped."
        action={
          <Link
            href="/contacts"
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Back to contacts
          </Link>
        }
      />

      <Section title="Upload" description="UTF-8 CSV, up to 5 MB and 50,000 rows.">
        <ImportPanel />
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          title="Expected columns"
          description="Only the header names matter; extra columns are stored as custom fields."
        >
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Column</th>
                  <th className="px-3 py-2">Required</th>
                  <th className="px-3 py-2">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                <tr>
                  <td className="px-3 py-2 font-mono text-xs">name</td>
                  <td className="px-3 py-2">No</td>
                  <td className="px-3 py-2">Display name.</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-mono text-xs">phone</td>
                  <td className="px-3 py-2">One of phone/email</td>
                  <td className="px-3 py-2">Normalised to E.164. Indian numbers without a code get +91.</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-mono text-xs">email</td>
                  <td className="px-3 py-2">One of phone/email</td>
                  <td className="px-3 py-2">Lower-cased and validated.</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-mono text-xs">language</td>
                  <td className="px-3 py-2">No</td>
                  <td className="px-3 py-2">Defaults to the workspace language.</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-mono text-xs">tags</td>
                  <td className="px-3 py-2">No</td>
                  <td className="px-3 py-2">Comma, pipe or semicolon separated.</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-mono text-xs">source</td>
                  <td className="px-3 py-2">No</td>
                  <td className="px-3 py-2">Where the contact came from. Defaults to csv_import.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>

        <Section
          title="Before you import"
          description="Consent must be collected before contacts enter the platform."
        >
          <ul className="space-y-3 text-sm text-slate-600">
            <li>
              Only upload people who gave you permission to be contacted. Importing a list does not
              create consent — record it on each contact or leave them ineligible.
            </li>
            <li>
              Rows that repeat a phone or email already in this workspace are marked as duplicates and
              skipped.
            </li>
            <li>
              Suppressed numbers and addresses stay suppressed. The suppression list is checked again
              before every call and send.
            </li>
            <li>
              Nothing is sent during import. Campaigns and agents start only when you start them.
            </li>
          </ul>
        </Section>
      </div>
    </div>
  );
}
