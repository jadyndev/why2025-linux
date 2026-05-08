#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""SD card sanity test on the WHY2025 badge.

Drives the badge via UART:
- Hard-reset, wait for boot+login, log in as root.
- Silence kernel printk (`dmesg -n 1`) so it doesn't garble typed commands.
- Run a `dd` matrix on /dev/mmcblk0 + /dev/mmcblk0p1.
- Mount /dev/mmcblk0p1 as VFAT under /tmp/sd, ls + umount.
- 4 MB sequential read for rough throughput.

Output is the captured serial stream printed at end. Run from macOS;
close `tio` first (it locks the port).

Doubles as the canonical reference for the read+pump+write driving
pattern used by other scripts in this directory.
"""
import serial, time, sys

s = serial.Serial('/dev/cu.wchusbserial10', 115200, timeout=0.3)
s.dtr = False; s.rts = False
time.sleep(0.1)
s.rts = True; time.sleep(0.2); s.rts = False

out = bytearray()
def pump(secs):
    end = time.time() + secs
    while time.time() < end:
        c = s.read(8192)
        if c: out.extend(c)

pump(22)
s.write(b'root\n'); pump(3)
s.write(b'dmesg -n 1\n'); pump(2)

# dd matrix.
s.write(b'ls /dev/mmcblk* 2>&1\n'); pump(2)
s.write(b'dd if=/dev/mmcblk0 of=/dev/null bs=512 count=1 2>&1; echo RC512=$?\n'); pump(5)
s.write(b'dd if=/dev/mmcblk0 of=/dev/null bs=4096 count=1 2>&1; echo RC4K=$?\n'); pump(5)
s.write(b'dd if=/dev/mmcblk0 of=/dev/null bs=512 count=8 2>&1; echo RC512x8=$?\n'); pump(5)
s.write(b'dd if=/dev/mmcblk0p1 of=/dev/null bs=512 count=2 2>&1; echo RCP1=$?\n'); pump(5)

# VFAT mount + read a file via dd.
s.write(b'mkdir -p /tmp/sd 2>&1; echo MKDIR=$?\n'); pump(2)
s.write(b'mount -t vfat /dev/mmcblk0p1 /tmp/sd 2>&1; echo MNT=$?\n'); pump(15)
s.write(b'ls /tmp/sd 2>&1 | head -10\n'); pump(3)
s.write(b'umount /tmp/sd 2>&1; echo UMNT=$?\n'); pump(4)

# Throughput.
s.write(b'dd if=/dev/mmcblk0 of=/dev/null bs=1M count=4 2>&1; echo RC4M=$?\n'); pump(45)

s.write(b'echo DONE_MARK\n'); pump(2)

s.close()
sys.stdout.buffer.write(bytes(out))
sys.stdout.flush()
