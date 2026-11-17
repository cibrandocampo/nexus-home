// Settings stored on the board: WiFi, API token, device name and door timings.
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
};

// Limits checked by validate().
constexpr uint16_t OPEN_MIN_S = 5, OPEN_MAX_S = 120;
constexpr uint16_t CLOSE_MIN_S = 10, CLOSE_MAX_S = 180;
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
#endif

}  // namespace settings
