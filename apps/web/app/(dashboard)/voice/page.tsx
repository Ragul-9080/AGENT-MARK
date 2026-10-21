import Link from "next/link";

import { PageHeading, Section } from "@/components/ui";

export const metadata = { title: "Voice" };

const ready = [
  "Voice campaigns exist as a first-class campaign type with a draft → scheduled → running → paused → completed state machine.",
  "Consent is tracked per channel, so a voice call is refused unless the contact granted voice consent.",
  "The workspace calling window is enforced before a dial, and the suppression list wins over consent.",
  "A workspace-scoped webhook endpoint already accepts and stores raw provider callbacks (POST /webhooks/vobiz).",
  "A dedicated `voice` Celery queue and worker run alongside the API, ready for real call jobs.",
];

const pending = [
  "Outbound call placement through Vobiz, with the exact credential and webhook signature scheme confirmed first.",
  "Sarvam speech-to-text and text-to-speech wiring for Indian languages, including the model version decision.",
  "The spoken AI disclosure line and the recording-consent prompt that must play before recording starts.",
  "Human handoff to a live agent, with the transfer event recorded on the contact timeline.",
  "Call outcome classification and retry policy driven by consent and suppression checks.",
];

export default function VoicePage() {
  return (
    <div className="space-y-8">
      <PageHeading
        eyebrow="Module"
        title="Voice agent"
        description="Outbound and inbound calling with an Indian-language voice agent. The calling engine is Phase 2; the foundations, guardrails and queue are in place."
        action={
          <Link
            href="/campaigns?type=voice"
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Voice campaigns
          </Link>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Ready in this phase" description="Shared platform pieces the voice agent builds on.">
          <ul className="space-y-3 text-sm text-slate-600">
            {ready.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-1 size-2 shrink-0 rounded-full bg-emerald-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Next phase" description="Tracked and blocked on provider documentation.">
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
        description="These run in the shared services, so the voice worker cannot bypass them."
      >
        <ul className="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
          <li>Consent is checked before eligibility, always.</li>
          <li>Suppression entries block the call even with consent.</li>
          <li>Calls are limited to the workspace calling window.</li>
          <li>Phone numbers are never written to application logs.</li>
          <li>Raw provider callbacks are stored before any parsing.</li>
          <li>Failed agents are stopped rather than allowed to improvise.</li>
        </ul>
      </Section>
    </div>
  );
}
