/**
 * M1 — headless inventory CLI (single-entry mode).
 *
 *   SILK_ENTRY=<path to a .circuit.tsx> bun server/inventory-cli.ts
 *   ./silk.sh run inventory ../src/drive/drive.circuit.tsx   (from silkscreen-editor/)
 *   npm run silk:inventory -- ../src/drive/drive.circuit.tsx (from ts-modules/)
 *
 * Prints the silkscreen item list (JSON array) on stdout. Cross-check against
 * the module's .routed.json: pcb_silkscreen_text count and the
 * pcb_component_id-linked refs must match exactly.
 */
import { compileEntry } from "./compile";
import { entryDisplayName, resolveEntryPath } from "./paths";

const entry = resolveEntryPath();
const result = await compileEntry();
if (!result.ok) {
  console.error(`!! compile failed for '${entry}':\n${result.error}`);
  process.exit(1);
}

console.error(
  `==> ${entryDisplayName(entry)}: ${result.counts?.silkscreenTexts} silkscreen texts ` +
    `(${result.counts?.refs} ref-linked, ${result.counts?.labels} labels), ` +
    `board ${result.board?.width}x${result.board?.height}mm` +
    ` — kept ${result.counts?.keptElements}/${(result.counts?.keptElements ?? 0) + (result.counts?.droppedElements ?? 0)} elements`,
);

console.log(JSON.stringify(result.items, null, 2));
