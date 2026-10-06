# Supported subset v1 — deliberately conservative

These are **admission plus acceptance gates**, not a promise every admitted board
will route successfully. Unsupported native DSN translations fail before the
engine runs. No all-board or manufacture-safety claim.

## Admitted context

- Installed **KiCad/CLI/bindings 10.0.6**, matching system `/usr/bin/python3`,
  Linux x86_64, existing Bubblewrap and previously verified pinned runtime.
- One same-stem `.kicad_pcb`, `.kicad_pro`, `.kicad_sch`; `.kicad_dru` optional.
  Single-sheet schematic with embedded symbols; schematic hierarchy not admitted.
- Frozen native local footprint libraries/tables, optional local symbol libraries
  and STEP/STP/WRL models. URI references may use `${KIPRJMOD}/` or canonical
  relative paths (`Local.pretty`, `../Libraries/Local.pretty`), resolved against
  the PCB/project directory and wholly inside the snapshot. No absolute paths,
  unresolved variables, URLs, missing/global/remote authority or link aliases.
- Up to 512 entries, 64 MiB total, 16 MiB per nonempty file. Recognized native
  project/library/model extensions and library tables only. No backups/logs,
  extra PCB/project authorities, special files, symlinks (even internal), hardlinks
  or source/output aliases. Source snapshot and approval plan are immutable.

## Admitted PCB/rules

- Exactly F.Cu/B.Cu signal layers; one closed four-line **rectangular outline**,
  no cutouts. Orthogonal footprint/pad orientation, subject to exact native DSN
  placement/image-pin translation checks; an unrecognized native pin syntax fails.
- Ordinary circle/rect/oval copper pads: SMD on one side or PTH with centered round
  drills. Unique nonempty copper pad numbers. No pad/footprint clearance, padstack,
  mask/paste/thermal/teardrop/net-tie overrides or unknown pad extensions.
- Straight tracks only, ordinary uniform **through vias** using nominal scalar
  diameter/drill on both layers. Existing nonnominal vias fail closed. Native
  forced F.Cu-SMD → B.Cu-SMD roundtrip has been exercised (one actual via), as has
  protecting an existing via on a completed non-authorized net.
- **One Default netclass**, with explicit positive width/gap/via diameter/drill
  scalars and project minima covered by those nominal values. No netclass
  assignments/patterns are rewritten or admitted. Copper-edge minimum is a
  positive whole-micrometre scalar, mirrored in the engine's **verified effective
  settings**; KiCad's DSN boundary alone is not called an edge-rule translation.
- `.dru` version 1: only **unconditional min-only** `track_width`, `clearance`,
  `via_diameter`, `hole_size`, expressed in mm and no stronger than checked native
  DSN nominal scalars. No conditions, selectors/layers, max/opt, altered severity,
  differential/length/skew or other constraints. Unknown active copper project
  constraints fail closed. Existing nonrouting fabrication/display constraints
  are preserved and native-DRC checked, not claimed as router translations.
- Native DSN is inspected per input for units, layers/boundary, exact scalar
  class/global width/gap, net memberships, placements, image pins/pad shapes/sizes,
  via diameter/drill naming/padstack and all protected/locked `type fix` geometry.
  Native DSN's lower `smd_smd` pad-pair exception is accepted **only with invariant
  pad geometry already passing baseline native DRC**; no DSN rule is rewritten
  to hide it. No other lower typed clearance is admitted. Final native DRC remains
  authority; this is not lossless KiCad-rule translation.

## Explicitly not admitted / not implemented

- **All board/footprint groups**, locked or unlocked (`GROUP_UNSUPPORTED`).
  Inherited group locks are not modeled; item `IsLocked` alone is insufficient.
- **All zones and keepouts in general flow**, even rectangles. The historical
  fixture's plane/keepout evidence is not generalized. Zone definition invariants
  and refill hooks remain, but v1 never claims ordinary-zone translation support.
- Other stackups/layers, blind/micro/nonuniform vias, arcs, custom/roundrect/trapezoid
  pads, slotted/offset drills, copper graphics, tuned/generated routing, active
  unsupported minima/overrides, exclusions or explicitly ignored rule severities.
- Differential/length rules and paired `_P/_N` or `+/-` differential-looking names
  are conservatively blocked (false positives require native review, not waiver).
  Dormant Default class diff-pair UI scalar defaults are not differential routing.
- Automatic placement, native push/shove scripting, length tuning, electrical/
  return-path/thermal/current/mechanical/manufacturing signoff. **Use PCB Editor
  natively** for unsupported or critical work; do not delete rules to pass admission.

Freerouting exclusions operate on **classes**, not arbitrary chosen nets. The
explicit net list defines only which unlocked copper may be replaced. Routing
must finish all planned opens and cannot touch any protected-net copper, including
new branches. No silent best-effort, partial acceptance or selected-net CLI claim.
