import path from "node:path";

import type { NextConfig } from "next";

// Next.js config for Zoho Catalyst client hosting (static export).
// Build output goes to apps/web/out/ and is copied to client/ for deployment.
const nextConfig: NextConfig = {
  output: "export",
  distDir: "out",
  reactStrictMode: true,
  transpilePackages: ["@ama/shared-types"],
  // Disable image optimization for static export (no server).
  images: {
    unoptimized: true,
  },
  // Trailing slash for static file compatibility.
  trailingSlash: true,
};

export default nextConfig;
