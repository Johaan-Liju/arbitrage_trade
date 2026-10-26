import type { NextConfig } from "next";

// Rewrites are captured during next build. Rebuild when changing this origin.
// Keep local development on loopback; hosted deployments explicitly opt in.
const backend = new URL(process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
if (!["http:", "https:"].includes(backend.protocol) || backend.pathname !== "/" ||
    backend.search || backend.hash || backend.username || backend.password) {
  throw new Error("BACKEND_URL must be an HTTP(S) origin, without /api, a path, credentials, query or fragment.");
}

const config: NextConfig = {
  turbopack: { root: process.cwd() },
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend.origin}/api/:path*` }];
  },
};
export default config;
