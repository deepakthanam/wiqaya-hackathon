/** @type {import('next').NextConfig} */
const apiOrigin = process.env.API_ORIGIN || "http://localhost:8000";
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Same-origin proxy: the browser talks to /api/v1 on the web origin, so the session cookie is first-party.
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ],
    }];
  },
};
export default nextConfig;
