import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const systemChromium = "/usr/bin/chromium";
const apiPort = Number(process.env.ECODELING_API_PORT ?? 8765);
const webPort = Number(process.env.ECODELING_WEB_PORT ?? 4173);

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
    baseURL: `http://127.0.0.1:${webPort}`,
    browserName: "chromium",
    launchOptions: existsSync(systemChromium)
      ? { executablePath: systemChromium }
      : {},
  },
  webServer: [
    {
      command: `env UV_CACHE_DIR=/tmp/ecodeling-uv-cache ECODELING_SERVICE_DATA=/tmp/ecodeling-playwright-service uv run uvicorn ecodeling.service.api:app --host 127.0.0.1 --port ${apiPort}`,
      cwd: ".",
      url: `http://127.0.0.1:${apiPort}/docs`,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev:web -- --host 127.0.0.1 --port ${webPort}`,
      cwd: ".",
      url: `http://127.0.0.1:${webPort}/web/public/`,
      reuseExistingServer: false,
    },
  ],
});
