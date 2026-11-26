# Firmware toolchain for the garage controller: g++ for the host tests, arduino-cli with the UNO R4
# core for builds and USB uploads, python3 for .ota files and the update script's file server.
# Used by the Makefile next to it (`make help`) and by CI; nothing of this runs on the host.
FROM debian:trixie-slim

ARG ARDUINO_CLI_VERSION=1.6.0
ARG ARDUINO_CLI_SHA256=321ee249f44c78053234fec0f36101092bc6021bf24939e15e0cc2449c5ed250
ARG RENESAS_CORE=arduino:renesas_uno@1.6.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends g++ make python3 curl ca-certificates iproute2 \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSLo /tmp/cli.tar.gz \
      "https://github.com/arduino/arduino-cli/releases/download/v${ARDUINO_CLI_VERSION}/arduino-cli_${ARDUINO_CLI_VERSION}_Linux_64bit.tar.gz" \
 && echo "${ARDUINO_CLI_SHA256}  /tmp/cli.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/cli.tar.gz -C /usr/local/bin arduino-cli \
 && rm /tmp/cli.tar.gz

# The core and its tools live in the image. The container runs as the host user (files it writes in
# the bind-mounted project are theirs), so the arduino directories are writable by any user.
ENV ARDUINO_DIRECTORIES_DATA=/opt/arduino/data \
    ARDUINO_DIRECTORIES_DOWNLOADS=/opt/arduino/downloads \
    ARDUINO_DIRECTORIES_USER=/opt/arduino/user \
    ARDUINO_UPDATER_ENABLE_NOTIFICATION=false \
    HOME=/tmp
RUN arduino-cli core update-index \
 && arduino-cli core install "${RENESAS_CORE}" \
 && rm -rf /opt/arduino/downloads/* \
 && chmod -R a+rwX /opt/arduino

WORKDIR /work
