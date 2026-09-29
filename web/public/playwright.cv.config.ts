import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const checkout = process.env.ECODELING_CV_CHECKOUT;
if (!checkout)
  throw new Error(
    "Set ECODELING_CV_CHECKOUT to a CV checkout containing the exported assets.",
  );
const port = 4283;
export default defineConfig({
  testDir: "./e2e",
  testMatch: "reader-cv.spec.ts",
  projects: [
    { name: "cv-desktop", use: { viewport: { width: 1280, height: 900 } } },
    { name: "cv-mobile", use: { ...devices["iPhone 13"] } },
  ],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: "chromium",
    launchOptions: existsSync("/usr/bin/chromium")
      ? { executablePath: "/usr/bin/chromium" }
      : {},
  },
  webServer: {
    command: "go run ./cmd/server",
    cwd: checkout,
    url: `http://127.0.0.1:${port}/healthz`,
    env: {
      PORT: String(port),
      GOCACHE: "/tmp/ecodeling-cv-go-cache",
      GOMODCACHE: "/tmp/ecodeling-cv-go-mod",
    },
    timeout: 120_000,
  },
});
