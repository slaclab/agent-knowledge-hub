/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  experimental: {
    esmExternals: false,
  },
  async redirects() {
    return [
      {
        source: "/marketplace.json",
        destination: "/cli/api/marketplace.json",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
