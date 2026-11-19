// Compile-time configuration: pins, timings and behaviour.
#pragma once
#include <Arduino.h>

#ifndef FW_VERSION  // can be overridden from the build command (bench tests of the update)
#define FW_VERSION "2.0.2"
#endif

namespace cfg {

// ---- Pins ----
constexpr uint8_t PIN_RELAY_LIGHT    = 2;   // OUTPUT, HIGH = light on
constexpr uint8_t PIN_RELAY_DOOR     = 3;   // OUTPUT, HIGH pulse = trigger opener
constexpr uint8_t PIN_DISPLAY_ENABLE = 6;   // INPUT_PULLUP, LOW = LED matrix off
constexpr uint8_t PIN_BUTTON         = 9;   // INPUT_PULLUP, button wired between the pin and GND
constexpr uint8_t PIN_DOOR_SENSOR    = 11;  // INPUT_PULLUP, contact to GND while the door is closed
constexpr uint8_t PIN_LDR            = 12;  // INPUT, digital light sensor
constexpr uint8_t PIN_LIGHT_LEVEL    = A0;  // analog output (AO) of the same light sensor module, only measured for now
constexpr uint8_t PIN_SETUP          = 7;   // INPUT_PULLUP, jumper to GND at boot = setup mode (own WiFi network)

constexpr bool LDR_HIGH_IS_NIGHT = true;

// Button and door sensor are active low: the internal pull-up keeps the pin at 5 V and the contact
// connects it to GND. A loose or broken wire therefore reads "not pressed" / "door not closed".
// Set to false for a contact wired to 5 V (that wiring needs an external pull-down resistor).
constexpr bool BUTTON_ACTIVE_LOW      = true;
constexpr bool DOOR_SENSOR_ACTIVE_LOW = true;

// ---- Door ----
constexpr uint32_t DOOR_PULSE_MS         = 400;    // relay pulse length
constexpr uint32_t DOOR_PULSE_GAP_MS     = 1200;   // minimum time between two pulses
// The two door timings below are defaults: each board stores its own (settings page / setup mode).
constexpr uint32_t DOOR_TRAVEL_MS        = 20000;  // opening time (measured: 16 s); the closed sensor is checked when it ends
// Closing must reach the closed sensor within this time, or the close is reported as failed.
// Measured: 19 s normally, up to 30 s when the opener recalibrates after an incident.
constexpr uint32_t DOOR_CLOSE_TIMEOUT_MS = 40000;
// The closed sensor bounces when the door starts to move (seen on the real door on 2026-11-19): during this
// time after an opening starts it is not read, so a bounce cannot be taken as "came back down".
constexpr uint32_t DOOR_SETTLE_MS        = 3000;

// ---- Light ----
constexpr uint32_t LIGHT_DEFAULT_S = 120;    // default timer for auto light and API "on"
constexpr uint32_t LIGHT_MAX_S     = 86400;  // upper bound accepted by the API
constexpr bool     AUTO_LIGHT      = true;   // light on when the door starts opening at night

// ---- Input filtering ----
constexpr uint32_t DEBOUNCE_BUTTON_MS = 30;
constexpr uint32_t DEBOUNCE_DOOR_MS   = 50;
constexpr uint32_t DEBOUNCE_NIGHT_MS  = 2000;  // avoids flicker at dusk
constexpr uint32_t LIGHT_SAMPLE_MS    = 1000;  // light level: one sample (average of 8 reads) per second

// ---- WiFi ----
constexpr uint32_t WIFI_TRIAL_S = 60;  // a new network from the settings page must connect within this, or the old one is restored

// ---- Watchdog ----
constexpr uint32_t WATCHDOG_HW_MS  = 5000;  // hardware watchdog: the timer interrupt must refresh it this often (max ~5.6 s)
constexpr uint32_t WATCHDOG_LOOP_S = 60;    // main loop stalled this long -> reset (WiFi.begin() blocks up to 10 s)

// ---- Event log ----
constexpr size_t LOG_SIZE = 64;  // most recent events kept in RAM (lost on reset)

// ---- LED matrix (debug display) ----
constexpr uint32_t DISPLAY_IP_EVERY_S = 30;  // show the last IP octet this often (0 = never)

}  // namespace cfg
