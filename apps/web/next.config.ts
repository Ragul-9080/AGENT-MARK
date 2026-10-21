import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.resolve(__dirname, "../.."),
  reactStrictMode: true,
  transpilePackages: ["@ama/shared-types"],
};

export default nextConfig;
