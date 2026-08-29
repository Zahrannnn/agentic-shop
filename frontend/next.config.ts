import type { NextConfig } from "next";

const nextConfig: NextConfig = {
   logging: {
    browserToTerminal: true,
    // 'error' — errors only (default)
    // 'warn'  — warnings and errors
    // true    — all console output
    // false   — disabled
  },
  cacheComponents: true,
  output: "standalone",
  reactCompiler: true,
  typedRoutes: true,
  experimental: {
    turbopackFileSystemCacheForBuild: true,
  },
};

export default nextConfig;
