# BASE 1.3.13 — Astra software/layout/export PASS; vendor/physical holds remain

The complete 1.3.12 candidate was imported and initially verified, not reconstructed
from a dashboard subset. The prior independent assembly HOLD was J5's mouth-based
CPL. This candidate supplies a documented HRO nominal shell-centre datum with
assembly-only XY fields and an independent expected-centre check. **Astra Max
targeted 1.3.13 software/layout/export confirmation is complete: PASS**, all four
findings resolved, in chat `fa1ba1b6-d28a-4178-bb09-cf6a42d01a68`.
See `../verification/astra-confirmation.json` for the user-supplied confirmation,
reviewed source commit/hashes and scope. **JLCPCB portal/library placement preview,
polarity and mapping remain UNPERFORMED.**

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
**No order authorization:** vendor placement preview/polarity/library mapping,
bench/reset/load/audio, physical mating and current quote/stock remain UNPERFORMED.
Production commit `4384e9cec531b8a56ffa921c44883365403e113e` was locally
fast-forwarded into original `base-improvements`; the follow-up publishes review
metadata only. No manufacturing artifacts changed, no advisors, no push or order.
