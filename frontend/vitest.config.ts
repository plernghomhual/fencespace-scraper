import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  oxc: {
    jsx: {
      runtime: "automatic",
      importSource: "react",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    setupFiles: ["./src/test/setup.ts"],
    testTimeout: 20000,
  },
  resolve: {
    alias: {
      "@/app": path.resolve(__dirname, "app"),
      "@": path.resolve(__dirname, "src"),
    },
  },
});
