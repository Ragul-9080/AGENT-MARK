import Link from "next/link";

import { PageHeading, Section } from "@/components/ui";

export const metadata = { title: "Website & SEO" };

const ready = [
  "The `seo` module is a first-class event source, so crawl and audit results join the same workspace timeline.",
  "The dashboard already surfaces the latest completed SEO score for the workspace.",
  "Events, jobs and suppression rules are shared with the voice and email modules.",
];

const pending = [
  "A read-only website crawler that never writes to, logs into, or modifies the target site.",
  "Technical SEO audits with a transparent score breakdown, plus per-page findings.",
  "Keyword and topic suggestions, and content briefs an operator can review before publishing.",
  "Scheduled re-crawls that record score deltas as events over time.",
];

export default function SeoPage() {
  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow="Module"
        title="Website & SEO agent"
        description="Read-only analysis of a marketing site. The crawler and audit engine are Phase 3."
        action={
          <Link
            href="/"
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Back to overview
          </Link>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Ready in this phase" description="Shared platform pieces this module reuses.">
          <ul className="space-y-3 text-sm text-slate-600">
            {ready.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-1 size-2 shrink-0 rounded-full bg-emerald-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Next phase" description="Scope agreed, implementation not started.">
          <ul className="space-y-3 text-sm text-slate-600">
            {pending.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-1 size-2 shrink-0 rounded-full bg-amber-400" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>
      </div>

      <Section
        title="Boundaries we hold"
        description="The agent analyses and recommends. It never edits the site."
      >
        <ul className="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
          <li>The crawler is read-only and respects robots rules.</li>
          <li>No content is published or modified without a human.</li>
          <li>Scores are shown with their inputs, not as bare claims.</li>
          <li>Findings reference the page they came from.</li>
        </ul>
      </Section>
    </div>
  );
}
