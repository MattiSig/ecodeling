import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import { mkdir, rename } from "node:fs/promises";
import { once } from "node:events";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const output = path.join(root, "publication/v0.1/fallback");
const port = 4187;
const origin = `http://127.0.0.1:${port}`;
const scenes = [
  "The economic circuit",
  "The exchange-rate shock",
  "Imported inputs cost more",
  "Firm prices move the CPI",
  "The price index rewrites debt",
  "Households and banks respond",
];

await mkdir(output, { recursive: true });
const server = spawn(
  "npm",
  ["run", "dev:web", "--", "--host", "127.0.0.1", "--port", String(port)],
  { cwd: root, stdio: ["ignore", "pipe", "pipe"] },
);

async function waitForServer() {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(`${origin}/web/public/`);
      if (response.ok) return;
    } catch {
      // Vite is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("publication fallback host did not start");
}

let browser;
try {
  await waitForServer();
  browser = await chromium.launch({
    executablePath: "/usr/bin/chromium",
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    recordVideo: { dir: output, size: { width: 1280, height: 900 } },
    reducedMotion: "reduce",
    colorScheme: "dark",
  });
  const page = await context.newPage();
  await page.goto(`${origin}/web/public/?ecodeling-mode=story`, { waitUntil: "networkidle" });
  const experience = page.locator("ecodeling-experience");
  await experience.evaluate((element) => element.setAttribute("static", ""));
  const video = page.video();

  for (const [index, title] of scenes.entries()) {
    await experience.getByRole("button", { name: title }).click();
    await experience.locator(".stage").scrollIntoViewIfNeeded();
    await experience.locator(".stage").screenshot({
      path: path.join(output, `scene-${String(index + 1).padStart(2, "0")}.png`),
      animations: "disabled",
    });
    await page.waitForTimeout(500);
  }

  await page.close();
  await context.close();
  if (video) {
    await rename(await video.path(), path.join(output, "canonical-story.webm"));
  }
} finally {
  if (browser) await browser.close();
  server.kill("SIGTERM");
  await Promise.race([
    once(server, "exit"),
    new Promise((resolve) => setTimeout(resolve, 2_000)),
  ]);
}

console.log(`Exported ${scenes.length} static scenes and canonical-story.webm`);
