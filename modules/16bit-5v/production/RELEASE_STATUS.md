# HOLD — partial Basic/Economy sourcing review

This package is for uncommitted native-diff review, **not manufacturing/order approval**.

- Authority: `16bit-5v` routed baseline `1e50e798d68e3d8d3167fb5fb47bdcb7ee436b83`; isolated workspace 291 / `okbrain/bread-modular-kicad/291-5d2e00a7` only; workspace 288 is preserved as the untouched backup. Main's base checkpoint/design was NOT imported.
- Shared tools/skill imported from `f43184a620aee47aec456241646d008fb4a65bda`; only the four capacitor-voltage fix paths imported from `4a77e133af1f1da80b8aed1bf03a5b550f8448d3`. No branch-private catalog normalization or exporter was created/used.
- 41 of 43 required R/C (including five supplier review candidates on application HOLD) now have exact actual Basic codes, matching nominal values/footprints and synchronized native supplier/rating fields. This is **not** a claim that all required R/C or the whole board pass sourcing/application review. Eleven other assembled references have exact-code allocations; nonpassive Extended classification is retained explicitly.
- R7/R8 remain unassigned 27-ohm USB resistors. Exact Basic+Economy mixed candidate: C25092 22 ohm + (C25077 10 ohm || C25077 10 ohm) = 27 ohm, 26.73–27.27 ohm at ±1%; NOT implemented because USB stress/pulse and near-chip branching/AC layout suitability are unproven.
- C6/C7/C9/C10 now bind C23733/CL05A475MP5NRNC (4.7uF, 10V, X5R, ±20%, retained 0402); C21 binds C15008/CL31A107MQHNNNE (100uF, 6.3V, X5R, ±20%, retained 1206). Explicit native supplier review candidates only: guaranteed bias/effective-C/ESR/ESL and circuit minima remain application/manufacturing HOLD. No topology/footprint/copper changes or new waivers; no Extended/DNP/manual workaround.
- STOP: D1 generic LED and U5 generic PSRAM exact identity/package/polarity/firmware intent unresolved. Candidate live evidence is investigation only.
- The conservative common native and BOM audits remain **failed/HOLD**: strict-live/cache replay, four missing identities, absent human review attestations and unresolved effective-C/ESR/ESL/temperature/external-stress facts are not fabricated or bypassed. C27's existing 1uF nominal AP2112 output part is not a proof of >=1uF effective after tolerance/bias/temperature; C25 input and R5 startup/repetitive pulse also require application validation.
- Quantity unknown. Saved dated stock is compared against **one board's placements**, without attrition, minima or reservation. PT8211 C92004 is the stock-only bottleneck (one available at observed retrieval); full-board maximum remains unverified and can be no greater than that known-part bound. Recheck actual quantity, all exact identities, service/classification/stock and attrition/minimum assembly quantities immediately before a user-controlled order.
- Preserve two copper layers/all-copper Gerbers, unchanged outline/mounts/connector alignment/assembly origin, 56 top SMD assembly refs and six explicit manual parts. Four connector bodies remain bottom (`GND1`, `V_SUPPLY1`, `J1`, `J2`); two RV09 pots remain front. No exclusions/side changes to game an audit.
- Human gates: purchased manual parts, lead protrusion/case/mating clearance; current board-level Economy options and process; QFN thermal via-in-pad/stencil/inspection and reflow; every Gerber layer/drill/paste and JLC placement/pin-1/polarity preview; bench power/ripple/inductor/startup/USB/audio and final production/order authorization.

Dated common-API evidence is replayed explicitly; final production audits make no new supplier queries and cannot pass strict-live or order gates. Current hashes/counts/evidence are in `manifest.json` and
[`verification/basic-economy/README.md`](../verification/basic-economy/README.md).
Historical `verification/review-response.json` and older advisor/placement reports
remain history only; they do not approve this source revision. Advisor OFF.

The rebound `tools/verify_power.py` and
`tools/regenerate_production.py --review-preparation` require the new reviewed
source/evidence/workspace/branch/HEAD hashes and preserve all electrical gates.
The module's old private exporter is retained only as historical code and is not
invoked; the old migration/finalizer and disabled layout prototype must not run.
No commit, staging, merge, push, authenticated upload or order was performed.
