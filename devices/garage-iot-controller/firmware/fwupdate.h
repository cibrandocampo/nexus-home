// Firmware update over the network: the WiFi module downloads an .ota file from an http:// URL,
// checks it (magic number and CRC) and reflashes this board with it. This is Arduino's own
// OTA path (OTAUpdate library); see tools/update.sh for the sender side.
#pragma once
#include <Arduino.h>

namespace fwupdate {

// Downloads and verifies the image. nullptr on success, otherwise an error code.
// Blocks for the download (a few seconds on the LAN); feeds the watchdog meanwhile.
const char* fetch(const char* url);

// Starts the reflash of the image fetched before. On success the module resets this board and
// the call does not return; if it returns, the update could not start.
void apply();

}  // namespace fwupdate
