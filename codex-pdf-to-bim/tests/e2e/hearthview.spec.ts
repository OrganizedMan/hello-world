import { expect, test } from "@playwright/test";


test("homeowner imports A-1, confirms facts, and explores one geometry", async ({ page }) => {
  const pdfPath = process.env.HEARTHVIEW_GARRIGAN_PDF;
  if (!pdfPath) throw new Error("Set HEARTHVIEW_GARRIGAN_PDF to the four-page Garrigan PDF.");

  await page.goto("/");
  await page.getByLabel("Add plan PDFs").setInputFiles(pdfPath);
  await expect(page.getByRole("heading", { name: "Choose the proposed plan" })).toBeVisible();
  await page.getByRole("button", { name: "Use proposed first floor" }).click();
  await page.getByRole("link", { name: "Review important details" }).click();

  for (let index = 0; index < 5; index += 1) {
    await page.getByRole("button", { name: "Confirm and continue" }).click();
  }
  await expect(page.getByRole("heading", { name: "Your plan details are confirmed" })).toBeVisible();
  await page.getByRole("link", { name: "Go to 3D model" }).click();

  await expect(page.getByText("Ready to view", { exact: true })).toBeVisible();
  const hash = await page.getByTestId("geometry-hash").textContent();
  expect(hash).toBeTruthy();
  await page.getByRole("button", { name: "Kitchen view" }).click();
  await expect(page.getByText("Kitchen camera selected")).toBeAttached();
  await expect(page.getByTestId("geometry-hash")).toHaveText(hash!);
});
