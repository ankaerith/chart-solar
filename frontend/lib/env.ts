/**
 * Validated frontend env. Reading `process.env` outside this module is a smell:
 * the value can be silently `undefined` and bugs surface at runtime in prod.
 *
 * `NEXT_PUBLIC_*` vars are inlined at build time and visible to the browser.
 * Anything sensitive (API keys, DB URLs, JWT secrets) lives in the backend.
 */

const isProd = process.env.NODE_ENV === "production";

const publicVar = (name: string, fallback?: string): string => {
  const value = process.env[name] ?? fallback;
  if (!value) {
    if (isProd) {
      throw new Error(`Missing required public env var \`${name}\` in production build.`);
    }
    return "";
  }
  return value;
};

export const env = {
  apiUrl: publicVar("NEXT_PUBLIC_API_URL", "http://localhost:8000"),
} as const;
