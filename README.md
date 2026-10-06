# Bread Modular

An open-source hardware modular synthesizer format designed to be minimalistic
and cost-effective: USB-powered, breadboard-friendly, with analog/digital
modules and MIDI alongside CV & Gate.

## Find your starting point

- **Build or explore:** [modules](modules/),
  [specification](https://github.com/bread-modular/bread-modular/wiki/Specification),
  [common parts](https://github.com/bread-modular/bread-modular/wiki/Common-Parts).
- **Set up KiCad libraries:** [workspace/library setup](opt/README.md). Projects
  use the shared `opt/fp-lib-table`; initialization copies local submodules
  rather than cloning them.
- **Check/export/source parts:** [KiCad toolkit](opt/kicad-tools/README.md).
  Canonical tools, JLCPCB utilities and skills live under `opt/kicad-tools/`.

## KiCad quick start

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py doctor
python3 -B opt/kicad-tools/kicad_tools.py export --help
```

Python + installed KiCad CLI; no extra packages for core tools. Private checks,
Gerber/BOM/CPL export, native netlist helpers and read-only sourcing have
[distinct requirements and safety boundaries](opt/kicad-tools/README.md).
Exports are not electrical/release/order approval; keep frozen module scripts
and production designs untouched. Historical `opt/kicad-jlcpcb` and
`.agents/skills/{kicad-workflow,jlcpcb-assembly}` resolve through
[relative compatibility symlinks](opt/kicad-tools/BUNDLING.md#canonical-layout).

Agents: start with the [KiCad workflow skill](opt/kicad-tools/skills/kicad-workflow/SKILL.md)
or [assembly skill](opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md), then actual CLI help.

## Project references

[Module catalog](https://github.com/bread-modular/bread-modular/wiki/Modules) ·
[Modular MIDI](https://github.com/bread-modular/bread-modular/wiki/Modular-MIDI) ·
[PCB assembly](https://github.com/bread-modular/bread-modular/wiki/PCB-Assembly)

- [Standalone exporter / native part-number setup](opt/kicad-tools/jlcpcb/README.md)
- [Sourcing, audits and passive planning](opt/kicad-tools/jlcpcb/ASSEMBLY.md)
- [32bit-5v sourcing / release HOLD](modules/32bit-5v/verification/basic-economy/README.md)
- [16bit-5v sourcing HOLD evidence](modules/16bit-5v/verification/basic-economy/README.md)

<details>
<summary>Project image and full feature overview</summary>

![Bread Modular](https://www.breadmodular.com/images/home-slide/01.jpg)

- **Modular design:** Just like Eurorack.
- **USB-powered:** It can be portable.
- **Minimal design:** Cost-effective.
- **Modular MIDI support:** Communicate between modules; CV & Gate still supported.
- **Analog and digital signal paths:** It’s your choice.
- **Diverse built-in modules:** A wide range of pre-designed modules.
- **Configurable digital modules:** Voice and CV using AtTiny 1616 or ESP32.
- **Fully open source:** Schematics, PCB designs and code.
- **Ease of customization:** Create modules tailored to your needs.
- **No case required:** Use directly on a breadboard or a simple base module.

</details>
