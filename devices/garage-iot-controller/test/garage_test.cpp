// Host test for the door/light state machine. Run with ./run.sh
#include "../firmware/config.h"
#include "../firmware/garage.h"
#include "../firmware/watchdog.h"
#include "../firmware/settings.h"
#include "../firmware/json.h"
#include <cstdio>
#include <cstdlib>

int pins[32];
uint32_t fakeMillis;

using namespace garage;
static int failures = 0;

#define CHECK(cond) \
  do { if (!(cond)) { printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); ++failures; } } while (0)

static void run(uint32_t ms) { for (uint32_t i = 0; i < ms / 10; ++i) tick(); }
static void sensor(bool closed) { pins[cfg::PIN_DOOR_SENSOR] = (closed == cfg::DOOR_SENSOR_ACTIVE_LOW) ? LOW : HIGH; }
static void night(bool n) { pins[cfg::PIN_LDR] = (n == cfg::LDR_HIGH_IS_NIGHT); }
static void button(bool pressed) { pins[cfg::PIN_BUTTON] = (pressed == cfg::BUTTON_ACTIVE_LOW) ? LOW : HIGH; }
static void press() { button(true); run(100); button(false); run(100); }
static void boot(bool closed, bool isNight) {
  memset(pins, 0, sizeof pins);
  button(false);
  sensor(closed);
  night(isNight);
  begin();
}

int main() {
  // Open and close through the API, by day.
  boot(true, false);
  CHECK(state().door == Door::Closed);
  CHECK(doorClose() == Cmd::Noop);
  CHECK(doorOpen() == Cmd::Ok);
  CHECK(pins[cfg::PIN_RELAY_DOOR] == HIGH);
  CHECK(state().door == Door::Opening);
  CHECK(doorOpen() == Cmd::Noop);
  CHECK(doorClose() == Cmd::Busy);
  run(cfg::DOOR_PULSE_MS);
  CHECK(pins[cfg::PIN_RELAY_DOOR] == LOW);
  CHECK(!state().light);  // daytime: no auto light
  sensor(false);
  run(cfg::DOOR_TRAVEL_MS);
  CHECK(state().door == Door::Open);
  CHECK(pins[LED_BUILTIN] == HIGH);
  CHECK(doorOpen() == Cmd::Noop);
  CHECK(doorClose() == Cmd::Ok);
  CHECK(state().door == Door::Closing);
  run(8000);
  sensor(true);
  run(200);
  CHECK(state().door == Door::Closed);
  CHECK(state().doorSource == Source::Api);

  // Door that does not move goes back to closed.
  boot(true, false);
  doorOpen();
  run(cfg::DOOR_TRAVEL_MS - 100);
  CHECK(state().door == Door::Opening);
  run(200);
  CHECK(state().door == Door::Closed);

  // Door that never reaches the sensor ends up open, with the close reported as failed.
  boot(false, false);
  CHECK(state().door == Door::Open && !state().closeFailed);
  CHECK(doorClose() == Cmd::Ok);
  run(cfg::DOOR_CLOSE_TIMEOUT_MS - 100);
  CHECK(state().door == Door::Closing && !state().closeFailed);
  run(200);
  CHECK(state().door == Door::Open && state().closeFailed);
  LogEntry last;
  CHECK(recent(&last, 1) == 1 && last.event == Event::CloseFailed && last.source == Source::Api);
  // Cleared when the sensor finally reports closed (closed by hand, or late).
  sensor(true);
  run(200);
  CHECK(state().door == Door::Closed && !state().closeFailed);

  // Cleared by a new pulse, and judged again on the next close.
  boot(false, false);
  doorClose();
  run(cfg::DOOR_CLOSE_TIMEOUT_MS + 100);
  CHECK(state().closeFailed);
  CHECK(doorClose() == Cmd::Ok);
  CHECK(state().door == Door::Closing && !state().closeFailed);

  // A slow close (opener recalibrating, 30 s) is not a failure.
  boot(false, false);
  doorClose();
  run(30000);
  sensor(true);
  run(200);
  CHECK(state().door == Door::Closed && !state().closeFailed);

  // Stopping a close on purpose is not a failure.
  boot(false, false);
  doorClose();
  run(5000);
  CHECK(doorStop() == Cmd::Ok);
  run(cfg::DOOR_CLOSE_TIMEOUT_MS + 100);
  CHECK(state().door == Door::Open && !state().closeFailed);

  // Close from the push button that fails: reported with the button as source.
  boot(false, false);
  press();
  CHECK(state().door == Door::Closing);
  run(cfg::DOOR_CLOSE_TIMEOUT_MS);
  CHECK(state().closeFailed);
  CHECK(recent(&last, 1) == 1 && last.event == Event::CloseFailed && last.source == Source::Button);

  // Physical button at night: opens and turns the light on with a timer.
  boot(true, true);
  press();
  CHECK(state().door == Door::Opening);
  CHECK(state().doorSource == Source::Button);
  CHECK(state().light && state().lightTimed);
  CHECK(pins[cfg::PIN_RELAY_LIGHT] == HIGH);
  run(cfg::LIGHT_DEFAULT_S * 1000);
  CHECK(!state().light);
  CHECK(pins[cfg::PIN_RELAY_LIGHT] == LOW);

  // Stop while moving, and pulse rate limit.
  boot(true, false);
  doorOpen();
  CHECK(doorStop() == Cmd::Busy);  // too soon after the previous pulse
  sensor(false);
  run(3000);
  CHECK(doorStop() == Cmd::Ok);
  CHECK(state().door == Door::Open);
  run(2000);
  CHECK(doorStop() == Cmd::Noop);

  // Opened without the board (by hand) at night: detected through the sensor.
  boot(true, true);
  sensor(false);
  run(200);
  CHECK(state().door == Door::Opening);
  CHECK(state().doorSource == Source::Sensor);
  CHECK(state().light);
  CHECK(pins[cfg::PIN_RELAY_DOOR] == LOW);

  // Light: manual timer, no timer, off, and auto light does not shorten a manual hold.
  boot(true, true);
  lightOn(30);
  CHECK(state().lightRemainingS == 30);
  run(29000);
  CHECK(state().light);
  run(1100);
  CHECK(!state().light);
  CHECK(lightOff() == Cmd::Noop);
  CHECK(lightOn(0) == Cmd::Ok);
  run(600000);
  CHECK(state().light && !state().lightTimed);
  const uint32_t revHeld = state().rev;
  CHECK(lightOn(0) == Cmd::Noop);  // already on without a timer
  CHECK(state().rev == revHeld);
  doorOpen();
  CHECK(state().light && !state().lightTimed);
  CHECK(lightOff() == Cmd::Ok);
  CHECK(!state().light);

  // Event log: newest first, with the source, and it wraps without losing the latest entries.
  boot(true, true);
  LogEntry ev[cfg::LOG_SIZE];
  CHECK(recent(ev, cfg::LOG_SIZE) == 2 && ev[1].event == Event::Boot);
  CHECK(ev[0].event == Event::DoorClosed && ev[0].source == Source::Sensor && ev[0].reason == Reason::Startup);
  run(5000);
  press();
  CHECK(recent(ev, cfg::LOG_SIZE) == 4);  // a press that fires the relay is logged as the door event only
  CHECK(ev[0].event == Event::LightOn && ev[0].source == Source::Auto && ev[0].value == cfg::LIGHT_DEFAULT_S);
  CHECK(ev[1].event == Event::DoorOpening && ev[1].source == Source::Button && ev[1].reason == Reason::Command &&
        ev[1].t == 5);
  CHECK(ev[2].event == Event::DoorClosed && ev[2].reason == Reason::Startup);
  CHECK(ev[3].event == Event::Boot && ev[3].t == 0);
  CHECK(recent(ev, 2) == 2 && ev[0].event == Event::LightOn);
  note(Event::WifiUp);
  CHECK(recent(ev, 1) == 1 && ev[0].event == Event::WifiUp);
  for (size_t i = 0; i < cfg::LOG_SIZE; ++i) { lightOn(0); lightOff(); }
  CHECK(recent(ev, cfg::LOG_SIZE) == cfg::LOG_SIZE);
  CHECK(ev[0].event == Event::LightOff && ev[0].source == Source::Api);
  CHECK(ev[cfg::LOG_SIZE - 1].event == Event::LightOn);

  // Every door event carries the reason that caused it.
  auto lastIs = [&](Event e, Source src, Reason why) {
    LogEntry x;
    return recent(&x, 1) == 1 && x.event == e && x.source == src && x.reason == why;
  };
  boot(false, false);
  CHECK(lastIs(Event::DoorOpen, Source::Sensor, Reason::Startup));
  sensor(true);
  run(200);
  CHECK(lastIs(Event::DoorClosed, Source::Sensor, Reason::SensorClosed));  // detected, not commanded
  boot(true, false);
  press();
  CHECK(lastIs(Event::DoorOpening, Source::Button, Reason::Command));
  button(true); run(100); button(false); run(100);  // second press, too soon
  CHECK(lastIs(Event::ButtonIgnored, Source::Button, Reason::TooSoon));
  run(cfg::DOOR_TRAVEL_MS);
  CHECK(lastIs(Event::DoorClosed, Source::Button, Reason::NoMovement));
  press();
  sensor(false);
  run(cfg::DOOR_TRAVEL_MS);
  CHECK(lastIs(Event::DoorOpen, Source::Button, Reason::TravelEnd));
  CHECK(doorClose() == Cmd::Ok);
  CHECK(lastIs(Event::DoorClosing, Source::Api, Reason::Command));
  run(3000);
  CHECK(doorStop() == Cmd::Ok);
  CHECK(lastIs(Event::DoorOpen, Source::Api, Reason::Stopped));
  run(2000);
  doorClose();
  run(5000);
  sensor(true);
  run(200);
  CHECK(lastIs(Event::DoorClosed, Source::Api, Reason::SensorClosed));
  sensor(false);
  run(200);
  CHECK(lastIs(Event::DoorOpening, Source::Sensor, Reason::SensorReleased));
  sensor(true);
  run(200);
  CHECK(lastIs(Event::DoorClosed, Source::Sensor, Reason::CameBack));
  sensor(false);
  run(cfg::DOOR_TRAVEL_MS + 500);
  sensor(true);
  run(200);
  CHECK(lastIs(Event::DoorClosed, Source::Sensor, Reason::SensorClosed));
  sensor(false);
  run(cfg::DOOR_TRAVEL_MS + 500);
  doorClose();
  run(cfg::DOOR_CLOSE_TIMEOUT_MS + 100);
  CHECK(recent(ev, 2) == 2 && ev[0].event == Event::CloseFailed && ev[0].value == cfg::DOOR_CLOSE_TIMEOUT_MS / 1000 &&
        ev[1].event == Event::DoorClosing);  // close_failed replaces door_open
  CHECK(lightOn(0) == Cmd::Ok);
  CHECK(recent(ev, 1) == 1 && ev[0].event == Event::LightOn && ev[0].source == Source::Api && ev[0].value == 0);

  // Uptime keeps counting past 2^32 ticks (497 days): times and ages stay right.
  boot(true, false);
  run(10000);
  CHECK(doorOpen() == Cmd::Ok);
  testSkipTicks(0xFFFFFFFFull - 500);  // 5 s before the 32-bit limit, door still "opening"
  run(8000);                           // crosses it
  const uint32_t days497 = 42949672;   // 2^32 ticks in seconds
  CHECK(state().uptimeS == days497 + 13);
  CHECK(state().door == Door::Opening && state().doorSinceS == days497 + 3);
  CHECK(lightOn(30) == Cmd::Ok);
  CHECK(recent(ev, 1) == 1 && ev[0].event == Event::LightOn && ev[0].t == days497 + 13);
  run(30000);
  CHECK(!state().light);

  // Button noise shorter than the debounce time is ignored; a held button fires once.
  boot(true, false);
  button(true); run(20); button(false); run(200);
  CHECK(state().door == Door::Closed);
  button(true); run(cfg::DOOR_TRAVEL_MS + 500);
  CHECK(state().door == Door::Closed);  // sensor still closed when the travel time ended
  uint32_t r = state().rev;
  run(5000);
  CHECK(state().rev == r);

  // A button already held when the board boots does not trigger.
  boot(true, false);
  button(true);
  begin();
  run(2000);
  CHECK(state().door == Door::Closed && state().button);

  // Watchdog: refreshed while the main loop is alive, never once it stalls for WATCHDOG_LOOP_S.
  CHECK(watchdog::begin(false) == false);
  watchdog::tick();
  CHECK(watchdog::testRefreshes() == 0);  // no hardware watchdog without the timer
  CHECK(watchdog::begin(true));
  const uint32_t loopTicks = cfg::WATCHDOG_LOOP_S * 100;
  for (uint32_t i = 0; i < 3 * loopTicks; ++i) {
    if (i % 1000 == 0) watchdog::heartbeat();  // main loop alive, even with 10 s gaps (WiFi.begin)
    watchdog::tick();
  }
  CHECK(watchdog::testRefreshes() == 3 * loopTicks);
  const uint32_t before = watchdog::testRefreshes();
  watchdog::heartbeat();
  for (uint32_t i = 0; i < 2 * loopTicks; ++i) watchdog::tick();  // main loop stalls
  CHECK(watchdog::testRefreshes() - before == loopTicks);         // refreshes stop after 60 s
  watchdog::heartbeat();
  watchdog::tick();
  CHECK(watchdog::testRefreshes() - before == loopTicks + 1);     // (before the reset: resumes)

  // Door timings from the settings apply to the next movement.
  boot(true, false);
  setTimings(10, 15);
  doorOpen();
  sensor(false);
  run(9900);
  CHECK(state().door == Door::Opening);
  run(200);
  CHECK(state().door == Door::Open);
  run(2000);
  doorClose();
  run(14900);
  CHECK(state().door == Door::Closing);
  run(200);
  CHECK(state().closeFailed);
  CHECK(recent(ev, 1) == 1 && ev[0].event == Event::CloseFailed && ev[0].value == 15);
  setTimings(cfg::DOOR_TRAVEL_MS / 1000, cfg::DOOR_CLOSE_TIMEOUT_MS / 1000);

  // Settings: defaults when the flash is blank, save/load, newest copy wins, a corrupted copy is skipped.
  memset(settings::testFlash(), 0xFF, 2048);
  settings::begin();
  CHECK(!settings::stored() && !settings::configured());
  CHECK(!strcmp(settings::get().name, "Garage") && settings::get().openS == cfg::DOOR_TRAVEL_MS / 1000);
  settings::Data d = settings::defaults();
  strcpy(d.ssid, "home");
  strcpy(d.password, "secret123");
  strcpy(d.token, "tok-12345");
  CHECK(settings::save(d));
  settings::begin();  // as after a reset
  CHECK(settings::stored() && settings::configured() && !strcmp(settings::get().password, "secret123"));
  d.openS = 25;
  CHECK(settings::save(d));  // goes to the other block
  settings::begin();
  CHECK(settings::get().openS == 25);
  settings::testFlash()[1024 + 20] ^= 0x55;  // corrupt the newest copy (second block)
  settings::begin();
  CHECK(settings::stored() && settings::get().openS == cfg::DOOR_TRAVEL_MS / 1000);  // previous copy
  settings::testFlash()[20] ^= 0x55;  // corrupt both
  settings::begin();
  CHECK(!settings::stored());

  // Settings validation.
  d = settings::defaults();
  CHECK(settings::validate(d) == nullptr);
  d.openS = 4;
  CHECK(settings::validate(d) && !strcmp(settings::validate(d), "invalid_open_time"));
  d = settings::defaults();
  d.closeS = 181;
  CHECK(settings::validate(d) && !strcmp(settings::validate(d), "invalid_close_time"));
  d = settings::defaults();
  strcpy(d.token, "short");
  CHECK(settings::validate(d) && !strcmp(settings::validate(d), "invalid_token"));
  strcpy(d.token, "has space1");
  CHECK(settings::validate(d) && !strcmp(settings::validate(d), "invalid_token"));
  d = settings::defaults();
  strcpy(d.ssid, "x");
  strcpy(d.password, "1234567");
  CHECK(settings::validate(d) && !strcmp(settings::validate(d), "invalid_password"));
  d.name[0] = 0;
  CHECK(settings::validate(d) != nullptr);
  CHECK(!settings::save(d));

  // JSON field readers.
  char out[16];
  uint32_t n = 0;
  const char* body = "{\"name\" : \"Ga\\\"r\\u0041ge\", \"open_s\":30, \"token\":\"abc\", \"x\":\"name\"}";
  CHECK(json::str(body, "name", out, sizeof out) == json::Ok && !strcmp(out, "Ga\"rAge"));
  CHECK(json::num(body, "open_s", n) == json::Ok && n == 30);
  CHECK(json::str(body, "missing", out, sizeof out) == json::Missing);
  CHECK(json::str(body, "open_s", out, sizeof out) == json::Invalid);  // not a string
  CHECK(json::num(body, "token", n) == json::Invalid);
  CHECK(json::str("{\"a\":\"0123456789abcdefXYZ\"}", "a", out, sizeof out) == json::Invalid);  // too long
  CHECK(json::str("{\"a\":\"\\u00e9\"}", "a", out, sizeof out) == json::Invalid);  // escaped non-ASCII
  CHECK(json::str("{\"a\":\"caf\xc3\xa9\"}", "a", out, sizeof out) == json::Ok && !strcmp(out, "caf\xc3\xa9"));
  CHECK(json::str("{\"a\":\"unterminated}", "a", out, sizeof out) == json::Invalid);
  CHECK(json::num("{\"a\":1.5}", "a", n) == json::Invalid);

  printf(failures ? "%d FAILED\n" : "all tests passed\n", failures);
  return failures ? EXIT_FAILURE : EXIT_SUCCESS;
}
