import Link from "next/link";

import { PageHeading, Section } from "@/components/ui";

export const metadata = { title: "Email" };

const ready = [
  "Email campaigns are a first-class type with the same state machine as voice campaigns.",
  "Email consent is tracked separately from voice consent, per contact.",
  "The suppression list stores unsubscribe, bounce, complaint and manual entries for addresses.",
  "A workspace-scoped webhook endpoint accepts provider delivery events (POST /webhooks/email).",
  "Sends are gated on consent and suppression before anything leaves the platform.",
];

const pending = [
  "Transactional sending through the chosen provider, with the sending domain and region confirmed.",
  "Templates with merge fields, and a preview before a campaign starts.",
  "Unsubscribe link handling that writes to the suppression list automatically.",
  "Bounce and complaint handling that suppresses the address on the first hard failure.",
  "Reply detection so a human can take over the conversation.",
];

export default function EmailPage() {
  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow="Module"
        title="Email agent"
        description="Campaign email with consent, suppression and delivery tracking. Sending is Phase 3; the queue, consent gate and callback storage are in place."
        action={
          <Link
            href="/campaigns?type=email"
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Email campaigns
          </Link>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Ready in this phase" description="Shared platform pieces the email agent builds on.">
          <ul className="space-y-3 text-sm text-slate-600">
            {ready.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-1 size-2 shrink-0 rounded-full bg-emerald-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Next phase" description="Needs a provider decision and credentials.">
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
        title="Compliance rules already enforced in code"
        description="Applied in the shared services, so the email worker cannot skip them."
      >
        <ul className="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
          <li>No send without recorded email consent.</li>
          <li>Suppressed addresses are skipped, even with consent.</li>
          <li>Message bodies and addresses stay out of application logs.</li>
          <li>Every send attempt is recorded as an event on the contact.</li>
          <li>Campaigns stop rather than retry past the attempt limit.</li>
          <li>Delivery callbacks are stored raw before parsing.</li>
        </ul>
      </Section>
    </div>
  );
}
