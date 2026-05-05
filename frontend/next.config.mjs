/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
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
