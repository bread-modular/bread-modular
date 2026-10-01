# BASE 1.3.13 — software checks pass; independent/vendor/physical holds remain

The complete 1.3.12 candidate was imported and initially verified, not reconstructed
from a dashboard subset. The prior independent assembly HOLD was J5's mouth-based
CPL. This candidate supplies a documented HRO nominal shell-centre datum with
assembly-only XY fields and an independent expected-centre check. **Focused Astra
confirmation is still pending; JLCPCB portal/library preview has NOT occurred.**

Three local C1525 100 nF supply capacitors were added at U2/U3/U4 pin 8 with short
GND via returns; existing +2.5 V bias capacitors/circuit remain unchanged. Hand-solder
notes are corrected without policy changes; J23 silk explicitly states LINE mono
and OPEN=STEREO. Bench stability/audio proof is not claimed.

All checks are tied to the exact refilled/saved source. Real DRC/parity: **0 errors,
0 unrouted, 0 parity** with **70 unsuppressed library-copy warnings**. ERC retains
**7 errors + 4 warnings by identity**, not zero ERC. No design-rule, severity or
exclusion weakening. Immutable input mechanical evidence and the exact bounded
schematic/copper delta are checked before frozen source hashes are updated.

**Current JLC upload set:** ../jlcpcb/base/base-gerbers.zip + bom.csv + positions.csv.
**115 SMD / 35 BOM rows**; physical inventory **160 = 115 + 44 hand-solder + DNP J23**.
All ZIP/loose copies are synchronized. See RELEASE_STATUS.md, manifest.json and
../verification/release-hashes.json for exact source/export identities and results.

Original POWER rationale remains under POWER-HISTORICAL-pre-1.3.12.md. Old plugin
database, backups and stale prices are history, not order instructions.
**No order authorization:** targeted review, vendor placement preview, bench,
physical mating, current quote/stock qualification remain holds. The authorized
atomic commit is workspace-only; no merge, push or original-branch commit.
