// Settings stored on the board: WiFi, API token, device name, door timings, light timer and night level.
// They replace the old compiled-in secrets.h, so every door runs the same binary.
#pragma once
#include <Arduino.h>

namespace settings {

struct Data {
  char     ssid[33];      // empty = WiFi not configured
  char     password[64];
  char     token[65];     // bearer token for commands and settings
  char     name[33];      // shown on the page, in /info and in Home Assistant
  uint16_t openS;         // opening time
  uint16_t closeS;        // close confirmation timeout
  uint16_t lightS;        // light timer: auto light and API "on" without a duration
  uint16_t nightLevel;    // light level (0-1023, higher = darker) from which it is night
  uint8_t  display;       // LED matrix: 1 on, 0 off
};

// Limits checked by validate().
// The web page shows them as sliders with the same ranges. Stored values outside them (saved by an older
// version with wider limits) are brought into range when loaded, never dropped.
constexpr uint16_t OPEN_MIN_S = 5, OPEN_MAX_S = 100;
constexpr uint16_t CLOSE_MIN_S = 10, CLOSE_MAX_S = 100;
constexpr uint16_t LIGHT_MIN_S = 10, LIGHT_MAX_S = 600;
constexpr uint16_t NIGHT_MIN = 1, NIGHT_MAX = 1023;
constexpr size_t   TOKEN_MIN = 8;

void        begin();         // loads the stored settings, or the defaults if none are valid
const Data& get();
Data        defaults();
bool        configured();    // WiFi network set
bool        stored();        // false: running on defaults (nothing saved yet)
const char* validate(const Data& d);  // nullptr if valid, else an error code
bool        save(const Data& d);      // validates and writes; false on error

#ifdef HOST_TEST
uint8_t* testFlash();
bool     testSaveV1(const Data& d);  // writes d in the 2.0.0-2.0.2 format, as a board before the update has it
#endif

}  // namespace settings
