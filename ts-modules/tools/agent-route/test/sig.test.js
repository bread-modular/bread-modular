// sig unit test (§5): a placement nudge inside S2's rect must NOT invalidate
// S1's sig; a nudge inside S1's rect MUST invalidate S1.
//
// Usage: node test/sig.test.js   (exit 0 = pass)
import { loadScanFromCircuitJson } from "../lib/scan.js";
import { buildPlan } from "../lib/plan.js";
import { sigForSection, verifySectionSig } from "../lib/sig.js";
import { distCircuit } from "../lib/constants.js";

const board = process.argv[2] ?? "8bit";
const scan = loadScanFromCircuitJson(board, distCircuit(board));
const { plan } = buildPlan(scan);
if (plan.sections.length < 2) {
  console.log(`SKIP: ${board} planned to ${plan.sections.length} section(s), need >= 2`);
  process.exit(0);
}
const [S1, S2] = plan.sections;
const sig1 = sigForSection(scan, S1);

function nudgedScan(ref, dx, dy) {
  const copy = structuredClone(scan);
  const c = copy.components.find((x) => x.ref === ref);
  if (!c) throw new Error(`no such ref ${ref}`);
  c.center.x += dx;
  c.center.y += dy;
  for (const p of copy.pads) {
    if (p.ref === ref) { p.x += dx; p.y += dy; }
  }
  return copy;
}

// find a member ref inside S2's rect but outside S1's rect (and vice versa)
const inRect = (x, y, r) => x >= r.minX && x <= r.maxX && y >= r.minY && y <= r.maxY;
const s2Only = scan.components.find((c) =>
  inRect(c.center.x, c.center.y, S2.rect) && !inRect(c.center.x, c.center.y, S1.rect),
);
const s1Only = scan.components.find((c) =>
  inRect(c.center.x, c.center.y, S1.rect) && !inRect(c.center.x, c.center.y, S2.rect),
);
if (!s2Only || !s1Only) {
  console.log("SKIP: sections overlap such that no exclusive member exists");
  process.exit(0);
}

let pass = true;
const check = (name, cond) => {
  console.log(`${cond ? "PASS" : "FAIL"}: ${name}`);
  if (!cond) pass = false;
};

check(`baseline S1 sig verifies`, verifySectionSig(scan, S1, sig1).valid);
check(
  `nudge ${s2Only.ref} (+1mm) outside S1 rect keeps S1 valid`,
  verifySectionSig(nudgedScan(s2Only.ref, 1, 0), S1, sig1).valid,
);
check(
  `nudge ${s1Only.ref} (+1mm) inside S1 rect invalidates S1`,
  !verifySectionSig(nudgedScan(s1Only.ref, 1, 0), S1, sig1).valid,
);
process.exit(pass ? 0 : 1);
