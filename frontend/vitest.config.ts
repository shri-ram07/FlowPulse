import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "jsdom",
    include: ["lib/**/*.test.ts", "components/**/*.test.tsx"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary", "lcov"],
      include: ["lib/scoring.ts", "components/ZoneCard.tsx", "components/Toast.tsx"],
      // Scope the threshold to pure-logic modules that can be unit-tested
      // without a browser. StadiumMap + WebSocket hook + API client require
      // Playwright's real-browser context — they're covered by e2e, not here.
      exclude: ["**/*.test.{ts,tsx}", "**/*.config.{ts,js}", "**/node_modules/**", ".next/**"],
      thresholds: {
        lines: 80,
        statements: 80,
        functions: 75,
        branches: 70,
      },
    },
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
});
