# Silent kernel wedge — investigation plan

This is the plan for closing out the silent runtime wedge described
in [`KNOWN-ISSUES.md`](KNOWN-ISSUES.md). Steps are listed in
ascending order of cost; each one independently moves the needle.

## 1. Remove `idle=poll` from cmdline (cheap, ~5 min)

The current cmdline forces the CPU to spin in `cpu_idle_loop()`
instead of using WFI. That was an early workaround when CLIC behaviour
under WFI was unclear. Now that the CLIC driver is stable, remove
`idle=poll` from `patches/linux/kernel.config`'s `CONFIG_CMDLINE` and
test the reproducer:

```sh
(while :; do /bin/true; done) &
```

If WFI-based idle path doesn't trigger the wedge, ship it. If the
kernel hangs at first idle, revert (CLIC may still mishandle WFI on
this v0.9 silicon).

## 2. Audit `mm/nommu.c` and `fs/binfmt_flat.c` for races (1–2 hr)

The wedge is in alloc/free/relocate during fork+exec on RV32 NOMMU.
Code-read these two files focused on:

  - Locks held across allocator calls.
  - Reentrancy in the FLAT relocation loop (we have a known issue
    where uClibc stdio loses relocations through elf2flt — that's
    binary-side; the kernel side is allocator + relocation patcher).
  - Memory-barrier requirements for PSRAM cache flushes around
    page tables / vma trees.

Cross-check against `linux-riscv@lists.infradead.org` archives for
similar reports. Cheap to do; either finds a known fix or rules it
out.

## 3. Disable BMI270 retry-trigger and pwm-c6 first-apply skip (1 hr)

Both ship in patch 0035 and fire from `late_initcall` /
deferred_probe_work. They might keep state alive that interacts with
sustained fork churn. Run the reproducer with each reverted (one at
a time) to confirm they're not contributing.

## 4. CMA reservation for FLAT exec (half-day)

Reserve a contiguous DT-described pool — same shape as the existing
`linux,nommu-userspace-pool` from patch 0032, but a separate region
specifically for the FLAT exec backing. Patch `binfmt_flat.c` to
allocate the program block from this pool instead of the buddy heap.
Different allocator code path entirely → likely sidesteps whatever's
racy in the buddy alloc/free path on this silicon.

Already on the project's "next steps" roadmap; this would be the
forcing function to actually do it.

## 5. `CONFIG_PROVE_LOCKING=y` (1 hr)

Heavy. Likely overflows the 6.5 MB kernel partition; would need to
disable other things (KALLSYMS is already off, DETECT_HUNG_TASK is
already on).

If it fits and fires during the reproducer, points directly at the
lock inversion. If it fits and stays silent, the wedge isn't a
classic AB/BA deadlock.

## 6. JTAG / SWD investigation (needs hardware: ESP-Prog ~€10)

Connect to the badge's JTAG pads. When wedged, halt CPU and inspect
PC, registers, memory. Only path to ground-truth if 1–5 don't crack
it. Big up-front investment but unblocks every future kernel-debug
task on this board.

## 7. Upstream report (~30 min)

Even without a fix, a well-formed bug report to
`linux-riscv@lists.infradead.org` with the minimal reproducer and the
characterisation summary may surface someone who's seen it. Also
relevant for the FOSDEM-talk RFC angle.

## Recommended order

**1 → 7 → 2 → 4 → 6.** Skip 3 unless 1–2 produce nothing. Skip 5
unless the partition headroom permits it.

## Tools available

  - `tools/loadtest.py` — sensorpanel + heartbeat reproducer (~19 min wedge)
  - `tools/greptest.py` — grep-loop reproducer (~5–25 s wedge)
  - `tools/grepbisect.py` — bisects which subtree triggers (TICK heartbeat detector)
  - Simpler: `(while :; do /bin/true; done) &` after login (seconds)
  - `drivers/misc/esp32p4-watchdog-blink.c` — kernel kthread that
    pr_alerts every 5 s and toggles backlight via cmd_set_backlight.
    Not in default build (commented `obj-y` in `drivers/misc/Makefile`
    of the in-tree-applied source). Distinguishes "scheduler dead"
    from "printk dead" from "SPI dead".
