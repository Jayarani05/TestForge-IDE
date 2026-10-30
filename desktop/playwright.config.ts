import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.ts",
  use: {
    baseURL: "http://127.0.0.1:4175",
    browserName: "chromium",
  },
  webServer: {
    command:
      "npx vite --config vite.config.test.mts --host 127.0.0.1 --port 4175 --strictPort",
    port: 4175,
    reuseExistingServer: !process.env.CI,
  },
});
