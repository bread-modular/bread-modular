/**
 * Compile worker — a bun child process that turns a module's .circuit.tsx into
 * silkscreen items + a silkscreen-only underlay SVG.
 *
 * Why a child process (not in-process)?
 *   1. The eval must import react/tscircuit from ts-modules/node_modules
 *      (user-land) — NOT from this package — so the KiCad font patch and the
 *      exact package versions used by `tsci build` apply (plan §2.1).
 *      Importing @tscircuit/eval's CircuitRunner in-process would resolve bare
 *      imports against a CDN and lose the patched font.
 *   2. Isolation: eval executes arbitrary module code; a crash takes down only
 *      this worker, not the vite dev server.
 *
 * The exact eval path mirrors @tscircuit/cli's generateCircuitJson:
 *   - createRequire(<ts-modules>/noop.js).resolve → import react + tscircuit
 *   - globalThis.React = React
 *   - platform = getPlatformConfig({ routingDisabled: true })
 *   - native import(pathToFileURL(entry)) — bun transpiles the TSX
 *   - RootCircuit.add(createElement(Component)); render until done
 *   - getCircuitJson()
 *
 * Protocol: argv --out <result.json>; the entry comes from SILK_ENTRY
 * (server/paths.ts). The parent reads the result FILE (not stdout) so stray
 * eval logs can never corrupt the payload.
 */
import { writeFileSync, statSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";
import {
  extractFrameLabels,
  filterSilkscreenCircuitJson,
  itemsFromCircuitJson,
  type SilkBoard,
} from "./silkscreen";
import { buildEntryContext } from "./entry-parse";
import {
  entryDisplayName,
  resolveEntryPath,
  tsModulesDirFor,
} from "./paths";

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

async function fail(outPath: string, message: string): Promise<never> {
  writeFileSync(
    outPath,
    JSON.stringify({ ok: false, error: message }, null, 2),
  );
  console.error(message);
  process.exit(1);
}

async function main() {
  const outPath = arg("--out");
  if (!outPath) throw new Error("missing --out <result.json>");
  // single-entry mode: which .circuit.tsx we compile comes from SILK_ENTRY
  const entry = resolveEntryPath();
  const entryName = entryDisplayName(entry);
  const tsModulesDir = tsModulesDirFor(entry);

  // --- user-land imports (ts-modules/node_modules — the patched copies) ---
  const userRequire = createRequire(path.join(tsModulesDir, "noop.js"));
  const React = await import(userRequire.resolve("react"));
  (globalThis as any).React = React.default ?? React;
  const tscircuit: any = await import(userRequire.resolve("tscircuit"));
  // @tscircuit/eval's exports map only has "import" conditions — resolve the
  // platform-config module by absolute path (CJS require.resolve would fail).
  const { getPlatformConfig } = await import(
    pathToFileURL(
      path.join(
        tsModulesDir,
        "node_modules/@tscircuit/eval/dist/platform-config/getPlatformConfig.js",
      ),
    ).href
  );
  const { convertCircuitJsonToPcbSvg } = await import(
    pathToFileURL(userRequire.resolve("circuit-to-svg")).href
  );

  // --- eval (routing disabled — the editor never routes; plan §2.1) ---
  const platform = getPlatformConfig({ routingDisabled: true } as any);
  const MainComponent = await import(pathToFileURL(entry).href);
  const Component =
    MainComponent.default ??
    Object.keys(MainComponent)
      .filter((k) => k[0] === k[0].toUpperCase())
      .map((k) => (MainComponent as any)[k])[0];
  if (!Component) {
    await fail(outPath, `no exported component in ${entry}`);
  }

  const runner = new tscircuit.RootCircuit({ platform });
  const R = (globalThis as any).React;
  runner.add(R.createElement(Component));
  runner.render();
  while (!runner.isDoneRendering()) {
    await new Promise((r) => setTimeout(r, 100));
    runner.render();
  }
  const circuitJson: any[] = await runner.getCircuitJson();

  // --- silkscreen view-model + underlay ---
  const frameLabels = extractFrameLabels(entry);
  const entryCtx = buildEntryContext(entry);
  const items = itemsFromCircuitJson(circuitJson, frameLabels, entryCtx);
  const filtered = filterSilkscreenCircuitJson(circuitJson);
  const svg: string = convertCircuitJsonToPcbSvg(filtered as any, {
    layer: "top",
    shouldDrawErrors: false,
    shouldDrawRatsNest: false,
    shouldDrawWarnings: false,
  } as any);

  const boardElem = circuitJson.find((e) => e?.type === "pcb_board");
  const board: SilkBoard = {
    width: boardElem?.width ?? 0,
    height: boardElem?.height ?? 0,
    center: boardElem?.center ?? { x: 0, y: 0 },
  };

  // mtime snapshot — the /api/apply write-back refuses to save if the source
  // changed on disk since this compile (plan §8 "Concurrent edits").
  const entryMtimeMs = statSync(entry).mtimeMs;

  writeFileSync(
    outPath,
    JSON.stringify(
      {
        ok: true,
        module: entryName,
        entry,
        sourcePath: entry,
        entryMtimeMs,
        board,
        frameLabels,
        items,
        counts: {
          silkscreenTexts: items.length,
          refs: items.filter((i) => i.kind === "ref").length,
          labels: items.filter((i) => i.kind === "label").length,
          keptElements: filtered.length,
          droppedElements: circuitJson.length - filtered.length,
        },
        svg,
      },
      null,
      2,
    ),
  );
}

main().catch(async (err) => {
  const outPath = arg("--out") ?? path.join(process.cwd(), "silk-error.json");
  await fail(outPath, err?.stack ?? String(err));
});
