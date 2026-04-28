import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  outputFileTracingRoot: path.resolve(__dirname),
};

export default config;
