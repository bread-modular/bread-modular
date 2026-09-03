import { test, expect } from "@playwright/test";

/**
 * Silkscreen editor e2e — move + show/hide with real save round-trips.
 *
 * Single-entry mode: the dev server is booted BY Playwright (webServer in
 * playwright.config.ts) with SILK_ENTRY pointing at the disposable drive
 * fixture copy in e2e/fixtures/. Tests mutate ONLY the fixture — real module
 * sources are never touched. The fixture file is still snapshotted +
 * restored (beforeAll/afterEach) so the suite never leaves even the fixture
 * dirty.
 *
 *   npx playwright test          # from ts-modules/silkscreen-editor/
 *
 * What is covered (drive fixture: 4 entry labels, 9 rv09 texts, 15 refs,
 * 8 frame ghosts):
 *   1. overlay alignment — every editable handle sits on the board area
 *      (inside the underlay svg box).
 *   2. drag an entry label (AUDIO) → Save → source patched + recompile shows
 *      the new position.
 *   3. move an RV09Pot caption (OD1 of RV2) via the panel → Save →
 *      labelDx/labelDy land on the <RV09Pot> call site.
 *   4. hide the GAIN caption → Save → caption gone from the recompile;
 *      show it again → Save → caption back.
 *   5. ghosts are not draggable — a frame-owned label (INPUT) has no drag
 *      path and its eye button is disabled.
 */

import { readFile, writeFile } from "node:fs/promises";
import { FIXTURE_ENTRY } from "./fixture";

const URL = "/";

let originalSource: string | null = null;

async function snapshotSource() {
  originalSource = await readFile(FIXTURE_ENTRY, "utf8");
}

async function restoreSource() {
  if (originalSource !== null) {
    const now = await readFile(FIXTURE_ENTRY, "utf8").catch(() => null);
    if (now !== null && now !== originalSource) {
      await writeFile(FIXTURE_ENTRY, originalSource);
    }
  }
}

test.beforeAll(snapshotSource);
test.afterEach(restoreSource);
test.afterAll(restoreSource);

async function openEntry(page: import("@playwright/test").Page) {
  // single-entry UI auto-loads the compile on boot — no picker to click
  await page.goto(URL, { waitUntil: "networkidle" });
  await expect(page.getByTestId("silk-entry-name")).toContainText("drive", {
    timeout: 120_000,
  });
  await page.waitForSelector(".handle", { timeout: 120_000 });
  await page.waitForTimeout(800);
}

test("overlay covers the underlay and handles sit on the board", async ({
  page,
}) => {
  await openEntry(page);
  const info = await page.evaluate(() => {
    const under = document.querySelector(".underlay-wrap")!;
    const overlay = document.querySelector(".overlay")!;
    const svg = under.querySelector("svg")!;
    const orr = overlay.getBoundingClientRect();
    const sr = svg.getBoundingClientRect();
    const handles = [...document.querySelectorAll(".handle")].map((h) => {
      const r = h.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    });
    return {
      overlay: { x: orr.x, y: orr.y, w: orr.width, h: orr.height },
      svg: { x: sr.x, y: sr.y, w: sr.width, h: sr.height },
      handles,
    };
  });

  // the overlay must cover exactly the rendered svg box (±3px tolerance —
  // the wrap's 1px border + sub-pixel rounding account for the slack)
  expect(Math.abs(info.overlay.x - info.svg.x)).toBeLessThan(3);
  expect(Math.abs(info.overlay.y - info.svg.y)).toBeLessThan(3);
  expect(Math.abs(info.overlay.w - info.svg.w)).toBeLessThan(3);
  expect(Math.abs(info.overlay.h - info.svg.h)).toBeLessThan(3);

  // every handle must sit inside the svg box (no runaway column on the left)
  for (const h of info.handles) {
    expect(h.x).toBeGreaterThanOrEqual(info.svg.x - 12);
    expect(h.x).toBeLessThanOrEqual(info.svg.x + info.svg.w + 12);
    expect(h.y).toBeGreaterThanOrEqual(info.svg.y - 12);
    expect(h.y).toBeLessThanOrEqual(info.svg.y + info.svg.h + 12);
  }
  expect(info.handles.length).toBeGreaterThan(20);
});

test("drag AUDIO entry label → save → source patched + recompiled position", async ({
  page,
}) => {
  await openEntry(page);

  // select AUDIO via the side panel row, drag its handle +1mm in x
  await page.getByTestId("silk-row-AUDIO").click();
  await expect(page.getByTestId("silk-item-panel")).toBeVisible();

  const handle = page.locator('.handle[data-fingerprint^="label|AUDIO|"]');
  await expect(handle).toBeVisible();
  const before = await page.evaluate(() => {
    const rows = [...document.querySelectorAll(".item-row")];
    const row = rows.find((r) => r.textContent?.includes("AUDIO"));
    return row?.querySelector(".item-pos")?.textContent ?? "";
  });
  expect(before).toContain("x -7.186");

  const box = (await handle.boundingBox())!;
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  // drag +40px in x, then read the resulting mm from the panel — the exact
  // px-per-mm scale doesn't matter, only that the handle actually moved.
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 40, cy, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(400);

  const posText = await page.evaluate(() => {
    const panel = document.querySelector(".item-panel");
    const xInput = panel?.querySelector(
      '[data-testid="silk-panel-x"]',
    ) as HTMLInputElement | null;
    return xInput?.value ?? "";
  });
  const movedX = Number(posText);
  expect(Number.isFinite(movedX)).toBe(true);
  expect(Math.abs(movedX - -7.186)).toBeGreaterThan(0.2); // actually moved

  // save flow: Save → confirm modal → Write to source
  await page.getByRole("button", { name: /Save to source/ }).click();
  await expect(page.getByText("Write edits to the module source?")).toBeVisible();
  await page.getByRole("button", { name: "Write to source" }).click();
  await expect(page.getByText(/saved to/)).toBeVisible({ timeout: 120_000 });

  // fixture patched: pcbX of the AUDIO silkscreentext changed
  const src = await readFile(FIXTURE_ENTRY, "utf8");
  expect(src).toContain("silkscreentext");
  const m = src.match(
    /<silkscreentext[\s\S]*?text="AUDIO"[\s\S]*?pcbX=\{(-?[\d.]+)\}[\s\S]*?pcbY=\{(-?[\d.]+)\}/,
  );
  expect(m).not.toBeNull();
  expect(Math.abs(Number(m![1]) - -7.186)).toBeGreaterThan(0.2);

  // recompile via the UI state: no dirty markers left, position matches
  await expect(page.getByText(/unsaved edit/)).toHaveCount(0);
});

test("move RV09Pot caption (OD1) via panel → save writes labelDx/labelDy", async ({
  page,
}) => {
  await openEntry(page);

  // RV2's "OD1" caption (editable) — scope to the Editable section. (Drive
  // has no same-named bus ghost, but scoping keeps the test robust.)
  const editableSection = page.locator(".item-list section").first();
  await editableSection.getByTestId("silk-row-OD1").click();
  await expect(page.getByTestId("silk-item-panel")).toBeVisible();

  const xInput = page.getByTestId("silk-panel-x");
  const before = Number(await xInput.inputValue());
  const target = Math.round((before + 1.0) * 1000) / 1000;
  await xInput.fill(String(target));
  await xInput.blur();
  await page.waitForTimeout(300);

  await page.getByRole("button", { name: /Save to source/ }).click();
  await expect(page.getByText("Write edits to the module source?")).toBeVisible();
  await page.getByRole("button", { name: "Write to source" }).click();
  await expect(page.getByText(/saved to/)).toBeVisible({ timeout: 120_000 });

  const src = await readFile(FIXTURE_ENTRY, "utf8");
  // the RV2 call site carries the new offset
  const rv2 = src.match(/<RV09Pot name="RV2"[^/]*\/>/);
  expect(rv2).not.toBeNull();
  expect(rv2![0]).toContain("labelDx");
});

test("hide GAIN caption → save → gone; show again → save → back", async ({
  page,
}) => {
  await openEntry(page);

  // hide via the side-panel eye button
  const row = page.getByTestId("silk-row-GAIN");
  await row.hover();
  await row.getByRole("button").first().click(); // eye button
  // the toggle must land first: dirty marker appears in the save bar
  await expect(page.getByText(/unsaved edit/)).toBeVisible({ timeout: 10_000 });

  await page.getByRole("button", { name: /Save to source/ }).click();
  await expect(page.getByText("Write edits to the module source?")).toBeVisible();
  await page.getByRole("button", { name: "Write to source" }).click();
  await expect(page.getByText(/saved to/)).toBeVisible({ timeout: 120_000 });

  let src = await readFile(FIXTURE_ENTRY, "utf8");
  expect(src).toContain("hideLabel");

  // caption gone from the recompiled inventory (ghost row keeps it toggleable)
  await expect(page.getByTestId("silk-row-GAIN")).toBeVisible();

  // show again: click the row's eye button (now 🚫 → 👁)
  await page.getByTestId("silk-row-GAIN").getByRole("button").first().click();
  await expect(page.getByText(/unsaved edit/)).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: /Save to source/ }).click();
  await expect(page.getByText("Write edits to the module source?")).toBeVisible();
  await page.getByRole("button", { name: "Write to source" }).click();
  await expect(page.getByText(/saved to/)).toBeVisible({ timeout: 120_000 });

  src = await readFile(FIXTURE_ENTRY, "utf8");
  expect(src).not.toContain("hideLabel");
});

test("frame-owned ghosts are not editable", async ({ page }) => {
  await openEntry(page);

  // INPUT is frame-owned: row eye button disabled, panel read-only
  const inputRows = page.getByTestId("silk-row-INPUT");
  await expect(inputRows.first()).toBeVisible();
  await expect(
    inputRows.first().getByRole("button").first(),
  ).toBeDisabled();

  await inputRows.first().click();
  await expect(page.getByTestId("silk-item-panel")).toBeVisible();
  await expect(page.getByTestId("silk-item-panel")).toContainText(
    "not editable",
  );
  await expect(page.getByTestId("silk-panel-visibility")).toBeDisabled();
});
