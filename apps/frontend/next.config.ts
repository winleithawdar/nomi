import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // The repository intentionally has root and frontend lockfiles.
  outputFileTracingRoot: path.join(__dirname, "../.."),
  typedRoutes: true,
};

export default nextConfig;
