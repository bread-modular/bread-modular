# silkscreen-editor

A purpose-built dev tool for editing the **silkscreen text** of Bread Modular
tscircuit PCBs (plan: `../../docs/silkscreen-editor-plan.md`). It renders only the
board outline + silkscreen — never traces, vias, pads or courtyards — and never
routes (every compile runs the eval with `routingDisabled: true`, mirroring
`tsci build --routing-disabled`).

Status: **M1 (inventory CLI) + M2 (viewer) + M3 (interactive editing) + M4 (source write-back) + e2e (Playwright, 5 tests)**. M5 polish (ref-designator extras, multi-module polish) remains.

## Single-entry mode

The editor works on exactly **one `.circuit.tsx` per process**, chosen at
startup via the `SILK_ENTRY` env var. There is no module picker and no
`?module=` params — the UI auto-loads the entry on boot.

```bash
# UI + /api (vite :5175) for one file — the path becomes SILK_ENTRY
./silk.sh dev ../src/drive/drive.circuit.tsx   # from silkscreen-editor/
npm run silk -- ../src/drive/drive.circuit.tsx # from ts-modules/

# M1 — silkscreen inventory as JSON for one file
./silk.sh run inventory ../src/drive/drive.circuit.tsx | jq
npm run silk:inventory -- ../src/drive/drive.circuit.tsx

# e2e — Playwright boots its own server against the drive fixture copy
npx playwright test                            # all 5 tests, one worker
npx playwright test -g "overlay covers"        # a single test
```

`silk.sh` puts `../node_modules/.bin` (bun, tsci) on `PATH`, re-applies
the KiCad silkscreen-font patch (idempotent), installs this package's deps on
first run, claims the first `*.circuit.tsx` arg as `SILK_ENTRY` (stripping it
so vite never sees it as a positional `[root]`), defaults
`SILK_TS_MODULES_DIR` to the real `ts-modules`, then executes
`bun run <script>` inside this package.

`SILK_TS_MODULES_DIR` override: the circuit package whose `node_modules`
(KiCad-font-patched) the worker evals against. Defaults to three levels above
the entry (`…/ts-modules/src/<m>/<f>` → `…/ts-modules`); entries living
elsewhere (e.g. `e2e/fixtures/`) must set it — the e2e webServer does.

## API (vite middleware)

| Endpoint | Result |
|---|---|
| `GET /api/entry` | `{ ok, entry, name, sourcePath }` — the single file under edit |
| `GET /api/inventory` | `{ ok, entry, name, items, counts, board, frameLabels }` |
| `GET /api/compile` | same + `svg` (silkscreen-only underlay) |
| `POST /api/apply` | `{ expectedEntryMtimeMs, edits }` → M4 write-back (see below) |

### Item shape (M1 inventory)

```jsonc
{
  "fingerprint": "label|CV1|-8.040|26.670|top",  // kind|text|x@3dp|y@3dp|layer — stable across recompiles
  "kind": "label",            // "label" (pcb_component_id null) | "ref" (linked designator)
  "ref": null,                // "R4" when kind === "ref"
  "text": "CV1",
  "x": -8.04, "y": 26.67,     // mm, pcb coords (anchor_position), Y up, board centered 0,0
  "rotation": 0,              // ccw_rotation, degrees
  "anchor": "center",         // anchor_alignment
  "fontSize": 1,              // font_size mm
  "layer": "top",
  "readonly": true,           // frame-computed labels (module-frame)
  "hidden": false, "dirty": false
}
```

`readonly` = lib/frame-owned (module-frame bus/name/version labels, computed
positions) — these render as **ghosts**: visible for context, never draggable,
eye button disabled. Every other item carries an `owner` claim
(`server/ownership.ts`) that the write-back dispatches on:

| owner | owns the position | move writes | hide writes |
|---|---|---|---|
| `entry` | literal `<silkscreentext>` in the module entry | `pcbX`/`pcbY` | `pcbStyle` visibility |
| `rv09` | `<RV09Pot name="…">` call site (caption/designator/value) | caption only → `labelDx`/`labelDy` | `hideLabel`/`hideDesignator`/`hideValue` |
| `ref` | `name="…"` component in the entry | `pcbSx` `"& silkscreentext"` offset | `pcbStyle` visibility |
| `frame` | lib/frame — ghost, refused on save | — | — |

## How compiling works

The vite middleware (`server/api.ts`) spawns a **bun child**
(`server/compile-worker.ts`) which mirrors `@tscircuit/cli`'s
`generateCircuitJson` eval path exactly:

1. resolve + import `react` and `tscircuit` from the **user-land
   `node_modules`** (`SILK_TS_MODULES_DIR` — the KiCad-font-patched copies;
   the KiCad glyph patch lives in `@tscircuit/alphabet`, applied by
   `../../scripts/kicad-font/apply-kicad-font-patch.mjs`),
2. `getPlatformConfig({ routingDisabled: true })` from `@tscircuit/eval/platform-config`,
3. native `import(pathToFileURL(SILK_ENTRY))` — bun transpiles the TSX, so
   `../../lib` resolves like `tsci build` (fixture copies reach the real lib
   via the `e2e/lib → ../../lib` symlink),
4. `RootCircuit.add(createElement(Component))` + render-until-done loop,
5. filter the circuit json to **board + silkscreen text/line/rect/circle/path +
   plated holes** (traces, vias, pads, courtyards, copper, source/schematic are
   dropped) and render the underlay with
   `convertCircuitJsonToPcbSvg(filtered, { layer: "top", … })` from
   `circuit-to-svg` (also from user-land via a `file:` dep).

The worker writes its result to a temp **file** (not stdout) so eval logs can
never corrupt the JSON payload.

## mm ⇄ px transform

`circuit-to-svg` renders onto a fixed 800×600 canvas at a uniform scale, Y
flipped. `src/transform.ts` derives everything deterministically from the
`<rect class="pcb-boundary">` + board mm size:

```
unitsPerMm = boundary.w / board.width
svgX = boundary.x + (mmX + boardW/2) · unitsPerMm
svgY = boundary.y + (boardH/2 − mmY) · unitsPerMm      // Y flip
```

The `.overlay` div covers exactly the rendered `<svg>` border box (measured at
runtime) — handles are `mmToPx(item) − svgRect.origin`, so they sit on the
underlay ink.

## Layout

```
server/
  paths.ts           SILK_ENTRY resolution (resolveEntryPath/entryDisplayName/tsModulesDirFor)
  compile-worker.ts  bun child: TSX → circuit json → items + underlay svg
  compile.ts         spawn wrapper (used by API + CLI)
  silkscreen.ts      circuit-json filter + item adapter + frame-label parse
  entry-parse.ts     ts-morph entry readers (frameLabels / RV09 sites / silkTexts / namedComponents)
  ownership.ts       owner classification (entry/rv09/ref/frame)
  inventory-cli.ts   M1 CLI
  api.ts             vite middleware plugin (+ POST /api/apply write-back)
  patch.ts           M4 ts-morph TSX patch engine
src/
  App.tsx            auto-load entry + layout + save flow (no picker)
  components/BoardCanvas.tsx   underlay svg + handles overlay + drag/nudge
  components/ItemPanel.tsx     floating control panel for the selected item
  components/ItemList.tsx      Labels / Ref designators side panel
  api.ts model.ts transform.ts styles.css
e2e/
  silkscreen.spec.ts 5 Playwright tests (drive fixture)
  fixture.ts         FIXTURE_ENTRY + webServer env
  fixtures/drive/    byte-identical drive.circuit.tsx copy (disposable)
  lib -> ../../lib   symlink so the fixture's ../../lib import resolves
```

## Editing (M3)

- The editor does **move + show/hide only**. Click a handle (or a side-panel
  row) to select — a floating panel opens with position x/y in mm and a
  visible/hidden toggle. Ghosts (`🔒`) render read-only.
- Drag a handle to move it (px ⇄ mm via the board transform; the item's mm
  position updates live; the footprint itself never moves). Arrow keys nudge
  0.1 mm (Shift = 0.5 mm). The component footprint NEVER moves — only text.
- Edits are session-local (`✳` markers, per-item reset / reset all).

## Write-back (M4)

`Save` → confirm modal → `POST /api/apply` patches the entry `.circuit.tsx`
with ts-morph (never string search), then recompiles and verifies every edit in
the fresh circuit json; ANY failure restores the original bytes.

| Edit | Source patch |
|---|---|
| Move a custom `<silkscreentext>` | set `pcbX`/`pcbY` literals |
| Hide (entry label or ref) | add/merge `pcbStyle={{ silkscreenTextVisibility: "hidden" }}` |
| Show again | remove the visibility prop (and empty `pcbStyle`) |
| Move an RV09Pot caption | set `labelDx`/`labelDy` on the `<RV09Pot>` call site |
| Hide an RV09Pot caption/designator/value | set `hideLabel`/`hideDesignator`/`hideValue` on the call site |
| Show again | remove the hide prop |
| Move a ref designator | merge `pcbSx={{ "& silkscreentext": { pcbX, pcbY } }}` on the owning component (component-local offset = R(−θ)·(target − center)) |

Text/rotation/anchor/fontSize edits are out of scope (move + show/hide only) —
change those in the module source directly. Ref renames are refused (netlist
identity). Computed (non-literal) attributes are never touched.
Afterwards run `./build.sh <module>` to regenerate gerbers/SVGs — the build's
placement signature excludes silkscreen, so routing is reused untouched.

## e2e (Playwright)

`e2e/silkscreen.spec.ts` (config `playwright.config.ts`, single worker — saves
mutate the fixture file). The dev server boots itself per run via `webServer`
with `SILK_ENTRY` = the disposable drive fixture copy, so real module sources
are never touched; the fixture is still snapshotted + restored around tests:

1. overlay covers the underlay svg box exactly; every handle sits on the board
2. drag the AUDIO entry label → save → `pcbX` patched + recompiled position
3. move the RV2 "OD1" caption via the panel → save → `labelDx` on the call site
4. hide GAIN → save → caption gone; show → save → caption back
5. frame-owned ghosts (INPUT) are not editable (eye disabled, panel read-only)

Drive fixture cross-check: inventory reports 36 texts (16 refs, 20 labels) —
exactly the `pcb_silkscreen_text` count in `src/drive/drive.routed.json`.

Refresh the fixture copy after drive changes (must stay byte-identical):
`cp ../../src/drive/drive.circuit.tsx e2e/fixtures/drive/drive.circuit.tsx`
