# Bounded local routing smoke

Stdlib Python facade around **native KiCad + Freerouting**, not another router or
file converter. Support/authorization is **synthetic fixture only**: no board-
input option, module/release input, production exports or global installation.

## Commands — repository root

```sh
python3 opt/kicad-routing/run.py doctor
python3 opt/kicad-routing/run.py doctor --help
python3 opt/kicad-routing/run.py prepare-runtime --help
python3 opt/kicad-routing/run.py smoke --help

# Explicit acquisition only; never executes Java. Refuses an existing runtime.
python3 opt/kicad-routing/run.py prepare-runtime --allow-downloads

# Offline only; requires previously prepared, re-hashed runtime.
python3 opt/kicad-routing/run.py smoke
python3 opt/kicad-routing/run.py smoke --run-id new-test --route-timeout 120

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s opt/kicad-routing/tests -v
```

Core facade can delegate these commands unchanged. stdout is JSON; binding
assertions remain visible on stderr. `doctor` is read-only (no board load,
Java/download or output-directory creation); it reports unavailable capabilities
without failing the diagnostic command. Preparation returns `prepared`; smoke
returns `passed`/`failed` with nonzero exit on failure. Invalid arguments exit 2.
Normal commands **never auto-download**. Routing requires **Python 3.9+**
(`Path.is_relative_to`; core toolkit alone supports 3.8+), Linux x86_64,
matching system Python/`pcbnew`, **KiCad 10.0.6**, `kicad-cli`, installed `/usr/bin/bwrap`; other
architectures/bindings fail closed, without an alternative engine.

## Runtime provenance and offline boundary

`runtime.py` pins **Freerouting 2.5.0** and **Temurin HotSpot JRE 25.0.4.1+1 Linux
x64**, using the exact URL/SHA256 pairs from
[`docs/kicad-routing-research.md`](../../docs/kicad-routing-research.md). Tagged
GitHub asset metadata, downloaded size/hash, release/ELF architecture and notices
are verified. Archive traversal, hardlinks, special files, symlink ancestors,
escaping/chained links, overwrite and untrusted redirects are rejected.

Freerouting is **GPL-3.0** (pinned license text retained); Temurin is **GPLv2 with
Classpath Exception**, plus bundled notices (184 files observed). Original
archive, legal tree and provenance stay local. Upstream pins are reproducibility
checks, **not an independent security audit**. No third-party source/binaries are
vendored; no PATH/Java-alternatives changes. `runtime.tmp/` and `work.tmp/` under
this directory use the existing repository `*.tmp` ignore rule. Partial
preparation retains failure provenance and is unusable; inspect/move only that
owned directory before a deliberate retry. No automatic retries exist.

Java executes **only in Bubblewrap**: network/PID/IPC/UTS namespaces, cleared
environment, read-only runtime/system libraries and source/before/DSN, hidden
host home, isolated HOME/XDG/TMP, and only the selected workspace-local run dir
persistently writable. `/proc` and `/dev` are sandbox pseudo-filesystems. The
installed Python probe proves namespace separation, only `lo`, egress
unreachable, host-loopback listener inaccessible, and actual read-only write
failures. Sandbox failure has **no online fallback**.

API/MCP/GUI are disabled; analytics/profile opt-out is explicit and logged.
Fanout, optimization and automatic neckdown are disabled. Actual help/reflection
parsing exercises nested flags; unknown/ignored-setting warnings fail even with
exit 0. Upstream `--router.result_json_path` supplies the **actual merged router
settings and DSN hash**; a default saved config is not called an effective
snapshot. One job, max 10 passes, 512 MiB Java heap, two processors, 1–120 s
routing deadline, 240 s smoke stage budget. Process groups die on timeout/log
limit; capture is capped at 4 MiB/stream, files at 16 MiB, cores disabled.

## Native smoke gates and retained evidence

`fixture.py` generates a self-contained **40×30 mm, two-layer** project: two
four-pin headers, crossing SIG_A/SIG_B endpoints, one locked CRITICAL track,
bottom GND zone and front track/via/pour keepout. Matching embedded schematic
symbols/local footprint library require no global project libraries. Fixture-
only rules: 0.20 mm gap, 0.25 mm nominal/minimum track, 0.60/0.30 mm via,
0.50 mm copper-to-edge. **Not production recommendations.**

Source hashes freeze the generated input. Same-stem `before/synthetic.*` and
`after/synthetic.*` preserve project/rules/schematic/tables/local libraries.
Project-aware native **two-argument** `ExportSpecctraDSN(board, file)` and
`ImportSpecctraSES(board, file)` perform interchange, not our structural
validators. Export checks native defaults, DSN net membership/layers/class
width/gap/via/plane/keepout and critical `type fix`. Before saving, in-memory
placement/pads/net names/rules/locked copper/protected-net branches must match.
Native save skips settings rewrites; explicit unload uses `aSave=False`.

Native CLI DRC/refill/save runs on copies **before and after**, with parity,
all-track errors, all severities/exclusions. Only two exact planned pad-pair
opens are allowed initially; every other finding blocks. Afterward: zero
findings/opens/parity, unchanged ignored checks. Schematic XML nodes are also
matched to every physical pad. Reloaded saved nonrouting/mechanical/pad and zone
**definitions** must match; filled polygons may change. Only `.kicad_prl` view
state/transient locks are outside design invariants; rule hashes are not waived.

Unique per-run DSN filenames + frozen source/PCB/project and DSN/SES hashes bind
one session to one snapshot. Observed SES `base_design` is the **input stem**,
whereas KiCad's DSN header is the full path; basename-only matching is unsafe.
Existing labels/files are never overwritten. `work.tmp/runs/<id>/run.json` and
per-process JSON retain commands/durations, tool/artifact/log hashes, full DRC,
invariants, actual settings, sandbox proof, metrics and honest failure status.
Native subprocesses contain SWIG crashes **without hiding stderr assertions**.
[`smoke-summary.json`](smoke-summary.json) retains compact reviewable evidence
independently of ignored-directory cleanup. The optional toolkit bundle ships
this exact historical evidence file and `tests/test_routing.py`, not raw logs or
runtime provenance/binaries. Tests are native/process mocks plus
an installed-Python timeout probe: no download or Java execution.

## Limits and future/manual external projects

Successful native → Freerouting → native/refill/save → DRC smoke used **front-
layer detours and zero vias**. Actual via/layer-change import, arbitrary custom
rules, differential pairs/tuning and production boards remain **unvalidated**.
Zone DRC/connectivity is not a return-path, neck/thermal, electrical or
manufacturing review. PROPERTY_ENUM assertions remain recorded. Direct
`SetProject` on a brand-new BOARD segfaulted in the initial probe; fixture
creation now native-saves/reloads first. Early neckdown produced a 0.1874 mm
segment; the final supported invocation disables neckdown and passes native DRC.

**External projects are a future/manual procedure, not a supported CLI; separate
authorization and rule/engineering review are required:**

1. Freeze a complete same-stem project snapshot (hierarchy, rules, severity/
   exclusions, local libraries, mechanics/stackup); route/lock critical copper
   natively and establish native DRC/parity.
2. Native-export DSN and inspect its supported rule subset; never weaken rules
   or treat DSN as authority for arbitrary KiCad constraints.
3. Under a separately reviewed offline setup, route ordinary nets and associate
   SES with the exact frozen snapshot/DSN hashes, not its basename.
4. Native-import into an isolated matching copy. SES can **replace unlocked
   copper and move footprints**: enforce invariants, refill/save/reload, run
   complete native DRC/parity and inspect the delta.
5. Human-review return paths, thermals, coupling/skew, current, mechanics and
   manufacturing intent. **DRC success is not production readiness.**
