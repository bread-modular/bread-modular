# v1.3.0 outputs — mechanical assembly hold

These files have been regenerated from the routed v1.3.0 PCB, not the old board.
KiCad DRC reports zero errors, zero unconnected items and zero schematic-parity
findings. The 59 retained library-copy warnings are explained in
[the verification report](../verification/README.md).

**DO NOT ORDER / ASSEMBLE YET.** The Phase 1 socket code C2894928 describes a male
header, not the female socket required to mate with the modules. Actual female
socket identity, mated board gap and the fitted C5664 shunt height still need
confirmation. The schematic/BOM was intentionally not substituted during Phase 2.
The jumper itself is nominally 6 mm above the base, not 2.8 mm.

- `base.zip` is identical to `../jlcpcb/base/base-gerbers.zip` and
  `../jlcpcb/production_files/GERBER-base.zip`.
- Full hand-assembly BOM/CPL and designators: 163 references.
- `../jlcpcb/base/` has the SMD-only JLCPCB BOM/CPL: 119 references, 32 BOM rows.
- `manifest.json` records source/artifact hashes and explicitly retains this hold.
- The old plugin database and `backups/` are historical, not order inputs.
- Preview diode/IC orientation and all placements in the assembler's system before
  approving an order; native CPL generation is not assembly approval.
