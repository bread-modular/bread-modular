/**
 * M1 — headless inventory CLI.
 *
 *   bun server/inventory-cli.ts <module>        (default: 8bit)
 *   ./silk.sh run inventory 8bit
 *
 * Prints the silkscreen item list (JSON array) on stdout. Cross-check against
 * ts-modules/src/<m>/<m>.routed.json: pcb_silkscreen_text count and the
 * pcb_component_id-linked refs must match exactly.
 */
import { compileModule } from "./compile";

const moduleName = process.argv[2] ?? "8bit";

const result = await compileModule(moduleName);
if (!result.ok) {
  console.error(`!! compile failed for '${moduleName}':\n${result.error}`);
  process.exit(1);
}

console.error(
  `==> ${moduleName}: ${result.counts?.silkscreenTexts} silkscreen texts ` +
    `(${result.counts?.refs} ref-linked, ${result.counts?.labels} labels), ` +
    `board ${result.board?.width}x${result.board?.height}mm` +
    ` — kept ${result.counts?.keptElements}/${(result.counts?.keptElements ?? 0) + (result.counts?.droppedElements ?? 0)} elements`,
);

console.log(JSON.stringify(result.items, null, 2));
