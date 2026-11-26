#!/bin/sh
# Runs the host tests, builds the firmware and leaves dist/garage-<version>.bin,
# the file to upload from the web page (Settings > Firmware update).
# Usage: tools/build.sh [version]   (default: FW_VERSION from firmware/config.h)
set -e
cd "$(dirname "$0")/.."
version=${1:-$(sed -n 's/^#define FW_VERSION "\(.*\)"/\1/p' firmware/config.h)}
[ -n "$version" ] || { echo "cannot read FW_VERSION from firmware/config.h" >&2; exit 1; }

test/run.sh
out=build/release  # inside the project (bind-mounted in the toolchain container)
rm -rf "$out"
flags=""
[ -n "$1" ] && flags="compiler.cpp.extra_flags=-DFW_VERSION=\"$version\""
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi ${flags:+--build-property "$flags"} \
  --output-dir "$out" firmware >/dev/null
mkdir -p dist
cp "$out/firmware.ino.bin" "dist/garage-$version.bin"
rm -rf "$out"
echo "dist/garage-$version.bin ($(wc -c < "dist/garage-$version.bin") bytes)"
