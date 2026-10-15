# BASE project footprint variants

`BreadModular_Base.pretty` contains 14 reusable footprint variants for the 61
BASE instances that differed from their original library definitions. They are
registered only in `modules/base/fp-lib-table`; that file is now a regular
project-local table rather than a symlink to `opt/fp-lib-table`. The shared table
and shared/installed footprints were not changed by this repair. Future shared
library-table additions must be explicitly included in this project table too.

## Why these are separate library entries

The installed library is not an exact description of the saved BASE layout:

- Passive footprints retain older line-based fab/courtyard drawings and 3D model
  references instead of the installed library's newer drawing representation.
- Audio jacks and RESET switch retain body graphics moved from silkscreen to
  F.Fab so they do not recreate prior silkscreen conflicts.
- U5 and D1 retain the existing body, polarity, fab and courtyard artwork.
- J5 retains the power-only USB-C pin mapping (A1 to B12, A4 to B9) and the
  previously reviewed shell outline. Do not replace its contact numbering with
  the original generic footprint or reinterpret its assembly XY datum.
- INPUT1 and 5V14 retain the saved socket annulus flags and courtyards.

The library nickname explicitly distinguishes these variants from the original
KiCad/BreadModular definitions. Package basenames are retained so JLCPCB BOM
package names do not change. These are footprint definitions, not procurement
choices: LCSC, MPN, assembly offsets and other part-specific fields stay in the
schematic/PCB, not in the reusable footprint library.

## Scope and maintenance

All copper, pad numbering/geometry/drills/nets, placement, rotation, silkscreen,
3D references, board rules and zone fills were preserved on the PCB. Only 61
footprint library IDs and the corresponding 61 schematic Footprint fields changed.
Native KiCad matched every repaired instance against its new library definition.

Library files are normalized to origin/zero rotation, use `REF**`, and contain no
board nets, sheet paths, per-instance procurement fields or board UUIDs. Do not
replace these with generic library versions without reviewing the differences.

Original footprint IDs, reference groups and normalized differences are recorded
in `../verification/footprint-library/library-manifest.json`. Standard-family
variants derive from the KiCad footprint libraries; BreadModular-family variants
derive from the repository libraries named in that manifest. Existing descriptive
source links and generator attribution remain in the footprint descriptions.

See `../verification/footprint-library/README.md` for native checks and the
fabrication-output equivalence proof. This synchronization is not a new component
qualification, 3D-model migration, electrical redesign or manufacturing approval.
