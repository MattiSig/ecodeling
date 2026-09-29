import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  if (test.info().project.name === "reduced-motion") {
    await page.emulateMedia({ reducedMotion: "reduce" });
  }
  await page.goto("/web/public/?ecodeling-mode=story");
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

test("plays recorded months and preserves the month between modes", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop interaction trace");
  const experience = page.locator("ecodeling-experience");
  const range = experience.getByRole("slider", { name: "Simulation month" });
  await experience
    .getByRole("button", { name: "The price index rewrites debt" })
    .click();
  await expect(range).toHaveValue("5");
  await experience.getByRole("tab", { name: "Explore", exact: true }).click();
  await expect(range).toHaveValue("5");
  await experience.getByLabel("Playback speed").selectOption("2");
  await experience.getByRole("button", { name: "Play" }).click();
  await expect
    .poll(async () => Number(await range.inputValue()), { timeout: 2_000 })
    .toBeGreaterThanOrEqual(6);
  await experience.getByRole("button", { name: "Pause" }).click();
});

test("inspects recorded sector and representative values", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop inspection trace");
  const experience = page.locator("ecodeling-experience");
  await experience.getByRole("button", { name: /^Households/ }).click();
  await expect(experience.getByText("Financial assets")).toBeVisible();
  await experience
    .getByRole("button", { name: /low income high ltv borrower/ })
    .click();
  await expect(experience.getByText("Mortgage", { exact: true })).toBeVisible();
  await expect(
    experience
      .locator(".inspection-card code")
      .getByText("worker-household-00005"),
  ).toBeVisible();
});

test("keeps paired playback, camera, selection, and charts synchronized", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop comparison trace");
  const experience = page.locator("ecodeling-experience");
  const range = experience.getByRole("slider", { name: "Simulation month" });
  await experience.getByRole("tab", { name: "Compare", exact: true }).click();
  await expect(
    experience.getByRole("heading", {
      name: "One clock, two contract structures",
    }),
  ).toBeVisible();
  await experience
    .getByRole("button", { name: "Nominal", exact: true })
    .click();
  await expect(experience.locator(".run-panel.nominal")).toBeVisible();
  await expect(experience.locator(".run-panel.indexed")).toHaveCount(0);
  await experience
    .getByRole("button", { name: "Indexed", exact: true })
    .click();
  await expect(experience.locator(".run-panel.indexed")).toBeVisible();
  await expect(experience.locator(".run-panel.nominal")).toHaveCount(0);
  await experience.getByRole("button", { name: "Split screen" }).click();
  await experience
    .locator(".run-panel.nominal")
    .getByRole("button", { name: /^Banks/ })
    .click();
  await expect(experience.getByText("Shared camera: Banks")).toHaveCount(2);
  await experience.getByLabel("Comparison metric").selectOption("debt_service");
  await expect(
    experience.getByRole("heading", { name: "Debt service" }),
  ).toBeVisible();
  await experience.getByLabel("Playback speed").selectOption("2");
  await experience.getByRole("button", { name: "Play" }).click();
  await expect(range).toHaveValue("17", { timeout: 12_000 });
  await expect(experience.locator(".run-panel.nominal")).toContainText(
    "2026-06",
  );
  await expect(experience.locator(".run-panel.indexed")).toContainText(
    "2026-06",
  );
  await expect(experience.locator(".shared-cursor")).toHaveAttribute(
    "x1",
    "94",
  );
});

test("keeps Compare mode accessible and contained on narrow screens", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile comparison audit");
  const experience = page.locator("ecodeling-experience");
  await experience.getByRole("tab", { name: "Compare", exact: true }).click();
  const results = await new AxeBuilder({ page })
    .include("ecodeling-experience")
    .disableRules(["landmark-one-main"])
    .analyze();
  expect(results.violations).toEqual([]);
  const scrollWidth = await page.evaluate(
    () => document.documentElement.scrollWidth,
  );
  expect(scrollWidth).toBeLessThanOrEqual(390);
  await expect(experience.getByLabel("Comparison metric")).toBeVisible();
  await expect(
    experience.locator(".cohort-panel th", { hasText: "Indexed − nominal" }),
  ).toBeVisible();
});

test("runs a browser to API to Python simulation replay workflow", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop",
    "single full simulation workflow",
  );
  const experience = page.locator("ecodeling-experience");
  await experience
    .getByRole("tab", { name: "Laboratory", exact: true })
    .click();
  await expect(
    experience.getByRole("heading", { name: "Laboratory" }),
  ).toBeVisible();
  await experience.getByLabel("Months", { exact: true }).fill("6");
  await experience.getByLabel("Households").fill("10");
  await experience.getByLabel("Firms").fill("2");
  await experience.getByLabel("Shock month").fill("2");
  await experience.getByRole("button", { name: "Run experiment" }).click();
  await expect(experience.locator(".laboratory-status")).toContainText(
    "completed",
    { timeout: 30_000 },
  );
  await expect(experience.locator(".provenance")).toContainText(
    "public-laboratory",
  );
  await expect(
    experience.getByRole("button", { name: "Restore canonical replay" }),
  ).toBeVisible();
});

test("matches the deterministic economy-scene baseline", async ({ page }) => {
  const experience = page.locator("ecodeling-experience");
  await experience.evaluate((element) => element.setAttribute("static", ""));
  await experience
    .getByRole("button", { name: "Imported inputs cost more" })
    .click();
  await expect(experience.locator(".flow-layer line")).toHaveCount(7);
  await expect(
    experience.locator(".flow-layer line").filter({ hasText: "Exports:" }),
  ).toHaveCount(1);
  await expect(experience.locator(".flow-layer line").first()).toBeVisible();
  await expect(experience.locator(".stage")).toHaveScreenshot(
    "economy-scene.png",
    { animations: "disabled", caret: "hide" },
  );
});

test("still embeds the internal audit page", async ({ page }) => {
  await page.goto("/web/internal-audit/");
  await expect(
    page.getByRole("heading", { name: /Follow the mortgage/ }),
  ).toBeVisible();
});
