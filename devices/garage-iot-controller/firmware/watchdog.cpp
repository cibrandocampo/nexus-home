#include "watchdog.h"
#include "config.h"

#ifndef HOST_TEST
#include <WDT.h>
#endif

namespace watchdog {
namespace {

constexpr uint32_t LOOP_TICKS = cfg::WATCHDOG_LOOP_S * 100;  // the interrupt runs at 100 Hz

volatile uint32_t sinceBeat = 0;  // interrupt ticks since the last heartbeat
bool              running = false;
const char*       reason = "unknown";
bool              byWatchdog = false;

#ifdef HOST_TEST
uint32_t refreshes = 0;
void refresh() { ++refreshes; }
void readResetReason() {}
#else
void refresh() { WDT.refresh(); }

// Reads and clears the reset flags, so the next reset reports its own cause.
void readResetReason() {
  const uint8_t r0 = R_SYSTEM->RSTSR0;
  const uint16_t r1 = R_SYSTEM->RSTSR1;
  if (r1 & (R_SYSTEM_RSTSR1_WDTRF_Msk | R_SYSTEM_RSTSR1_IWDTRF_Msk)) {
    reason = "watchdog";
    byWatchdog = true;
  } else if (r1 & R_SYSTEM_RSTSR1_SWRF_Msk) {
    reason = "software";  // firmware upload or a reset requested by code
  } else if (r0) {
    reason = "power";     // power-on or low voltage
  } else {
    reason = "pin";       // reset button
  }
  R_SYSTEM->RSTSR0 = 0;
  R_SYSTEM->RSTSR1 = 0;
}
#endif

}  // namespace

bool begin(bool hardware) {
  readResetReason();
  sinceBeat = 0;
  if (!hardware) return running = false;
#ifdef HOST_TEST
  running = true;
#else
  running = WDT.begin(cfg::WATCHDOG_HW_MS);
#endif
  return running;
}

void tick() {
  if (!running) return;
  if (sinceBeat < LOOP_TICKS) {
    ++sinceBeat;
    refresh();
  }
}

void heartbeat() { sinceBeat = 0; }

const char* resetReason() { return reason; }
bool        resetByWatchdog() { return byWatchdog; }

#ifdef HOST_TEST
uint32_t testRefreshes() { return refreshes; }
#endif

}  // namespace watchdog
