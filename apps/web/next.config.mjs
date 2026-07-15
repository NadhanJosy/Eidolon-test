const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

if (process.env.NODE_ENV === "production") {
  if (!configuredApiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is required for a production frontend build.");
  }
  const apiUrl = new URL(configuredApiBaseUrl);
  if (!new Set(["http:", "https:"]).has(apiUrl.protocol) || apiUrl.username || apiUrl.password) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must be an HTTP(S) URL without credentials.");
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  poweredByHeader: false
};

export default nextConfig;
