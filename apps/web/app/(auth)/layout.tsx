import Link from "next/link";
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-slate-950 via-slate-900 to-indigo-950">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center gap-2 text-white">
          <span className="grid size-8 place-items-center rounded-lg bg-indigo-500 text-sm font-bold">
            AM
          </span>
          <span className="text-sm font-semibold tracking-wide">Agentic Marketing</span>
        </Link>
        <span className="rounded-full border border-white/20 px-3 py-1 text-xs text-slate-300">
          Phase 1
        </span>
      </header>
      <main className="flex flex-1 items-center justify-center px-6 pb-16">{children}</main>
      <footer className="px-6 pb-8 text-center text-xs text-slate-400">
        Consent first · suppression aware · workspace isolated
      </footer>
    </div>
  );
}
