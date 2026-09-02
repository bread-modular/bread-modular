# okcircuit — Design Document

**Date:** 2026-09-02

**Status:** Draft for review

**Decision:** Build `okcircuit`, a headless, minimum-dependency fork of
`@tscircuit/core`, protected by a reference-first differential E2E suite.

**Scope correction:** `okcircuit` is an independent circuit-engine project. No
downstream product, module set, build script, or fabrication workflow defines
its scope.

---

## 1. Goal

Build a maintainable npm package and CLI named **`okcircuit`** for agents and
other non-interactive tools to:

1. compile supported tscircuit TSX/React circuit definitions into Circuit JSON;
2. run connectivity checks and DRC diagnostics;
3. route supported boards through a pinned autorouter dependency;
4. run supported simulations through a pinned simulation dependency;
5. emit deterministic 2D image previews; and
6. export fabrication-ready Gerber files.

This is a fork of the tscircuit **core engine**, not a fork of the complete
browser/editor platform. The implementation should preserve useful headless core
behavior while deleting platform features and dependencies that do not serve the
contract above.

“Minimum dependency” means the smallest justified, audited runtime closure for
this scope. It does **not** mean rewriting mature routing, simulation, or Gerber
algorithms merely to make the dependency count zero.

## 2. Product principles

### 2.1 Agent-first and headless

`okcircuit` is primarily driven by agents, scripts, and CI:

- every operation has a stable programmatic API and a non-interactive CLI form;
- machine-readable JSON diagnostics are the default contract;
- commands never require a browser, display server, editor, prompt, or login;
- output paths and exit codes are deterministic;
- progress text is separable from structured results;
- failures identify the unsupported feature or failed compiler phase;
- network access is not required after installation.

A web UI is neither required nor planned.

### 2.2 Capability-driven compatibility

The fork is not limited to one product’s fixtures. Its support contract is the
headless capability matrix in this document plus:

- retained upstream tests for every in-scope core subsystem;
- neutral E2E fixtures committed to `okcircuit`;
- documented public API exports; and
- explicit negative tests for excluded behavior.

An in-scope feature may not disappear only because the first fixture corpus did
not happen to reach it. Conversely, passing fixtures does not imply compatibility
with the entire `tscircuit` package or its web APIs.

### 2.3 Evidence-driven dependency reduction

A dependency is retained when it owns a substantial, reached domain algorithm or
asset and replacing it would add more maintenance risk than value. A dependency
is removed when it is unreachable, belongs only to an excluded feature, is
stale, or exposes a very small API that can be replaced safely.

All retained versions and transitive closures are pinned and tested. Bundling a
large unused dependency tree into one JavaScript file does not count as
minimization.

## 3. Compatibility boundary

### 3.1 In scope

- the headless React reconciler and core render lifecycle;
- supported primitive components, footprints, selectors, and connectivity;
- source, schematic, and PCB Circuit JSON generation;
- transforms, placement, schematic layout, and PCB layout needed by supported
  core primitives;
- manual traces, vias, and automatic PCB routing;
- structured checks and DRC diagnostics;
- deterministic 2D schematic and PCB image previews;
- Gerber fabrication layers and drill data for supported boards;
- offline simulation for an explicitly supported set of analyses;
- Node and Bun execution through a shared runtime API;
- a compatibility facade for the selected `@tscircuit/core` exports listed in a
  checked-in API manifest.

The exact primitive and public-export matrix is frozen in Phase 0. Headless core
features are presumed in scope unless this document or that matrix excludes
them.

### 3.2 Required public operations

| Logical operation | Required result |
|---|---|
| `compile` | Circuit JSON plus structured diagnostics |
| `check` | structured DRC/connectivity results and a meaningful exit code |
| `render` | deterministic PNG image for a supported 2D view |
| `gerber` | Gerber layer set and companion Excellon drill files when holes exist |
| `route` | routed Circuit JSON or explicit routing failure diagnostics |
| `simulate` | structured numeric analysis results with units and probe names |

The CLI spelling is expected to be:

```text
okcircuit compile <entry> --out <directory> --json
okcircuit check <entry-or-circuit-json> --json
okcircuit render <entry-or-circuit-json> --view pcb --out board.png --json
okcircuit gerber <entry-or-circuit-json> --out <directory> --json
okcircuit simulate <entry-or-circuit-json> --analysis <file-or-name> --json
```

Final flags may change during implementation, but the logical operations and
structured result contracts may not change accidentally.

A corresponding library surface should remain small:

```ts
compile(input, options): Promise<CompileResult>
check(circuitJson, options): Promise<CheckResult>
renderImage(circuitJson, options): Promise<Uint8Array>
exportGerbers(circuitJson, options): Promise<GerberFileSet>
simulate(circuitJson, analysis, options): Promise<SimulationResult>
```

Routing may be selected through `compile` options and exposed separately only if
agents need an explicit reroute operation.

### 3.3 Required artifacts

- **Circuit JSON** is the canonical intermediate and debugging artifact.
- **Diagnostics JSON** is the canonical agent-readable failure/reporting format.
- **PNG** is the initial preview contract. SVG is not a required public output.
- **Gerber** is the only required fabrication export. Excellon is emitted only as
  the normal drill-data companion for boards containing holes.
- A deterministic archive may be offered as a transport convenience, but ZIP
  bytes are not a semantic contract.

BOM, pick-and-place, assembly drawings, 3D models, and enclosure outputs are not
required.

## 4. Non-goals

- Browser editor, runframe, interactive canvas, CDN evaluator, or development web
  server
- React DOM rendering or a browser runtime
- 3D rendering (`gltf`, JSCAD, Three.js), STEP export, or enclosures
- SVG as a stable public artifact or compatibility target
- Assembly renderings, photorealistic board previews, or component 3D models
- BOM, PnP, distributor, registry, auth, publishing, or matchpack workflows
- KiCad project import/export
- General panelization or enclosure generation
- Compatibility with all top-level `tscircuit` CLI and web APIs
- Automatic adoption of upstream releases
- Removing routing or simulation packages solely to advertise zero dependencies

An internal vector scene or transient SVG string is acceptable if it is the
smallest reliable way to produce the required PNG, provided it does not add a
DOM/browser runtime or become a public compatibility promise.

## 5. Audited upstream baseline

The initial oracle is frozen to the versions already audited from the repository
lock and their exact source revisions. Repository-specific modules and patches do
not define the product contract.

| Package | Baseline | Role |
|---|---:|---|
| `tscircuit` | `0.0.2462` / [`c179f7e`](https://github.com/tscircuit/tscircuit/tree/c179f7ecc6bf65c016fee2e75525284cce40dbc7) | reference harness only |
| `@tscircuit/core` | `0.0.1816` / [`51c17c9`](https://github.com/tscircuit/core/tree/51c17c970db7bfdb57bc6dcd996a44d18b1da4ff) | fork source baseline |
| `@tscircuit/cli` | `0.1.2021` / [`0b2a92a`](https://github.com/tscircuit/cli/tree/0b2a92a286883853f90220b1f12c7845125218b1) | reference adapter only |
| `circuit-json` | `0.0.479` / [`2d66087`](https://github.com/tscircuit/circuit-json/tree/2d6608722876d2bd773795396970080382ec4fab) | schema/model baseline |
| `circuit-to-svg` | `0.0.410` / [`a222b1e`](https://github.com/tscircuit/circuit-to-svg/tree/a222b1eb02d20513186cb98d05a1be10c803ddb5) | reference image adapter or internal implementation option; not a required output |
| `circuit-json-to-gerber` | `0.0.97` / [`00ba06f`](https://github.com/tscircuit/circuit-json-to-gerber/tree/00ba06fb8bcf635efd4e501b2136ad5850187a5d) | eligible retained Gerber dependency |
| `@tscircuit/checks` | `0.0.178` / [`270af66`](https://github.com/tscircuit/checks/tree/270af66ccc9b782e1ad6f6527c226292eb590884) | checks/DRC baseline |
| `@tscircuit/capacity-autorouter` | `0.0.851` / [`2f0f304`](https://github.com/tscircuit/tscircuit-autorouter/tree/2f0f3040874cfc7af97df39510b7a0a0960c5cfc) | deliberately retained routing candidate |
| `@tscircuit/alphabet` | `0.0.25` / [`75cab69`](https://github.com/tscircuit/alphabet/tree/75cab694a79f9c9e99cc02e56daaa02d2a04a4d8) | text/geometry baseline |
| `@tscircuit/ngspice-spice-engine` | `0.0.20` | deliberately retained simulation candidate; remote asset loading must be replaced by a pinned local asset path |

The exact core release declares 12 regular dependencies and 18 peer
dependencies; its built entry imports 38 external bare specifiers. It is therefore
not safe to infer the minimum closure from `package.json` alone. The exact source
also contains 1,279 tests, providing a large characterization pool, but tests for
excluded web, 3D, and unrelated platform capabilities should not be carried into
the permanent suite.

The oracle fingerprint records:

- package versions and source commits;
- lockfile hash;
- runtime and operating-system versions;
- reference adapter version;
- rasterizer/viewer versions used only to normalize reference artifacts; and
- hashes of fixture inputs and reference contracts.

The clean upstream baseline is the default oracle. Any existing local font patch
or other repository-specific modification is an explicit optional delta, never
an implicit part of `okcircuit` compatibility.

## 6. Strategy: fork, characterize, then prune

### 6.1 Bootstrap sequence

1. Import the exact `@tscircuit/core@0.0.1816` source with provenance while
   preserving its folder structure.
2. Build a thin `okcircuit` API and CLI around the unmodified core fork.
3. Create neutral, headless E2Es and run them against the pinned upstream
   reference first.
4. Run the same contracts against the unpruned candidate and reach parity before
   major deletion.
5. Delete excluded feature registrations and their source closures: browser/web,
   3D, public SVG export, registry/cloud, BOM/PnP, and other platform-only paths.
6. Retain and adapt the pinned routing, simulation, checks, model, and Gerber
   dependencies when their audited closures are justified.
7. Remove or replace one remaining dependency slice at a time, running retained
   tests, differential E2Es, and package audits after every slice.
8. Publish only after the packed, offline runtime closure is reproducible.

A temporarily heavy candidate is acceptable during bootstrap. It is not an
acceptable release artifact.

### 6.2 Reachability and support analysis

Static and dynamic analysis must distinguish three classes:

1. **Required core:** compiler phases and algorithms owned by `okcircuit`.
2. **Retained domain dependency:** routing, simulation, Gerber, or another
   substantial reached subsystem intentionally consumed as a package.
3. **Excluded/unreachable:** platform or feature code outside the support matrix.

For every pruning decision:

- generate an import graph from the pinned source;
- instrument compiler phases and optional services;
- run the neutral fixture corpus and the relevant retained upstream tests;
- record reached files, exports, element types, selector forms, and service calls;
- remove registrations and barrels that keep excluded paths reachable;
- rerun parity and negative-support tests; and
- update the checked-in dependency and capability manifests.

E2E reachability is not permission to delete an in-scope capability. The support
matrix and retained upstream tests remain authoritative.

### 6.3 Provenance and licenses

Keep:

- `UPSTREAM_BASELINE.json`: package, version, source revision, and hashes;
- `PROVENANCE.md`: retained source files/directories mapped to upstream;
- `THIRD_PARTY_NOTICES.md`: license and copyright notices;
- the required upstream license files; and
- `SUPPORTED_CAPABILITIES.json`: public exports, primitives, analyses, and
  artifact operations promised by a release.

Behavior-changing adaptations require focused local tests and a provenance note.

## 7. Dependency policy

### 7.1 Retain domain dependencies deliberately

The release dependency allowlist is generated and reviewed from a clean install;
it is not restricted to React.

| Dependency area | Policy |
|---|---|
| `react`, `react-reconciler`, `scheduler` | retain and pin for TSX and the custom reconciler |
| Capacity autorouter | retain the pinned package and its justified closure; adapt through a narrow interface |
| Simulation | retain the pinned engine/solver packages and required peer closure; load WASM/assets locally |
| Gerber | retain the pinned converter unless a smaller owned implementation is demonstrably safer |
| Circuit JSON, props, checks | retain initially for compatibility; prune/fork only with differential coverage |
| Image encoder/rasterizer | select one headless implementation after a size, portability, and determinism spike |
| Browser, web UI, 3D, registry, assembly, BOM/PnP packages | exclude from production closure |

An upstream dependency may be wrapped or minimally forked to remove a network or
browser assumption without internalizing its algorithm. Routing and simulation
are explicit examples where a clean adapter is preferred over a rewrite.

### 7.2 Core dependency triage

| Upstream dependency or concern | Planned treatment |
|---|---|
| `nanoid`, `performance-now` | remove first if the pinned source/import audit continues to show no reached use |
| `zod` / `@tscircuit/props` | retain initially; consolidate parsing behind an internal boundary before considering reduction |
| `transformation-matrix` | retain until exact affine behavior is characterized; replace only with exhaustive differential tests |
| `css-select` | preserve the core selector semantics promised by the support matrix; reduce only after an observed selector corpus exists |
| `format-si-unit` | retain or replace with a small table-driven implementation based on measured closure and parity |
| `svg-path-commander` | keep only if reached by supported schematic/image geometry; public SVG export remains out of scope |
| `@flatten-js/core` | retain reached board geometry or replace narrow containment operations with tested geometry code |
| `@lume/kiwi` | retain reached constraint/layout behavior; remove only unsupported/unreached constraint paths |
| packing and cell-boundary packages | retain when needed by in-scope auto-layout; otherwise prune with negative tests |

The project optimizes for a small **maintainable** closure, not the smallest
possible package count at any correctness cost.

### 7.3 Runtime rules

- No runtime CDN fetches, dynamic package installation, or remote evaluation.
- No browser global, DOM, Canvas API, or display-server dependency.
- Optional routing and simulation code may load lazily, but missing assets must
  produce structured errors rather than silent degradation.
- No supported algorithm may be stubbed to pass a dependency gate.
- All production dependencies and transitive versions are represented in a
  reviewed lockfile and generated runtime allowlist.

## 8. Target architecture

```text
okcircuit/
├── package.json
├── UPSTREAM_BASELINE.json
├── PROVENANCE.md
├── THIRD_PARTY_NOTICES.md
├── SUPPORTED_CAPABILITIES.json
├── src/
│   ├── api/                    # stable programmatic operations and result types
│   ├── cli/                    # non-interactive, JSON-first command adapters
│   ├── core/                   # forked/pruned tscircuit core renderer and phases
│   ├── model/                  # Circuit JSON indexes and canonical utilities
│   ├── checks/                 # check/DRC integration
│   ├── routing/                # narrow capacity-autorouter adapter
│   ├── simulation/             # narrow engine adapter and local asset loader
│   ├── render-image/           # headless 2D scene, rasterizer, PNG encoder
│   ├── gerber/                 # Gerber/Excellon adapter and deterministic writer
│   ├── assets/                 # pinned fonts and simulation assets
│   └── runtime/                # Node/Bun filesystem, worker, and clock adapters
└── tests/
    ├── unit/                   # retained upstream and local focused tests
    ├── compatibility/          # public export and primitive support contracts
    ├── e2e/                    # reference-vs-candidate headless contracts
    └── package/                # pack/install/offline/dependency gates
```

Preserve upstream source boundaries during bootstrap. Renaming, pruning, and
algorithm replacement should happen in separate reviewable changes.

## 9. Image-output design

PNG is the initial stable output because agents need an inspectable image, not an
editable vector document.

Requirements:

- support deterministic PCB and schematic views declared in the capability
  manifest;
- fixed viewport, scale, background, layer palette, and font inputs;
- no host-installed fonts or browser text layout;
- explicit top/bottom layer visibility and mirroring semantics;
- deterministic PNG dimensions and decoded RGBA pixels;
- machine-readable metadata beside the image, including view, bounds, scale,
  warnings, and source fingerprint;
- no 3D or perspective projection.

The implementation may use a small internal vector scene, direct rasterization,
or a transient SVG string. Only the PNG bytes and scene semantics are public.
SVG serialization is neither emitted by default nor compared for compatibility.

For E2E comparison, the reference adapter may rasterize upstream SVG with one
pinned dev-only rasterizer. The candidate may render PNG directly. Equivalence is
judged on canonical scene invariants and decoded pixels, not on matching SVG
markup.

## 10. Gerber-output design

`okcircuit gerber` emits a directory containing the supported Gerber layer set.
When a board contains drilled holes, it also emits the corresponding Excellon
drill file because drilling is a separate normal fabrication datum.

Required guarantees:

- deterministic file names and layer mapping;
- finite coordinates and valid aperture definitions;
- a closed board outline when the input defines a board;
- correct top/bottom mirroring and text geometry;
- valid termination commands;
- no BOM, PnP, assembly, 3D, or vendor-specific upload workflow;
- optional deterministic archive packaging only as a convenience.

The Gerber exporter is a justified external domain dependency unless Phase 0
finds it cannot run headlessly or cannot be made deterministic. The project owns
the adapter, validation, output naming, and public result schema even when the
conversion algorithm remains upstream.

## 11. Routing and simulation adapters

### 11.1 Routing

The capacity autorouter remains an external pinned subsystem behind a narrow
adapter:

```ts
route(circuitJson, options): Promise<RouteResult>
```

The adapter owns input validation, seed/determinism settings, cancellation,
timeouts, structured progress, and mapping solver failures into stable
`okcircuit` diagnostics. Debug visualization and web workers are not part of the
runtime contract.

### 11.2 Simulation

The ngspice-compatible engine remains an external pinned subsystem behind:

```ts
simulate(circuitJson, analysis, options): Promise<SimulationResult>
```

The adapter owns supported-analysis validation, local WASM/engine asset loading,
worker portability, timeouts, and numeric result normalization. The installed
baseline’s remote engine loading is not acceptable: release tests must prove the
simulation path works after installation with network access denied and empty
runtime caches.

## 12. E2E strategy: one contract suite, two engines

### 12.1 Core rule

Write the E2Es before pruning. For each fixture and operation:

1. run the exact pinned upstream **reference engine**;
2. stop if the reference contract fails;
3. run the locally packed **candidate engine**;
4. canonicalize each engine’s outputs through artifact-specific comparators; and
5. compare contracts, allowing only explicit reviewed deltas.

The reference engine proves current behavior. The candidate is never allowed to
create or update its own oracle.

Tests invoke public APIs or CLIs in isolated child processes and inspect emitted
files. They do not import candidate-private helpers.

### 12.2 Harness layout

```text
tests/e2e/
├── fixtures/
│   ├── minimal-primitives/
│   ├── connectivity-and-selectors/
│   ├── footprints-and-transforms/
│   ├── schematic-layout/
│   ├── routing-and-vias/
│   ├── drc-pass/
│   ├── drc-fail/
│   ├── text-and-silkscreen/
│   ├── gerber-board/
│   └── simulation-smoke/
├── engines/
│   ├── reference.ts            # exact upstream lock and adapters
│   └── candidate.ts            # packed/local okcircuit
├── comparators/
│   ├── circuit-json.ts
│   ├── diagnostics.ts
│   ├── image.ts
│   ├── gerber-excellon.ts
│   └── simulation.ts
├── contracts/reference/<oracle-fingerprint>/
├── fixture-manifest.ts
└── run-e2e.ts
```

Fixtures are neutral and self-contained. No downstream product source, build
script, warning inventory, or product-specific artifact is part of the oracle.

### 12.3 Oracle lifecycle

- `test:e2e:reference` runs the reference contracts and initially repeats them to
  expose nondeterminism.
- `test:e2e:candidate` compares the candidate with committed contracts.
- `test:e2e:differential` runs reference first and candidate second, preserving
  both raw output trees on failure.
- `test:e2e:record-reference` is manual and records the full oracle fingerprint.
- CI never updates reference contracts.
- A reference update requires explicit review of the upstream lock/source change
  and every semantic/image/Gerber delta.
- During migration, differential mode is mandatory. After cutover, frozen
  contracts may be the normal fast path while the isolated reference remains
  available for deliberate compatibility work.

The reference and candidate use separate installs and caches. Neither may resolve
unlocked caret versions.

### 12.4 Fixture contracts

| Fixture | Contract |
|---|---|
| `minimal-primitives` | representative in-scope primitives and source→schematic→PCB relationships |
| `connectivity-and-selectors` | supported selector forms, nets, ports, and trace relationships |
| `footprints-and-transforms` | built-in/custom footprints, placement, rotation, and layer transforms |
| `schematic-layout` | deterministic source/schematic geometry and image view |
| `routing-and-vias` | manual/automatic traces, widths, vias, layers, containment, and connectivity |
| `drc-pass` / `drc-fail` | exit status plus structured categories, severity, and references |
| `text-and-silkscreen` | glyphs, anchors, sizes, rotation, side mirroring, and Gerber/image agreement |
| `gerber-board` | copper, mask, silkscreen, outline, pads, and drill output |
| `simulation-smoke` | small deterministic analyses with numeric probe assertions |

Every added capability extends `SUPPORTED_CAPABILITIES.json`, at least one
fixture, and the relevant retained/unit tests.

### 12.5 Artifact comparison contracts

| Artifact | Canonicalization and assertions |
|---|---|
| Circuit JSON | recursively sort keys; canonicalize generated IDs and references; normalize runtime paths; compare element types, relationships, ordered route geometry, and numeric fields with explicit per-field tolerances |
| Diagnostics/DRC | compare exit status and sorted tuples of code/category, severity, canonical element reference, and stable payload fields; omit stack paths and prose-only prefixes |
| PNG image | decode to a fixed RGBA representation; verify dimensions/view metadata; compare exact pixels where deterministic and fixture-owned pixel/perceptual thresholds where antialiasing differs; also compare extracted scene bounds and layer counts |
| Gerber/Excellon | compare sorted file names and normalized commands; require exact apertures and geometry where stable; syntax-validate every file; rasterize layers with a pinned dev-only viewer for a secondary image comparison |
| Simulation | compare analysis type, signal/probe names, sample axes, units, and numeric values with explicit tolerances |
| CLI/API | compare exit code, operation result schema, output paths relative to the workspace, and stable diagnostic codes |

Raw output bytes are retained for debugging, but generated IDs, image metadata,
floating formatting, and archive timestamps may be normalized only through
reviewed artifact-specific rules. Ordered geometry is never sorted away.

### 12.6 Intentional deltas

Every intentional difference records:

- fixture, operation, and artifact path;
- old and new behavior;
- reason and approving review;
- replacement invariant or reviewed golden; and
- removal condition if temporary.

Initial acceptable classes are CLI branding, PNG encoder metadata, and optional
archive metadata. Circuit semantics, routing, DRC, Gerber geometry, and simulation
numbers are not blanket exceptions. Any font change is a separate product
decision after baseline parity, not an assumed delta.

### 12.7 Hermeticity

Both adapters fix locale, timezone, working-directory shape, supported random
seeds, and clock inputs. Tests run with network access denied. A CDN request,
dynamic package install, remote evaluation, or host-font dependency fails the
suite.

## 13. Other test layers

Differential E2Es are necessary but not sufficient:

- **Retained upstream tests:** preserve tests attached to every in-scope core,
  checks, layout, routing, Gerber, and simulation subsystem. Drop tests only with
  an explicit excluded-capability mapping.
- **Public API compatibility tests:** compare the checked-in export/type manifest
  and exercise each supported operation from a consumer package.
- **Replacement contract tests:** run pinned dependency and replacement over the
  same corpus before replacing transforms, selectors, units, paths, or geometry.
- **Invariants:** all references resolve; connectivity is symmetric; geometry is
  finite; traces use valid layers; Gerber has a closed outline and valid
  termination; simulation arrays and units are internally consistent.
- **Negative tests:** browser/web/3D/SVG-export/BOM/PnP operations and unsupported
  primitives fail with stable `UNSUPPORTED_*` diagnostics rather than partial
  output.
- **Regression tests:** each parity defect gets the smallest neutral fixture that
  reproduces it.

No browser E2E framework is required because no browser UI is in scope.

## 14. Runtime, packaging, and dependency gates

Shared runtime code may use Node-compatible standard APIs such as `fs`, `path`,
`URL`, `crypto`, `zlib`, `WebAssembly`, and workers behind small adapters.

Node support has two distinct requirements:

1. the packed JavaScript API and CLI run under Node; and
2. supported TSX input can be ingested without a globally installed Bun.

TSX ingestion is a Phase 0 spike. Choose a small owned transform or a pre-bundle
strategy after testing neutral fixtures. Node support may not secretly shell out
to Bun.

Automated release gates:

- build and `npm pack` `okcircuit`;
- install the tarball into an empty temporary consumer project with lifecycle
  scripts disabled;
- run `npm ls --omit=dev --all` and compare the complete tree with the reviewed
  runtime allowlist;
- reject undeclared packages, unlocked versions, web/3D/UI packages, and
  non-approved native binaries;
- scan packed JavaScript/assets for runtime URLs and dynamic-install code;
- execute compile, check, image, Gerber, routing, and simulation E2Es from the
  installed tarball rather than source;
- repeat on the supported Node and Bun versions;
- execute with network denied and empty runtime caches after installation;
- verify simulation and font/image assets are included and loaded locally;
- record compressed/unpacked size, clean install size, cold command latency, and
  peak RSS against reviewed budgets; and
- generate an SBOM and license notice check for the retained dependency closure.

The allowlist may include routing, simulation, Gerber, and their justified
transitive dependencies. The gate prevents accidental growth; it does not force
these subsystems into the fork.

## 15. Phased delivery plan

### Phase 0 — Freeze scope and reference behavior

- Create `SUPPORTED_CAPABILITIES.json` for headless core features and public
  exports.
- Freeze the clean upstream reference lock and oracle fingerprint.
- Build neutral fixtures, adapters, canonicalizers, and artifact retention.
- Run the reference suite twice and resolve nondeterminism.
- Produce static/dynamic import and dependency-closure reports.
- Spike Node TSX ingestion, headless PNG rendering, local simulation assets, and
  Gerber output.
- Record clean size, install, latency, and memory baselines.

**Exit:** the reference-only suite is green and deterministic; the capability and
dependency manifests are reviewed; image, simulation, Gerber, and Node ingestion
approaches are chosen.

### Phase 1 — Establish an unpruned core fork

- Import exact core source and provenance.
- Add the small API/CLI facade and candidate E2E adapter.
- Keep existing pinned domain dependencies initially.

**Exit:** the unpruned candidate passes all non-intentional contracts before major
feature or dependency removal.

### Phase 2 — Remove platform and excluded outputs

- Delete browser/editor/runframe/cloud paths.
- Delete 3D, assembly, BOM/PnP, and public SVG-export registrations.
- Remove packages reachable only from those paths.
- Add negative support tests for every removed public operation.

**Exit:** headless compile/check remains at parity, excluded paths fail clearly,
and the runtime graph contains no web UI or 3D closure.

### Phase 3 — Stabilize retained domain services

- Finalize narrow routing, simulation, checks, and Gerber adapters.
- Pin local simulation assets and eliminate runtime network access.
- Implement deterministic PNG output without a browser.
- Reduce remaining generic dependencies only where parity-backed replacement is
  lower risk than retention.

**Exit:** image, Gerber, routing, and simulation contracts pass from the packed
candidate under Node and Bun with network denied.

### Phase 4 — Package and release

- Pass clean-install, runtime allowlist, SBOM/license, size, latency, and memory
  budgets.
- Document the supported API/capability matrix and migration from
  `@tscircuit/core` for the selected compatibility exports.
- Keep the frozen upstream reference available for future regression checks.

**Exit:** `okcircuit` is reproducibly installable and all public operations run
headlessly from its packed artifact.

## 16. Risks and mitigations

1. **Core coupling is larger than the manifest suggests.**
   Mitigation: begin with an unpruned fork, use import/reachability evidence, and
   require parity after each removal.
2. **A narrow fixture set accidentally defines a narrow product.**
   Mitigation: use an explicit capability matrix and retain upstream tests for
   every in-scope subsystem.
3. **Dependency minimization triggers risky algorithm rewrites.**
   Mitigation: retain mature routing, simulation, and Gerber packages behind
   narrow adapters; optimize maintainable closure rather than package count.
4. **Images match visually while circuit semantics are wrong.**
   Mitigation: combine pixel checks with Circuit JSON relationships, DRC,
   connectivity, and Gerber command assertions.
5. **Raster output becomes nondeterministic across platforms.**
   Mitigation: pin renderer/font assets, compare decoded pixels, standardize
   viewport/palette, and test all supported runtimes in CI.
6. **Gerber parity is not manufacturability.**
   Mitigation: syntax validation, rendered-layer checks, outline/drill
   invariants, and at least one independently reviewed fabrication fixture.
7. **Simulation retains a hidden CDN or cache dependency.**
   Mitigation: local pinned assets plus packed, empty-cache, network-denied E2E.
8. **Node execution secretly depends on Bun for TSX.**
   Mitigation: consumer-package E2E with Bun absent from `PATH`.
9. **Retained dependencies grow transitively.**
   Mitigation: reviewed runtime-tree allowlist, lockfile diff review, SBOM, and
   package-size budgets.
10. **Removing public SVG breaks image generation indirectly.**
    Mitigation: treat SVG, if used internally, as an implementation detail and
    test only the canonical scene/PNG contract.
11. **Upstream changes drift from the fork.**
    Mitigation: upgrades are explicit projects using a new oracle fingerprint and
    differential suite; no automatic tracking.

## 17. Investigated references

- [Top-level tscircuit baseline](https://github.com/tscircuit/tscircuit/tree/c179f7ecc6bf65c016fee2e75525284cce40dbc7)
- [Core source baseline](https://github.com/tscircuit/core/tree/51c17c970db7bfdb57bc6dcd996a44d18b1da4ff)
- [Core test-writing guidance](https://github.com/tscircuit/core/blob/51c17c970db7bfdb57bc6dcd996a44d18b1da4ff/docs/WRITING_TESTS.md)
- [CLI baseline](https://github.com/tscircuit/cli/tree/0b2a92a286883853f90220b1f12c7845125218b1)
- [Circuit-to-SVG baseline](https://github.com/tscircuit/circuit-to-svg/tree/a222b1eb02d20513186cb98d05a1be10c803ddb5)
- [Gerber baseline](https://github.com/tscircuit/circuit-json-to-gerber/tree/00ba06fb8bcf635efd4e501b2136ad5850187a5d)
- [Checks baseline](https://github.com/tscircuit/checks/tree/270af66ccc9b782e1ad6f6527c226292eb590884)
- [Capacity autorouter baseline](https://github.com/tscircuit/tscircuit-autorouter/tree/2f0f3040874cfc7af97df39510b7a0a0960c5cfc)
- [Alphabet baseline](https://github.com/tscircuit/alphabet/tree/75cab694a79f9c9e99cc02e56daaa02d2a04a4d8)

These references document the frozen starting point. The `okcircuit` capability
manifest, neutral contract suite, and reviewed dependency allowlist govern the
fork; no product-specific downstream repository defines its scope.
