# Local routing: ordinary project candidates

Standalone **native KiCad DSN → pinned offline Freerouting → native SES** routing
for a deliberately small supported subset. **Not all-board support, auto-placement,
production/export approval or a replacement for native GUI push/shove.**

## Quickstart — repository root

First place components and route/lock critical copper with an agent's native
editing tools or PCB Editor. Freeze a **separate complete snapshot**, not a live
project/repository: matching PCB/project/schematic/rules plus local libraries.
Read [SUPPORTED_SUBSET.md](SUPPORTED_SUBSET.md) before opting in.

```sh
python3 opt/kicad-routing/run.py doctor
# Acquisition is optional, explicit, workspace-local; NEVER automatic during routing:
python3 opt/kicad-routing/run.py prepare-runtime --allow-downloads

# Inspect (stdout only), then authorize only ordinary nets. Repeat --reroute-net.
python3 opt/kicad-routing/run.py inspect-project --snapshot "/path/Project snapshot" --pcb "Controller.kicad_pcb"
python3 opt/kicad-routing/run.py plan-project --snapshot "/path/Project snapshot" --pcb "Controller.kicad_pcb" \
  --reroute-net DATA --reroute-net ENABLE > /path/reviewed-plan.json

# Review that JSON OUTSIDE the snapshot; no hashes or UUID pairs to hand-craft.
python3 opt/kicad-routing/run.py route-project --snapshot "/path/Project snapshot" --pcb "Controller.kicad_pcb" \
  --plan /path/reviewed-plan.json --run-id controller-001 --dry-run
python3 opt/kicad-routing/run.py route-project --snapshot "/path/Project snapshot" --pcb "Controller.kicad_pcb" \
  --plan /path/reviewed-plan.json --run-id controller-001 --route-timeout 120 --apply
```

Only `--apply` creates a **NEW candidate/evidence** under
`opt/kicad-routing/work.tmp/runs/<id>/`; it never updates the source. All copper
on non-authorized nets (even unlocked branches), all locked copper and all
placements must remain unchanged. Approval is not selected-net router support:
Freerouting exclusions are class-based; **no class assignments are rewritten**.

[API.md](API.md) · [Supported subset](SUPPORTED_SUBSET.md) · [Safety/evidence](SAFETY.md)
· [Tests and observed results](TESTING.md) · [Historical smoke](SMOKE.md)
