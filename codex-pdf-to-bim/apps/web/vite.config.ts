import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";


export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", "HEARTHVIEW_");
  const apiPort = environment.HEARTHVIEW_API_PORT ?? "8008";
  const webPort = Number(environment.HEARTHVIEW_WEB_PORT ?? "5178");
  return {
    plugins: [react()],
    server: {
      port: webPort,
      proxy: {
        "/api": `http://127.0.0.1:${apiPort}`,
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: true,
    },
  };
});
