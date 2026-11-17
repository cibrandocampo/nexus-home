// Garage IoT Controller v2 - Arduino UNO R4 WiFi
// Door opener + light, with a web UI and a REST API (see ../README.md).
#include "config.h"
#include "display.h"
#include "garage.h"
#include "http.h"
#include "net.h"
#include "settings.h"
#include "watchdog.h"

static void logChanges() {
  static uint32_t lastRev = 0;
  static uint32_t lastLog = 0;
  if (millis() - lastLog < 100) return;
  lastLog = millis();
  const garage::State st = garage::state();
  if (st.rev == lastRev) return;
  lastRev = st.rev;
  char line[120];
  snprintf(line, sizeof line, "[garage] door=%s(%s)%s sensor=%s light=%s(%lus) night=%d button=%d",
           garage::name(st.door), garage::name(st.doorSource), st.closeFailed ? " CLOSE FAILED" : "", st.sensorClosed ? "closed" : "open",
           st.light ? "on" : "off", (unsigned long)st.lightRemainingS, st.night, st.button);
  Serial.println(line);
}

void setup() {
  garage::begin();  // first: relays to a safe state and logic running
  settings::begin();
  garage::setTimings(settings::get().openS, settings::get().closeS);
  Serial.begin(115200);
  pinMode(cfg::PIN_SETUP, INPUT_PULLUP);
  delay(5);  // let the pull-up settle
  const bool setupJumper = digitalRead(cfg::PIN_SETUP) == LOW;
  const net::Mode mode = setupJumper            ? net::Mode::Setup
                         : settings::configured() ? net::Mode::Station
                                                  : net::Mode::Unconfigured;
  display::begin();
  net::begin(mode);
  if (mode == net::Mode::Setup) garage::note(garage::Event::SetupMode);
  const bool wdt = watchdog::begin(garage::timerActive());
  if (watchdog::resetByWatchdog()) garage::note(garage::Event::WatchdogReset);
  Serial.print("[boot] garage controller " FW_VERSION ", reset reason: ");
  Serial.print(watchdog::resetReason());
  Serial.println(wdt ? ", watchdog on" : ", watchdog OFF");
  Serial.println(settings::stored() ? "[boot] settings loaded" : "[boot] no stored settings: defaults");
}

void loop() {
#ifdef WATCHDOG_SELFTEST
  // Bench test only: 1 = main loop hangs, 2 = interrupts stop. Both must end in a watchdog reset.
  if (millis() > 30000) {
    Serial.println("[selftest] hanging now");
    Serial.flush();
    if (WATCHDOG_SELFTEST == 2) noInterrupts();
    for (;;) {}
  }
#endif
  watchdog::heartbeat();
  garage::loop();
  net::loop();
  http::loop();
  display::loop();
  logChanges();
}
