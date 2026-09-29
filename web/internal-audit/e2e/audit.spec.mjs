import { expect, test } from "@playwright/test";

test("scrubs a representative mortgage and exposes both ledger sides", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Follow the mortgage/ })).toBeVisible();
  await expect(page.locator("#month-label")).toHaveText("2025-01");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.locator("#month-label")).toHaveText("2025-02");
  await page.getByRole("button", { name: "Inspect ledger entry" }).click();
  await expect(page.locator("#event-detail")).toContainText("CPI_REVALUATION");
  await expect(page.locator("#event-detail")).toContainText("borrower liability");
  await expect(page.locator("#event-detail")).toContainText("lender asset");
  await expect(page.locator("#event-detail code").first()).toContainText(
    "micro:2025-02:cpi-revaluation",
  );
});
