# Bread Modular
Bread Modular is an open-source hardware modular synthesizer format designed to be minimalistic and cost-effective.

![Bread Modular](https://www.breadmodular.com/images/home-slide/01.jpg)
### Key Features

* **Modular Design:** Just like Eurorack
* **USB-Powered:** It can be portable
* **Minimal Design:** Cost Effective
* **Modular MIDI Support:** Use MIDI to communicate between modules (still supports CV & Gate)
* **Analog and Digital Signal Paths:** It’s your choice 
* **Diverse Built-in Modules:** Includes a wide range of pre-designed modules
* **Configurable Digital Modules:** Supports both voice and CV (uses AtTiny 1616 or ESP32)
* **Fully Open Source:** Including schematics, PCB designs, and code
* **Ease of Customization:** Enables straightforward creation of custom modules tailored to specific needs.
* **No Case Required:** Can be used directly on a breadboard or mounted on a simple base module.

## KiCad workspace setup

Footprint libraries use a shared project-local table in `opt/fp-lib-table`, linked
into every KiCad project. Workspace initialization copies existing local
submodules instead of cloning them. See [library setup and verification](opt/README.md).

## Table of Contents

* [Specification](https://github.com/bread-modular/bread-modular/wiki/Specification)
* [Common Parts](https://github.com/bread-modular/bread-modular/wiki/Common-Parts)
* [Modules](https://github.com/bread-modular/bread-modular/wiki/Modules)
* [Modular MIDI](https://github.com/bread-modular/bread-modular/wiki/Modular-MIDI)
* [PCB Assembly](https://github.com/bread-modular/bread-modular/wiki/PCB-Assembly)
* [KiCad → JLCPCB Export Tool](opt/kicad-jlcpcb/README.md) — Gerber ZIP, BOM and pick-and-place CSV; no extra Python packages or plugins.

## KiCad assembly export

```sh
python3 opt/kicad-jlcpcb/export.py modules/line_in
```

Requires Python and KiCad's built-in CLI. Add an `LCSC` field to symbols using KiCad's native Symbol Properties / Symbol Fields Table to include catalog part numbers. See the [tool documentation](opt/kicad-jlcpcb/README.md) for requirements, field setup and export options.

