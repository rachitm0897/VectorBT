import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

declare const process: {
  env: Record<string, string | undefined>;
};

const backendProxyTarget = process.env.VITE_BACKEND_PROXY_TARGET;
const configuredBase = process.env.VITE_FRONTEND_BASE || process.env.VITE_APP_BASE_PATH || process.env.ROOT_PATH || "/insta_backtester_frontend/";
const devPort = Number(process.env.VITE_DEV_PORT ?? 5173);

function normalizeBase(base: string): string {
  if (base === "/" || base.trim() === "") {
    return "/";
  }

  const path = base.trim().replace(/^\/+|\/+$/g, "");
  return `/${path}/`;
}

export default defineConfig({
  base: normalizeBase(configuredBase),
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: devPort,
    allowedHosts: ["qfsplatform.com"],
    proxy: backendProxyTarget
      ? {
          "/insta_backtester/api": {
            target: backendProxyTarget,
            changeOrigin: true,
          },
          "/insta_backtester/v1": {
            target: backendProxyTarget,
            changeOrigin: true,
          },
          "/insta_backtester_api": {
            target: backendProxyTarget,
            changeOrigin: true,
          },
          "/vectorbt_api": {
            target: backendProxyTarget,
            changeOrigin: true,
          },
        }
      : undefined,
  },
});
