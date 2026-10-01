Uploading Firmware
==================

The UPDIProgrammer runs the jtag2updi firmware on its own ATtiny1616. Because a
board cannot program itself, flashing needs a *second* UPDI-capable programmer
(another UPDIProgrammer board, or any jtag2updi / serialupdi adapter) plugged
into USB-serial.

Two scripts live in opt/attiny1616-tools/ and are symlinked next to this file
(same pattern as the 8bit module):

  setup.sh   install avrdude (with jtag2updi support) + check serial access
  flash.sh   write jtag2updi_t1616.hex through avrdude

One-time setup
--------------

  ./setup.sh            # install what is missing (avrdude, serial access)
  ./setup.sh --check    # report the current state only; change nothing

setup.sh reuses an avrdude that already supports jtag2updi, otherwise installs
one with the system package manager (brew / apt-get / dnf / pacman / zypper),
otherwise falls back to arduino-cli + megaTinyCore and exposes its bundled
avrdude as ~/bin/avrdude. Re-running is safe.

Flashing
--------

  ./flash.sh                    # list the serial ports and pick one
  ./flash.sh /dev/ttyUSB0       # explicit port (the suggested default)
  ./flash.sh --port /dev/ttyUSB1
  ./flash.sh --list             # just show the candidate ports
  ./flash.sh --dry-run          # read the chip but write nothing
  ./flash.sh --no-fuses         # keep the current fuse bytes
  ./flash.sh --help

Without a port argument the script detects the USB-serial adapters
(/dev/ttyUSB*, /dev/ttyACM*, /dev/cu.*) and asks which one to use; the list
pre-selects /dev/ttyUSB0, so pressing Enter uses it. One port is used without
asking, and with no port at all the script stops with the list.

Environment overrides: PORT, PORT_DEFAULT, PROGRAMMER (default jtag2updi),
PART (t1616), BAUD, HEX_FILE, AVRDUDE, AVRDUDE_CONF, SKIP_FUSES=1.

Other programmers:

  PROGRAMMER=serialupdi      ./flash.sh   # plain USB serial + 4.7 kOhm resistor
  PROGRAMMER=serialupdi57k   ./flash.sh   # serialupdi @ 57600 baud (CH340)

Reference avrdude command
-------------------------

flash.sh runs the equivalent of (fuses first, chip erased, then the flash):

  avrdude -c jtag2updi -P /dev/ttyUSB0 -p t1616 -e \
    -U fuse0:w:0x00:m -U fuse1:w:0b00000000:m -U fuse2:w:0x02:m \
    -U fuse4:w:0x00:m -U fuse5:w:0xC7:m -U fuse6:w:0x03:m \
    -U fuse7:w:0x00:m -U fuse8:w:0x00:m \
    -U flash:w:jtag2updi_t1616.hex:i
