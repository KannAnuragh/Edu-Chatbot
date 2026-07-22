/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  webpack: (config) => {
    // Required for react-pdf to work with Next.js
    config.resolve.alias.canvas = false;
    return config;
  },
};

module.exports = nextConfig;
