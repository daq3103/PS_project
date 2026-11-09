import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    cpus: Math.max(1, Number(process.env.NEXT_BUILD_CPUS ?? "2")),
    webpackMemoryOptimizations: true,
  },
  async redirects() { return [{source:"/cuu-ho/:path*",destination:"/tram-cuu-ho/:path*",permanent:true}]; },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; " +
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://challenges.cloudflare.com https://accounts.google.com; " +
              "style-src 'self' 'unsafe-inline' https://accounts.google.com; " +
              "img-src 'self' data: https:; " +
              "font-src 'self'; " +
              "connect-src 'self' https://challenges.cloudflare.com https://accounts.google.com; " +
              "frame-src https://challenges.cloudflare.com https://accounts.google.com; " +
              "frame-ancestors 'none'; " +
              "upgrade-insecure-requests",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
