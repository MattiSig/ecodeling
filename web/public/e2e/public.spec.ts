import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  if (test.info().project.name === "reduced-motion") {
    await page.emulateMedia({ reducedMotion: "reduce" });
  }
  await page.goto("/web/public/");
  await expect(page.locator("ecodeling-experience")).toHaveAttribute(
    "role",
    "region",
  );
  await expect(page.getByText("canonical-replay-v1")).toBeVisible();
});

test("loads the canonical replay and exposes keyboard timeline state", async ({
  page,
}) => {
  const experience = page.locator("ecodeling-experience");
  const range = experience.getByRole("slider", { name: "Simulation month" });
  await expect(range).toHaveValue("0");
  await experience.focus();
  await page.keyboard.press("ArrowRight");
  await expect(range).toHaveValue("1");
  await expect(
    experience.getByText("2025-02", { exact: true }).first(),
  ).toBeVisible();
});

test("has no automatically detectable accessibility violations", async ({
  page,
}) => {
  const results = await new AxeBuilder({ page })
    .include("ecodeling-experience")
    .disableRules(["landmark-one-main"])
    .analyze();
  expect(results.violations).toEqual([]);
});

test("keeps the component within the mobile viewport", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "mobile",
    "mobile-only responsive assertion",
  );
  const box = await page.locator("ecodeling-experience").boundingBox();
  expect(box).not.toBeNull();
  expect(box?.width).toBeLessThanOrEqual(390);
  const scrollWidth = await page.evaluate(
    () => document.documentElement.scrollWidth,
  );
  expect(scrollWidth).toBeLessThanOrEqual(390);
});

test("reports reduced motion in the component shell", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "reduced-motion",
    "reduced-motion-only assertion",
  );
  await expect(page.getByText("Reduced motion")).toBeVisible();
});

test("still embeds the internal audit page", async ({ page }) => {
  await page.goto("/web/internal-audit/");
  await expect(
    page.getByRole("heading", { name: /Follow the mortgage/ }),
  ).toBeVisible();
});
