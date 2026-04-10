import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  // Globe.gl uses three.js which requires transpiling
  transpilePackages: ["react-globe.gl", "three"],

  // Pre-launch: keep SalientSignal out of search engines entirely.
  // The middleware also sets these headers, but framework-level headers
  // run on static assets the middleware matcher excludes.
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Robots-Tag",
            value: "noindex, nofollow, noarchive, nosnippet",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
