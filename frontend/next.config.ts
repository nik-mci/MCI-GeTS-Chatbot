import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/stream',
        destination: 'http://localhost:8000/chat/stream',
      },
    ];
  },
};

export default nextConfig;
