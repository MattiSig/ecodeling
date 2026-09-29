import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

for (const theme of ["dark", "light"]) {
  test(`CV-owned route: first-reader handoff and ${theme} host embedding`, async ({
    page,
  }) => {
    const errors: string[] = [];
    const apiRequests: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => {
      if (request.url().includes("/api/v1/")) apiRequests.push(request.url());
    });
    await page.addInitScript(
      (theme) => localStorage.setItem("theme", theme),
      theme,
    );
    await page.goto("/work/ecodeling");
    const component = page.locator("ecodeling-experience");
    await expect(
      component.getByRole("tab", { name: "Article", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await expect(
      component.getByRole("tab", { name: "Laboratory", exact: true }),
    ).toHaveCount(0);
    const reader = component.locator(".article-scroll");
    for (const [label, mode, month] of [
      ["View shock in Story", "Story", "3"],
      ["Inspect revaluation in Explore", "Explore", "5"],
      ["Compare closing results", "Compare", "17"],
    ] as const) {
      const action = reader.getByRole("button", { name: label, exact: true });
      await action.scrollIntoViewIfNeeded();
      const scroll = await reader.evaluate((el) => el.scrollTop);
      await action.click();
      await expect(
        component.getByRole("tab", { name: mode, exact: true }),
      ).toHaveAttribute("aria-selected", "true");
      await expect(
        component.getByRole("slider", { name: "Simulation month" }),
      ).toHaveValue(month);
      await component
        .getByRole("tab", { name: "Article", exact: true })
        .click();
      await expect
        .poll(() => reader.evaluate((el) => el.scrollTop))
        .toBeCloseTo(scroll, 0);
    }
    await reader.evaluate((el) => {
      el.scrollTop = 0;
    });
    await component.locator(".mode-tabs").scrollIntoViewIfNeeded();
    expect(
      (
        await new AxeBuilder({ page })
          .include("ecodeling-experience")
          .disableRules(["landmark-one-main"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await expect(component.locator(".ready")).toHaveScreenshot(
      `cv-reader-${theme}.png`,
      { animations: "disabled" },
    );
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(page.viewportSize()!.width);
    expect(errors).toEqual([]);
    expect(apiRequests).toEqual([]);
  });
}
