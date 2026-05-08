# Known issues

## Silent kernel wedge under sustained fork+exec churn

Reproducer (after login, badge boots cleanly):

```sh
(while :; do /bin/true; done) &
```

Kernel goes silent within seconds — no Oops, no `DETECT_HUNG_TASK`
output, no panic. UART input is also dead, so `tools/loadtest.py`'s
post-wedge state-capture commands return nothing. Recovery requires a
deep esptool reset.

### What's been ruled out
- **Memory exhaustion.** `/proc/buddyinfo` and `/proc/meminfo` stay
  flat across all observed pre-wedge heartbeat samples. Order-7 (512 KB)
  and order-8 (1 MB) blocks are still free at the wedge moment.
- **Sensorpanel-specific.** Originally observed under sensorpanel +
  heartbeat; later confirmed reproducible with grep loops, then with
  pure `/bin/true` loops. Sensorpanel is sufficient but not necessary.
- **File-content-specific.** Continuous grep loops on `/etc`, `/bin`,
  `/sys`, `/proc`, etc. all eventually wedge. Single-shot greps that
  finish (no loop) survive.
- **UART output volume.** Tight CPU loops with no UART output also
  trigger the wedge.

### What it scales with
**Fork+exec rate × wall-time.** The kernel-side heartbeat (KWB kthread,
disabled in default builds, source at
`drivers/misc/esp32p4-watchdog-blink.c`) and the userspace heartbeat
both stop at the same wall-time → total kernel scheduler death, not
just userspace or just printk.

### Hypothesis
Bug in the NOMMU FLAT exec contiguous-block alloc/free path under
sustained churn. Each fork+exec of busybox needs an order-7 (512 KB)
contiguous block; under sustained allocate/free, something in
`mm/nommu.c` or `fs/binfmt_flat.c` reaches an unrecoverable state on
this RV32 + 32 MB PSRAM + ESP32-P4 v1.0 silicon. CPU stalls in a path
that doesn't service the timer IRQ.

### Diagnostic ceiling reached
No Oops because the trap-handler / printk path also dies. Cannot
diagnose further without JTAG / SWD or a non-printk dead-mans-switch.
See `docs/RUNTIME-WEDGE.md` for the planned next steps.

### Workaround for shipping
- Don't run sustained fork+exec loops. Real-user workloads (occasional
  shell commands, sensorpanel idle, wifi-connect) are safe.
- Demos that need continuous child-process churn should be ported to a
  single C process (one fork at startup, then long-running).

## Boot residual ~1/30 freeze at pwm-c6 line (deferred)

After all the patch-0035 fixes, ~1 in 30 cold boots still wedges
silently right after the kernel prints
`esp-hosted-c6-pwm soc:pwm-c6: esp32-c6 backlight pwm registered`.
Suspected to be a deferred-probe-context race when pwm-backlight's
post-apply class-register path runs concurrently with another deferred
consumer. Low priority — the boot harness retries any way.

## BMI270 internal status check sometimes fails

Cosmetic regression from the kernel 6.12 → 6.18 bump. After firmware
upload, the chip's `INTERNAL_STATUS` register sometimes doesn't read
`MSG_INIT_OK`, and the driver returns -ENODEV. Boot continues fine;
sensor isn't enumerated on those cycles. Not investigated yet.
