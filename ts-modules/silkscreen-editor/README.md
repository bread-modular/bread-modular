# silkscreen-editor

A purpose-built dev tool for editing the **silkscreen text** of Bread Modular
tscircuit PCBs (plan: `../../docs/silkscreen-editor-plan.md`). It renders only the
board outline + silkscreen — never traces, vias, pads or courtyards — and never
routes (every compile runs the eval with `routingDisabled: true`, mirroring
`tsci build --routing-disabled`).

Status: **M1 (inventory CLI) + M2 (viewer) + M3 (interactive editing) + M4 (source write-back)**. M5 polish (ref-designator extras, multi-module polish) remains.

## Quickstart

```bash
# M1 — silkscreen inventory as JSON (defaults to 8bit)
./silk.sh run inventory 8bit | jq            # from silkscreen-editor/
./silk.sh run inventory blank
npm run silk:inventory -- 8bit               # from ts-modules/

# M2 — viewer (UI + /api middleware in one vite dev server)
./silk.sh dev                                # from silkscreen-editor/
npm run silk                                 # from ts-modules/
# open http://localhost:5175 and pick a module
```

`silk.sh` puts `../node_modules/.bin` (bun, tsci) on `PATH`, re-applies
the KiCad silkscreen-font patch (idempotent), installs this package's deps on
first run, then executes `bun run <script>` inside this package.

## API (vite middleware)

| Endpoint | Result |
|---|---|
| `GET /api/modules` | `{ ok, modules: string[] }` — dirs under `ts-modules/src/` with a `<m>.circuit.tsx` |
| `GET /api/inventory?module=8bit` | `{ ok, module, items, counts, board, frameLabels }` |
| `GET /api/compile?module=8bit` | same + `svg` (silkscreen-only underlay) |
| `POST /api/apply` | M4 write-back (see below) |

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

`readonly` = frame-owned labels: `INPUT` / `OUTPUT` / `BREAD` / `MODULAR`, the
module `name`/`version`, and `inputLabels`/`outputLabels` strings **that sit on
the frame's bus label column** (`x = ±(halfW − 7.2)`, the `BUS_LABEL_INSET`
from `lib/module-frame.tsx`). The column check keeps a same-named module-authored
caption (e.g. the RV09Pot "CV1" label) editable. Refs are editable (M5 handles
them via the hide+insert pattern).

## How compiling works

The vite middleware (`server/api.ts`) spawns a **bun child**
(`server/compile-worker.ts`) which mirrors `@tscircuit/cli`'s
`generateCircuitJson` eval path exactly:

1. resolve + import `react` and `tscircuit` from **`../node_modules`**
   (the KiCad-font-patched user-land — the KiCad glyph patch lives in
   `@tscircuit/alphabet`, applied by `../../scripts/kicad-font/apply-kicad-font-patch.mjs`),
2. `getPlatformConfig({ routingDisabled: true })` from `@tscircuit/eval/platform-config`,
3. native `import(pathToFileURL(<m>.circuit.tsx))` — bun transpiles the TSX, so
   `../lib` resolves against `ts-modules/` (same as `tsci build`),
4. `RootCircuit.add(createElement(Component))` + render-until-done loop,
5. filter the circuit json to **board + silkscreen text/line/rect/circle/path +
   plated holes** (traces, vias, pads, courtyards, copper, source/schematic are
   dropped) and render the underlay with
   `convertCircuitJsonToPcbSvg(filtered, { layer: "top", … })` from
   `circuit-to-svg` (also from `../node_modules` via a `file:` dep).

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

## Layout

```
server/
  paths.ts           ts-modules resolution (SILK_TS_MODULES_DIR override)
  compile-worker.ts  bun child: TSX → circuit json → items + underlay svg
  compile.ts         spawn wrapper (used by API + CLI)
  silkscreen.ts      circuit-json filter + item adapter + frame-label parse
  inventory-cli.ts   M1 CLI
  api.ts             vite middleware plugin (+ POST /api/apply write-back)
  patch.ts           M4 ts-morph TSX patch engine
src/
  App.tsx            module picker + layout + save flow
  components/BoardCanvas.tsx   underlay svg + handles overlay + drag/nudge
  components/ItemPanel.tsx     floating control panel for the selected item
  components/ItemList.tsx      Labels / Ref designators side panel
  api.ts model.ts transform.ts styles.css
```

## Editing (M3)

- Click a handle (or a side-panel row) to select — a floating panel opens with
  editable text, position x/y in mm, rotation, anchor (9-point), fontSize and a
  visible/hidden toggle. Frame-owned labels (`🔒`) render read-only.
- Drag a handle to move it (px ⇄ mm via the board transform; the item's mm
  position updates live; the footprint itself never moves). Arrow keys nudge
  0.1 mm (Shift = 0.5 mm). The component footprint NEVER moves — only text.
- Edits are session-local (`✳` markers, per-item reset / reset all).

## Write-back (M4)

`Save` → confirm modal → `POST /api/apply` patches the module's `.circuit.tsx`
with ts-morph (never string search), then recompiles and verifies every edit in
the fresh circuit json; ANY failure restores the original bytes.

| Edit | Source patch |
|---|---|
| Move a custom `<silkscreentext>` | set `pcbX`/`pcbY` literals |
| Rotate / re-anchor / resize it | set `pcbRotation` / `anchorAlignment` / `fontSize` literals |
| Edit its text | set the `text` literal |
| Hide (label or ref) | add/merge `pcbStyle={{ silkscreenTextVisibility: "hidden" }}` |
| Show again | remove the visibility prop (and empty `pcbStyle`) |
| Move a ref designator | merge `pcbSx={{ "& silkscreentext": { pcbX, pcbY } }}` on the owning component (component-local offset = R(−θ)·(target − center)) |

Ref renames and rotation/anchor/fontSize of auto refs are refused (netlist
identity / frame-owned). Computed (non-literal) attributes are never touched.
Afterwards run `./build.sh <module>` to regenerate gerbers/SVGs — the build's
placement signature excludes silkscreen, so routing is reused untouched.
