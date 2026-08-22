/**
 * Photograph the tour in a real browser and report what is on screen.
 *
 * Every serious defect in this viewer so far -- storeys that hid their own
 * geometry, ceilings that could not be switched off, boxes wound inside out,
 * an overhead camera the controls swung away from -- passed the unit tests and
 * was obvious in one screenshot. This is the check that opens the page.
 *
 *   node scripts/tour_snapshot.mjs [url] [outputDirectory]
 *
 * Exits non-zero on a console error, a failed request or a scene that never
 * reports ready. `favicon.ico` is ignored: the dev server does not serve one.
 */
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const url = process.argv[2] ?? "http://localhost:5173/tour";
const out = process.argv[3] ?? "tour-snapshots";
const floors = ["Basement", "First floor", "Second floor", "Third floor"];

await mkdir(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium",
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 820 } });

const problems = [];
const ignorable = (target) => target.includes("favicon.ico");
page.on("console", (message) => {
  if (message.type() === "error" && !ignorable(message.location().url ?? "")) {
    problems.push(`console: ${message.text()}`);
  }
});
page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
page.on("requestfailed", (request) => {
  // React's development double-render aborts the first manifest fetch on
  // purpose; an abort is the cleanup working, not a broken request.
  const reason = request.failure()?.errorText ?? "";
  if (reason !== "net::ERR_ABORTED" && !ignorable(request.url())) {
    problems.push(`request failed: ${request.url()} ${reason}`);
  }
});
page.on("response", (response) => {
  if (response.status() >= 400 && !ignorable(response.url())) {
    problems.push(`http ${response.status()}: ${response.url()}`);
  }
});

await page.goto(url, { waitUntil: "networkidle", timeout: 180000 });
await page.waitForSelector("canvas", { timeout: 60000 });
await page
  .waitForFunction(() => !document.querySelector(".tour-stage__loading"), null, { timeout: 180000 })
  .catch(() => problems.push("the scene never reported ready"));

const stage = page.locator(".tour-stage");
await stage.scrollIntoViewIfNeeded();

let taken = 0;
async function shot(name) {
  await page.waitForTimeout(2200);
  taken += 1;
  const file = `${out}/${String(taken).padStart(2, "0")}-${name}.png`;
  await stage.screenshot({ path: file });
  console.log("shot", file);
}

async function visibleStoreyNodes() {
  return page.evaluate(() => {
    const scene = window.__hvScene;
    if (!scene) return ["no scene handle -- is this a development build?"];
    const shown = [];
    scene.traverse((node) => {
      if (!node.name.startsWith("storey_") || node.name.split("_").length > 3) return;
      let visible = node.visible;
      for (let above = node.parent; above && visible; above = above.parent) visible = above.visible;
      if (visible) shown.push(node.name);
    });
    return shown;
  });
}

await shot("whole-house");
console.log("  showing:", (await visibleStoreyNodes()).join(", "));

for (const floor of floors) {
  const button = page.locator(".tour-storey").filter({ hasText: floor }).first();
  if ((await button.count()) === 0) {
    problems.push(`no floor button for ${floor}`);
    continue;
  }
  await button.click();
  await shot(floor.replace(/\s+/g, "-").toLowerCase());
  console.log("  showing:", (await visibleStoreyNodes()).join(", "));

  await page.getByRole("button", { name: "Overhead" }).click();
  await shot(`${floor.replace(/\s+/g, "-").toLowerCase()}-overhead`);
}

await page.locator(".tour-storey").filter({ hasText: "Whole house" }).first().click();
await page.getByRole("button", { name: "Overhead" }).click();
await shot("whole-house-overhead");

// Move here has to land the camera somewhere sensible, at eye height, on the
// floor that was clicked -- it was inert on the traced model until recently.
await page.locator(".tour-storey").filter({ hasText: "First floor" }).first().click();
await page.waitForTimeout(1500);
await page.getByRole("button", { name: "Move here" }).click();
await stage.scrollIntoViewIfNeeded();
await page.waitForTimeout(400);
// The stage is taller than the viewport, so a fraction of its own height can
// land off screen and the click never reaches the canvas at all. Several spots
// are tried because a click has to find open floor, not a wall or a worktop.
const box = await stage.boundingBox();
const viewport = page.viewportSize();
let landed = false;
for (const [across, down] of [[0.5, 0.5], [0.42, 0.45], [0.58, 0.55], [0.5, 0.38], [0.46, 0.6]]) {
  await page.mouse.click(
    box.x + box.width * across,
    Math.min(box.y + box.height * down, viewport.height - 60),
  );
  await page.waitForTimeout(500);
  const now = (await page.locator(".tour-mode-status").textContent()) ?? "";
  if (!now.startsWith("Move here")) {
    landed = true;
    console.log(`  move here accepted ${across}, ${down}`);
    break;
  }
}
if (!landed) problems.push("Move here accepted none of the five spots tried on the plan");
await shot("moved-here");

console.log(
  problems.length ? `\nPROBLEMS\n${problems.join("\n")}` : "\nno console errors, no failed requests",
);
await browser.close();
if (problems.length) process.exitCode = 1;
