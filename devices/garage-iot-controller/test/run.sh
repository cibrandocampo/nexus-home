#!/bin/sh
# Builds and runs the host tests for the garage logic (needs g++).
set -e
cd "$(dirname "$0")"
out=$(mktemp)
${CXX:-g++} -std=c++17 -Wall -Wextra -DHOST_TEST -Istubs garage_test.cpp ../firmware/garage.cpp ../firmware/watchdog.cpp ../firmware/settings.cpp -o "$out"
"$out"
rm -f "$out"
