# C6 slave patches against upstream esp-hosted-ng

Patch series against the slave application from
[`espressif/esp-hosted`](https://github.com/espressif/esp-hosted),
tag `release/ng-1.0.6`. The slave lives in
`esp_hosted_ng/esp/esp_driver/network_adapter/` upstream; we apply
patches relative to that directory (so `a/main/foo.c` →
`network_adapter/main/foo.c`).

## Active series

| #    | Patch | What it does |
|------|-------|--------------|
| 0001 | `spi-slave-c6-gpio-matrix-overrides.patch` | SPI pin overrides for the WHY2025 badge: MOSI=18, MISO=20, SCK=19, CS=21 (mapped via the C6 GPIO matrix to align with the badge's SDIO trace pins). Replaces the upstream defaults in the C6 stanza of `spi_slave_api.c`. |
| 0002 | `cmd-set-backlight-slot-32.patch` | Adds `CMD_SET_BACKLIGHT = 32` to `include/cmd.h`, `struct cmd_set_backlight { command_header header; u8 brightness; u8 pad[3]; }` to `include/adapter.h`, and the `process_set_backlight()` handler to `cmd.c`. The handler does `ledc_set_duty + ledc_update_duty` on `LEDC_CHANNEL_0` (display backlight). |
| 0003 | `app-main-why2025-backlight-init.patch` | Adds `why2025_backlight_init()` (sets up LEDC timer 0 + channels for display + keyboard backlight, `BL_DISPLAY_INITIAL_DUTY=76`), wires the `CMD_SET_BACKLIGHT` dispatch into `process_priv_cmd()`, and calls the init at boot. Also includes a small SLC-bootup-retrigger loop that's only relevant for the SDIO transport and is harmless on SPI builds. |

## Disabled / parked

| Patch | Note |
|-------|------|
| `0004-sdio-slave-c6-v02-quirks.patch.disabled` | C6 v0.2 SDIO slave silicon-and-firmware quirks: pkt_len strobe gates DAT drive; conf_w5 must be individual size not cumulative; spurious slc0_rx_eof handling. Required for the SDIO transport (now historical — the badge's runtime path is SPI). Kept here for completeness and in case the SDIO path is revisited. |

## Applying

```bash
git clone -b release/ng-1.0.6 https://github.com/espressif/esp-hosted.git
cd esp-hosted/esp_hosted_ng/esp/esp_driver/network_adapter

for p in /path/to/why2025-linux/patches/c6-slave/00[0-9][0-9]-*.patch; do
    patch -p1 -i "$p"
done
# (0004 is .disabled by default; only apply if you actually need SDIO)
```

The result should match this repo's `c6-slave/` tree (modulo
sdkconfig.old and CHANGES.md). Buildroot-style `BR2_KERNEL_PATCH=...`
is not used here — the slave is an ESP-IDF project, build with
`idf.py build` after applying the patches.

## Building

```bash
. $IDF_PATH/export.sh
idf.py set-target esp32c6
idf.py build
```

Flash via the **back** USB-C port (CH334 hub reaches the C6 directly);
hold `SW1` (BOOT) low at reset to enter ROM download mode, then:

```bash
esptool --chip esp32c6 -p /dev/cu.usbmodem<your-c6-port> \
  --before default-reset --after hard-reset \
  write-flash 0x0 build/network_adapter.bin
```

(In-band OTA from Linux is also possible once Wi-Fi is up; see
`drivers/net/wireless/espressif/esp_hosted/main.c` `ota_file=` module
parameter.)
