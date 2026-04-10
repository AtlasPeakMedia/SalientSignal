import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  // Globe.gl uses three.js which requires transpiling
  transpilePackages: ["react-globe.gl", "three"],
};

export default nextConfig;
