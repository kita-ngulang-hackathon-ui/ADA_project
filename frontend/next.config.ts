import type { NextConfig } from "next";

// Standalone output for Docker; images stay local (offline demo).
const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [],
  },
};

export default nextConfig;
