import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }, info) => {
  if (info.project.name === "reduced-motion")
    await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/web/public/");
  await expect(
    page.getByRole("tab", { name: "Article", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
});

test("first reader follows evidence into each mode and returns to the same article position", async ({
  page,
}) => {
  const reader = page.locator(".article-scroll");
  const articleTab = page.getByRole("tab", { name: "Article", exact: true });
  for (const [label, mode, index] of [
    ["View shock in Story", "Story", "3"],
    ["Inspect revaluation in Explore", "Explore", "5"],
    ["Compare closing results", "Compare", "17"],
  ] as const) {
    const link = reader.getByRole("button", { name: label, exact: true });
    await link.scrollIntoViewIfNeeded();
    const scroll = await reader.evaluate((el) => el.scrollTop);
    await link.click();
    await expect(
      page.getByRole("tab", { name: mode, exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await expect(
      page.getByRole("slider", { name: "Simulation month" }),
    ).toHaveValue(index);
    if (mode === "Explore")
      await expect(page.locator(".inspection-card")).toContainText("Banks");
    if (mode === "Compare") {
      await expect(page.getByLabel("Comparison metric")).toHaveValue(
        "mortgage_principal",
      );
      await expect(page.getByText("Shared camera: Banks")).toHaveCount(2);
    }
    await articleTab.click();
    await expect
      .poll(() => reader.evaluate((el) => el.scrollTop))
      .toBeCloseTo(scroll, 0);
  }
  await reader
    .getByRole("button", { name: /Inspect household: low income/ })
    .click();
  await expect(page.locator(".inspection-card")).toContainText(
    "worker-household-00005",
  );
  await page.getByRole("tab", { name: "Compare", exact: true }).click();
  await expect(
    page.getByText("Matched individual", { exact: true }),
  ).toBeVisible();
});

test("tabs support keyboard and touch without changing the economic clock; mode survives reload", async ({
  page,
}, info) => {
  const articleTab = page.getByRole("tab", { name: "Article", exact: true });
  await articleTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Story", exact: true }),
  ).toBeFocused();
  await expect(
    page.getByRole("slider", { name: "Simulation month" }),
  ).toHaveValue("0");
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Explore", exact: true }),
  ).toBeFocused();
  const compare = page.getByRole("tab", { name: "Compare", exact: true });
  if (info.project.name === "mobile") await compare.tap();
  else await compare.click();
  await page.reload();
  await expect(compare).toHaveAttribute("aria-selected", "true");
  await page.goto("/web/public/?ecodeling-mode=story");
  await expect(
    page.getByRole("tab", { name: "Story", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
});

test("Article pauses playback and keeps month, metric, selection and camera on return", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "Compare", exact: true }).click();
  await page.getByLabel("Comparison metric").selectOption("debt_service");
  await page
    .locator(".run-panel.nominal")
    .getByRole("button", { name: /^Banks/ })
    .click();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect
    .poll(() =>
      page.getByRole("slider", { name: "Simulation month" }).inputValue(),
    )
    .not.toBe("0");
  await page.getByRole("tab", { name: "Article", exact: true }).click();
  const month = await page
    .locator("ecodeling-experience")
    .evaluate(
      (el: HTMLElement & { replayState?: { monthIndex: number } }) =>
        el.replayState!.monthIndex,
    );
  // Observe longer than a normal playback tick, rather than asserting only immediate pause state.
  await page.waitForTimeout(1600);
  await page.getByRole("tab", { name: "Compare", exact: true }).click();
  await expect(
    page.getByRole("slider", { name: "Simulation month" }),
  ).toHaveValue(String(month));
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Comparison metric")).toHaveValue(
    "debt_service",
  );
  await expect(page.getByText("Shared camera: Banks")).toHaveCount(2);
});

test("glossary definitions work with hover, keyboard and touch and every surface passes axe", async ({
  page,
}, info) => {
  const inline = page.locator('[aria-describedby="term-intro-ABM"]');
  if (info.project.name === "mobile") await inline.tap();
  else await inline.hover();
  await expect(page.locator("#term-intro-ABM")).toBeVisible();
  await inline.focus();
  await page.keyboard.press("Escape");
  await expect(page.locator("#term-intro-ABM")).toBeHidden();
  await page.getByText("How to read this model", { exact: true }).click();
  await page
    .getByText("Glossary — words used in this model", { exact: true })
    .click();
  const cpi = page.locator('[aria-describedby="definition-CPI"]');
  if (info.project.name === "mobile") await cpi.tap();
  else await cpi.hover();
  await expect(page.locator("#definition-CPI")).toBeVisible();
  const fx = page.locator('[aria-describedby="definition-FX"]');
  await fx.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#definition-FX")).toBeVisible();
  for (const mode of ["Article", "Story", "Explore", "Compare", "Laboratory"]) {
    await page.getByRole("tab", { name: mode, exact: true }).click();
    const results = await new AxeBuilder({ page })
      .include("ecodeling-experience")
      .disableRules(["landmark-one-main"])
      .analyze();
    expect(results.violations, mode).toEqual([]);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflow, mode).toBe(false);
  }
});

test("static and failed replays keep the explanation accessible", async ({
  page,
}) => {
  const component = page.locator("ecodeling-experience");
  await component.evaluate((el) => el.setAttribute("static", ""));
  await expect(
    page.getByText("Interpretation, limitations, and conclusion", {
      exact: true,
    }),
  ).toBeAttached();
  await expect(page.locator("[data-claim]")).toHaveCount(12);
  await component.evaluate((el) =>
    el.setAttribute("src", "/missing-replay.json"),
  );
  await expect(
    page.getByText("Replay unavailable", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("When inflation changes the debt itself", { exact: true }),
  ).toBeVisible();
  await page
    .getByText("Glossary — words used in this model", { exact: true })
    .click();
  await expect(
    page.locator('[aria-describedby="definition-ISK"]'),
  ).toBeVisible();
  expect(
    (
      await new AxeBuilder({ page })
        .include("ecodeling-experience")
        .disableRules(["landmark-one-main"])
        .analyze()
    ).violations,
  ).toEqual([]);
});

for (const theme of ["dark", "light"]) {
  test(`reader screenshot in ${theme} host theme`, async ({ page }) => {
    if (theme === "light")
      await page.evaluate(() => {
        const style = document.documentElement.style;
        for (const [name, value] of Object.entries({
          bg: "#f5f4f0",
          fg: "#24262b",
          muted: "#62666e",
          rule: "#d5d5d1",
          accent: "#805a1b",
        }))
          style.setProperty(`--${name}`, value);
      });
    await page.locator(".mode-tabs").scrollIntoViewIfNeeded();
    await expect(page.locator(".ready")).toHaveScreenshot(
      `reader-${theme}.png`,
      { animations: "disabled" },
    );
  });
}
