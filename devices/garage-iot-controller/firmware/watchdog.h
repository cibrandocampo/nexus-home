// Watchdog: resets the board if the 100 Hz logic or the main loop stops running.
//
// The hardware watchdog allows about 5.6 s at most, less than a WiFi.begin() call (up to 10 s),
// so it is not refreshed from the main loop. The 100 Hz timer interrupt refreshes it instead, but only
// while the main loop has called heartbeat() within cfg::WATCHDOG_LOOP_S:
//   - interrupt (door logic) stuck -> no refresh -> reset after cfg::WATCHDOG_HW_MS
//   - main loop (network, web) stuck -> refreshes stop after cfg::WATCHDOG_LOOP_S -> reset
#pragma once
#include <Arduino.h>

namespace watchdog {

// Reads the reset reason and, if `hardware`, starts the hardware watchdog. Pass false when the logic
// runs from the main loop (no timer): WiFi.begin() would then outlast the hardware timeout.
bool        begin(bool hardware);
void        tick();       // from the timer interrupt
void        heartbeat();  // from the main loop
const char* resetReason();  // why the board last started: power, pin, software, watchdog
bool        resetByWatchdog();

#ifdef HOST_TEST
uint32_t testRefreshes();
#endif

}  // namespace watchdog
