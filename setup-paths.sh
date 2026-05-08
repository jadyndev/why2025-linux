#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Replace the @WHY2025_LINUX@ placeholder in patches/linux/{buildroot,kernel}.config
# with the absolute path to this repo, so Buildroot can find the kernel patches,
# overlay, and post-build script.
#
# Run once after cloning. Idempotent.

set -e

REPO=$(cd "$(dirname "$0")" && pwd)

for f in "$REPO/configs/why2025_defconfig" "$REPO/patches/linux/kernel.config"; do
    if [ ! -f "$f" ]; then
        echo "skip: $f (not found)"
        continue
    fi
    if grep -q '@WHY2025_LINUX@' "$f"; then
        # macOS sed needs '' for in-place; GNU sed doesn't. Detect and adapt.
        if sed --version >/dev/null 2>&1; then
            sed -i "s|@WHY2025_LINUX@|$REPO|g" "$f"
        else
            sed -i '' "s|@WHY2025_LINUX@|$REPO|g" "$f"
        fi
        echo "patched: $f -> $REPO"
    else
        echo "ok: $f (no placeholder)"
    fi
done
