# Compact verification record

Verified on installed Linux Python **3.14.4**, `pcbnew` build
**10.0.6-10.0.6~ubuntu26.04.1**, `kicad-cli` **10.0.6**.
All circuits/footprints/wrappers are generated under `TemporaryDirectory`;
no released design is loaded, no generated board/native runtime binary is stored
in this directory. No advisor/subagents or commits/merges/pushes used.

## Exact commands

From repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover \
  -s opt/kicad-tools/automation/tests -p test_unit.py -v
KICAD_AUTOMATION_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover \
  -s opt/kicad-tools/automation/tests -p test_native.py -v
```

**13 stdlib tests passed; 13 opt-in real-KiCad test methods passed.** Native test
methods exercise multiple candidate transactions and negative subcases.
Unselected integration methods skip by default; running stdlib tests does not
import pcbnew. No global install is needed.

| Coverage | Verified evidence |
| --- | --- |
| Strict schema | Numeric/bool/non-finite/precision/bounds, unknown nested fields, duplicate JSON keys, UUID/ref syntax/collisions, malformed polygons/via geometry, deferred operations, path normalization |
| Transformations | Front/back native flip, absolute move/rotation, stable ref/pad UUID/net/field identity, untouched routed track preserved; moves yield explicit non-clean drafts |
| Additions | Local electrical footprint matches XML/native parity and routing; non-electrical board-only addition accepted, electrical template rejected for mechanical use |
| Copper | Same-net straight-track branch (original item unchanged), explicit vias + F/B layer transition, foreign-net crossing short/clearance rejection even with draft option |
| Zone/board/text | Native saved filled polygons, closed outline lines, stray single-edge shape rejection, text candidate accepted |
| Protection | Locked footprint, locked graphic child/in-memory pad guard, nested locked ancestor group, locked zone/global-refill rejection, duplicate refs |
| Transactions | Deterministic read-only plans/source hashes, stale ops/rules, output collision/symlink, source-hardlinked candidate rejection, injected post-stage worker failure and real subprocess nonzero/stderr, no failure completion marker |
| Checks | Actual native XML/ERC/all-severity DRC/refill/save/reload, strict final parity/open/short gates, identity deltas rather than totals, draft CLI exit 1 |
| Relocation | Absolute external library/Sheetfile bindings rebound relative, repeated hierarchical sheet parity, candidate moved and original source dependencies removed, native checks rerun successfully |
| CLI/API | Importable stdlib controller + standalone inspect/plan/apply from unrelated CWD, explicit selection/config, persisted plan and original operation-file hash |

The installed pcbnew emits `PROPERTY_ENUM(): No enum choices defined` startup
assertions (and SWIG deprecation/debug messages). These remain in stderr/logs;
subprocess return codes plus native output/invariants determine success, not
absence of diagnostics. Scope/limitations are detailed in `docs/safety.md`.
