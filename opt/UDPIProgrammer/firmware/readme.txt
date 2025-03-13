Uploading Firmware
==================

* Install avrdude
* Run the following command:

```
avrdude -c jtag2updi -P /dev/tty.usbserial-A5069RR4 -p t1616 -e -U fuse0:w:0x00:m -U fuse1:w:0b00000000:m -U fuse2:w:0x02:m -U fuse4:w:0x00:m -U fuse5:w:0xC7:m -U fuse6:w:0x03:m -U fuse7:w:0x00:m -U fuse8:w:0x00:m -U flash:w:jtag2updi_t1616.hex:i
```