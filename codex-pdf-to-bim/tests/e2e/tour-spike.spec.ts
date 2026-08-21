import { expect, test } from "@playwright/test";


test("homeowner can move, walk, recover, and frame the quality-spike room", async ({ page }) => {
  test.setTimeout(120_000);
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });

  const loadStarted = Date.now();
  await page.goto("/tour-spike");
  await expect(page.getByRole("heading", { name: "Explore the proposed kitchen and family room" })).toBeVisible();
  await expect(page.locator(".tour-stage__loading")).toBeHidden({ timeout: 60_000 });
  const usableAfterMs = Date.now() - loadStarted;
  test.info().annotations.push({ type: "headless-load-ms", description: String(usableAfterMs) });

  await expect(page.getByText("Quality spike · visual staging")).toBeVisible();
  await expect(page.getByRole("button", { name: "Orbit" })).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "Move here" }).click({ force: true });
  await expect(page.getByRole("status", { name: "Tour mode" })).toContainText("Move here mode");
  const canvas = page.locator("canvas");
  const canvasBounds = await canvas.boundingBox();
  if (!canvasBounds) throw new Error("The tour canvas did not have a visible size.");
  await canvas.click({
    force: true,
    position: {
      x: canvasBounds.width * 0.36,
      y: canvasBounds.height * 0.68,
    },
  });
  await expect(page.getByRole("button", { name: "Orbit" })).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "Walk" }).click({ force: true });
  await expect(page.getByRole("button", { name: "Exit walk" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Tour mode" })).toContainText("Walk mode");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("status", { name: "Tour mode" })).toContainText("Orbit mode");

  await page.getByRole("button", { name: "Overhead" }).click({ force: true });
  await expect(canvas).toBeVisible();
  await page.getByRole("button", { name: "Reset" }).click({ force: true });
  await expect(page.getByRole("button", { name: "Orbit" })).toHaveAttribute("aria-pressed", "true");

  expect(browserErrors).toEqual([]);
});
