import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Agentic Marketing Platform",
    template: "%s · Agentic Marketing",
  },
  description:
    "Voice, website and email marketing agents in one workspace, with compliance built in.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
