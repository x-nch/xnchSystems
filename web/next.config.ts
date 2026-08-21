import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["192.168.1.10"],
  transpilePackages: ["three", "3d-force-graph", "react-force-graph-3d"],
};

export default nextConfig;
