/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

import { buildCsp } from "./src/lib/csp";

/** Attach the SPA's Content-Security-Policy.
 *
 * Dev gets it as a response header from the dev server (relaxed enough for HMR);
 * the production build gets it as a <meta> tag so the policy travels with the
 * bundle onto whatever static host serves it.
 */
function csp(apiOrigin: string): Plugin {
  return {
    name: "wb-analytics-csp",
    configureServer(server) {
      server.middlewares.use((_req, res, next) => {
        res.setHeader("Content-Security-Policy", buildCsp(apiOrigin, { dev: true }));
        next();
      });
    },
    transformIndexHtml: {
      order: "pre",
      handler(html, ctx) {
        if (ctx.server) return html; // dev is covered by the header above
        const tag = `<meta http-equiv="Content-Security-Policy" content="${buildCsp(apiOrigin)}" />`;
        return html.replace("<head>", `<head>\n    ${tag}`);
      },
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const apiOrigin = env.VITE_API_BASE ?? "http://localhost:8000";

  return {
    plugins: [react(), csp(apiOrigin)],
    server: { host: "127.0.0.1", port: 5173 },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/setupTests.ts",
      css: true,
      coverage: {
        provider: "v8",
        reportsDirectory: "./coverage",
        thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
      },
    },
  };
});
