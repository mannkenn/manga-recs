/** @type {import('next').NextConfig} */

// `output: 'export'` emits a fully static bundle into ./out, which FastAPI then
// serves directly. That collapses the demo to a single container on a single
// origin, which in turn removes CORS and the API-proxy route from the picture.
//
// The trade-off is that API routes and other server-side Next features are no
// longer available. The only one this app had was a proxy to the backend, which
// is redundant once both are served from the same origin.
const nextConfig = {
  output: 'export',
  reactStrictMode: true,
  // Emit directory-style paths so the export works when served by a plain
  // static file handler with no rewrite rules.
  trailingSlash: true,
  images: { unoptimized: true },
};

module.exports = nextConfig;
