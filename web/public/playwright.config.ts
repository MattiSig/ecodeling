import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const systemChromium = "/usr/bin/chromium";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 900 } } },
    { name: "mobile", use: { ...devices["iPhone 13"] } },
    {
      name: "reduced-motion",
      use: { colorScheme: "light", viewport: { width: 1280, height: 900 } },
    },
  ],
  use: {
    baseURL: "http://127.0.0.1:4173",
    browserName: "chromium",
    launchOptions: existsSync(systemChromium)
      ? { executablePath: systemChromium }
      : {},
  },
  webServer: [
    {
      command:
        "env UV_CACHE_DIR=/tmp/ecodeling-uv-cache ECODELING_SERVICE_DATA=/tmp/ecodeling-playwright-service uv run uvicorn ecodeling.service.api:app --host 127.0.0.1 --port 8765",
      cwd: ".",
      url: "http://127.0.0.1:8765/docs",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev:web -- --host 127.0.0.1 --port 4173",
      cwd: ".",
      url: "http://127.0.0.1:4173/web/public/",
      reuseExistingServer: false,
    },
  ],
});
