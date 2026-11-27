#include "garage.h"
#include "config.h"
#include "watchdog.h"

#ifndef HOST_TEST
#include <FspTimer.h>
#endif

namespace garage {
namespace {

constexpr uint32_t TICK_HZ = 100;
constexpr uint32_t ticksOf(uint32_t ms) { return (ms * TICK_HZ + 999) / 1000; }

struct Input {
  bool     state;
  uint16_t count;
};

struct Core {
  uint64_t ticks;       // 64-bit: a 32-bit count would wrap after 497 days
  uint32_t rev;
  Input    button, closed, night;
  Door     door;
  Source   doorSource;
  uint64_t doorSince;   // tick when the door entered its state
  uint32_t doorTimer;   // ticks left for the current movement
  bool     leftClosed;  // sensor released during the current opening
  bool     closeFailed; // last close not confirmed by the sensor; cleared by closing or a new pulse
  uint16_t pulseTicks;  // relay pulse remaining
  uint16_t gapTicks;    // until the next pulse is allowed
  Dir      stopped;     // door stopped part way by a pulse, and in which direction it was going
  uint8_t  queued;      // pulses still to send for an open/close that must reverse first
  Source   queuedSrc;
  bool     light;
  bool     lightTimed;
  uint32_t lightTicks;
  uint32_t openTicks;   // opening time (setting)
  uint32_t closeTicks;  // close confirmation timeout (setting)
  uint32_t lightDefTicks; // light timer for the auto light and the API without a duration (setting)
  uint64_t lightOffAt;  // tick when the light was last switched off
  bool     nightSet;    // night decided from the stored night level (first configure() after boot)
};

volatile bool timerRunning = false;
Core s;

// Light level and the night decision taken from it, before the debounce. Written by the main loop only.
uint16_t      lightLevel = 0;
uint16_t      nightLevel = cfg::NIGHT_LEVEL_DEFAULT;
volatile bool rawNight = false;

LogEntry logBuf[cfg::LOG_SIZE];
size_t   logHead = 0, logCount = 0;

// Call from the tick or with interrupts disabled.
void record(Event e, Source src = Source::None, Reason why = Reason::None, uint32_t value = 0) {
  logBuf[logHead] = {(uint32_t)(s.ticks / TICK_HZ), e, src, why, value};
  logHead = (logHead + 1) % cfg::LOG_SIZE;
  if (logCount < cfg::LOG_SIZE) ++logCount;
}

Event doorEvent(Door d) {
  switch (d) {
    case Door::Closed:  return Event::DoorClosed;
    case Door::Opening: return Event::DoorOpening;
    case Door::Open:    return Event::DoorOpen;
    default:            return Event::DoorClosing;
  }
}

struct Lock {
  Lock() { noInterrupts(); }
  ~Lock() { interrupts(); }
};

// Returns true when the filtered state changes.
bool debounce(Input& in, bool raw, uint16_t ticks) {
  if (raw == in.state) {
    in.count = 0;
    return false;
  }
  if (++in.count < ticks) return false;
  in.state = raw;
  in.count = 0;
  return true;
}

bool readButton() { return (digitalRead(cfg::PIN_BUTTON) == LOW) == cfg::BUTTON_ACTIVE_LOW; }
bool readClosed() { return (digitalRead(cfg::PIN_DOOR_SENSOR) == LOW) == cfg::DOOR_SENSOR_ACTIVE_LOW; }

// Changes the door state and logs it with its reason (unless `log` is false: the caller logs it).
void setDoor(Door d, uint32_t timer, Reason why, bool log = true) {
  s.doorTimer = timer;
  if (why != Reason::Stopped) s.stopped = Dir::None;  // any other change: the door is not stopped part way
  if (s.door == d) return;
  s.door = d;
  s.doorSince = s.ticks;
  if (d == Door::Closed) s.closeFailed = false;
  ++s.rev;
  if (log) record(doorEvent(d), s.doorSource, why);
}

void setLight(bool on, uint32_t ticks, Source src) {
  digitalWrite(cfg::PIN_RELAY_LIGHT, on ? HIGH : LOW);
  if (s.light && !on) s.lightOffAt = s.ticks;
  s.light = on;
  s.lightTimed = on && ticks > 0;
  s.lightTicks = on ? ticks : 0;
  ++s.rev;
  record(on ? Event::LightOn : Event::LightOff, src, Reason::None, on ? ticks / TICK_HZ : 0);
}

void autoLight() {
  if (!cfg::AUTO_LIGHT || !s.night.state) return;
  if (s.light && !s.lightTimed) return;  // manually held on: leave it
  const uint32_t t = s.lightDefTicks;
  setLight(true, s.lightTicks > t ? s.lightTicks : t, Source::Auto);
}

void startOpening(Source src, Reason why) {
  s.doorSource = src;
  s.leftClosed = !s.closed.state;
  setDoor(Door::Opening, s.openTicks, why);
  autoLight();
}

// Fires the opener relay and updates the expected door movement.
bool pulse(Source src) {
  if (s.pulseTicks || s.gapTicks) return false;
  digitalWrite(cfg::PIN_RELAY_DOOR, HIGH);
  s.pulseTicks = ticksOf(cfg::DOOR_PULSE_MS);
  s.gapTicks = ticksOf(cfg::DOOR_PULSE_GAP_MS);
  s.closeFailed = false;  // a new movement: judged again
  ++s.rev;

  switch (s.door) {
    case Door::Closed:
      startOpening(src, Reason::Command);
      break;
    case Door::Open:
      if (s.stopped == Dir::Down) {  // stopped while closing: the opener now opens
        startOpening(src, Reason::Command);
        break;
      }
      s.doorSource = src;
      setDoor(Door::Closing, s.closeTicks, Reason::Command);
      break;
    case Door::Opening:
    case Door::Closing: {  // a pulse while moving stops the door
      const Dir was = s.door == Door::Opening ? Dir::Up : Dir::Down;
      s.doorSource = src;
      setDoor(s.closed.state ? Door::Closed : Door::Open, 0, Reason::Stopped);
      s.stopped = s.door == Door::Open ? was : Dir::None;
      break;
    }
  }
  return true;
}

void stepDoor() {
  const bool closed = s.closed.state;
  switch (s.door) {
    case Door::Closed:
      if (!closed) startOpening(Source::Sensor, Reason::SensorReleased);  // not started by this board
      break;
    case Door::Opening:
      // The sensor bounces while the door starts to move: it is ignored for DOOR_SETTLE_MS.
      if (s.ticks - s.doorSince < ticksOf(cfg::DOOR_SETTLE_MS)) {
        // settling
      } else if (!closed) {
        s.leftClosed = true;
      } else if (s.leftClosed) {
        setDoor(Door::Closed, 0, Reason::CameBack);  // came back down
        break;
      }
      // Travel time over: open only if the closed sensor is not active.
      if (--s.doorTimer == 0) setDoor(closed ? Door::Closed : Door::Open, 0, closed ? Reason::NoMovement : Reason::TravelEnd);
      break;
    case Door::Open:
      if (closed) {
        s.doorSource = Source::Sensor;
        setDoor(Door::Closed, 0, Reason::SensorClosed);
      }
      break;
    case Door::Closing:
      if (closed) {
        setDoor(Door::Closed, 0, Reason::SensorClosed);
      } else if (--s.doorTimer == 0) {  // closed only when the sensor says so
        setDoor(Door::Open, 0, Reason::None, false);  // logged as close_failed instead of door_open
        s.closeFailed = true;
        record(Event::CloseFailed, s.doorSource, Reason::None, s.closeTicks / TICK_HZ);
      }
      break;
  }
}

// Night with hysteresis: from the night level up; back to day only below it minus NIGHT_HYSTERESIS.
void decideNight(bool fresh) {
  const uint16_t dayBelow = nightLevel > cfg::NIGHT_HYSTERESIS ? nightLevel - cfg::NIGHT_HYSTERESIS : 0;
  if (lightLevel >= nightLevel) rawNight = true;
  else if (fresh || lightLevel < dayBelow) rawNight = false;
}

// Light level from the sensor's analog output. Main loop only: analogRead is too slow for the 100 Hz interrupt.
void sampleLightLevel(bool now) {
  static uint32_t last = 0;
  if (!now && millis() - last < cfg::LIGHT_SAMPLE_MS) return;
  last = millis();
  uint32_t sum = 0;
  for (int i = 0; i < 8; ++i) sum += analogRead(cfg::PIN_LIGHT_LEVEL);
  lightLevel = (uint16_t)(sum / 8);
  decideNight(now);
}

#ifndef HOST_TEST
FspTimer timer;
void onTimer(timer_callback_args_t*) {
  tick();
  watchdog::tick();
}

bool startTimer() {
  uint8_t type;
  int8_t ch = FspTimer::get_available_timer(type);
  if (ch < 0) ch = FspTimer::get_available_timer(type, true);
  if (ch < 0) return false;
  return timer.begin(TIMER_MODE_PERIODIC, type, ch, (float)TICK_HZ, 0.0f, onTimer) &&
         timer.setup_overflow_irq() && timer.open() && timer.start();
}
#else
bool startTimer() { return false; }
#endif

}  // namespace

void tick() {
  ++s.ticks;

  if (debounce(s.button, readButton(), ticksOf(cfg::DEBOUNCE_BUTTON_MS))) {
    ++s.rev;
    // A press that fires the relay is logged by the door event it causes; only a refused one is logged here.
    if (s.button.state) s.queued = 0;  // a press cancels a reversing open/close in progress
    if (s.button.state && !pulse(Source::Button)) record(Event::ButtonIgnored, Source::Button, Reason::TooSoon);
  }
  if (debounce(s.closed, readClosed(), ticksOf(cfg::DEBOUNCE_DOOR_MS))) {
    ++s.rev;
    digitalWrite(LED_BUILTIN, s.closed.state ? LOW : HIGH);
  }
  // The sensor sees our own lamp: while it is on, and a little after, night/day is left as it was.
  if (s.light || s.ticks - s.lightOffAt < ticksOf(cfg::LAMP_SETTLE_MS)) {
    s.night.count = 0;
  } else if (debounce(s.night, rawNight, ticksOf(cfg::DEBOUNCE_NIGHT_MS))) {
    ++s.rev;
    record(s.night.state ? Event::Night : Event::Day);
  }

  if (s.pulseTicks && --s.pulseTicks == 0) {
    digitalWrite(cfg::PIN_RELAY_DOOR, LOW);
    ++s.rev;
  }
  if (s.gapTicks) --s.gapTicks;
  if (s.queued && !s.pulseTicks && !s.gapTicks) {
    --s.queued;
    pulse(s.queuedSrc);
  }

  stepDoor();

  if (s.lightTimed && --s.lightTicks == 0) setLight(false, 0, Source::Auto);
}

void begin() {
  pinMode(cfg::PIN_RELAY_LIGHT, OUTPUT);
  pinMode(cfg::PIN_RELAY_DOOR, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(cfg::PIN_RELAY_LIGHT, LOW);
  digitalWrite(cfg::PIN_RELAY_DOOR, LOW);
  pinMode(cfg::PIN_BUTTON, cfg::BUTTON_ACTIVE_LOW ? INPUT_PULLUP : INPUT);
  pinMode(cfg::PIN_DOOR_SENSOR, cfg::DOOR_SENSOR_ACTIVE_LOW ? INPUT_PULLUP : INPUT);

  s = Core{};
  s.openTicks = ticksOf(cfg::DOOR_TRAVEL_MS);
  s.closeTicks = ticksOf(cfg::DOOR_CLOSE_TIMEOUT_MS);
  s.lightDefTicks = cfg::LIGHT_DEFAULT_S * TICK_HZ;
  s.lightOffAt = 0;
  sampleLightLevel(true);
  s.button.state = readButton();  // a button held at boot does not trigger
  s.closed.state = readClosed();
  s.night.state = rawNight;
  s.door = s.closed.state ? Door::Closed : Door::Open;
  digitalWrite(LED_BUILTIN, s.closed.state ? LOW : HIGH);
  logHead = logCount = 0;
  record(Event::Boot);
  s.doorSource = Source::None;  // unknown after a restart: nobody moved it, the state was read from the sensor
  record(doorEvent(s.door), Source::Sensor, Reason::Startup);

  timerRunning = startTimer();
}

void loop() {
  sampleLightLevel(false);
  if (timerRunning) return;
  // Fallback when no hardware timer could be allocated.
  static uint32_t last = millis();
  while (millis() - last >= 1000 / TICK_HZ) {
    last += 1000 / TICK_HZ;
    Lock l;
    tick();
  }
}

State state() {
  Lock l;
  State o;
  o.rev = s.rev;
  o.uptimeS = (uint32_t)(s.ticks / TICK_HZ);
  o.door = s.door;
  o.doorSource = s.doorSource;
  o.stopped = s.stopped;
  o.doorSinceS = (uint32_t)((s.ticks - s.doorSince) / TICK_HZ);
  o.sensorClosed = s.closed.state;
  o.closeFailed = s.closeFailed;
  o.relayPulse = s.pulseTicks > 0;
  o.light = s.light;
  o.lightTimed = s.lightTimed;
  o.lightRemainingS = (s.lightTicks + TICK_HZ - 1) / TICK_HZ;
  o.night = s.night.state;
  o.lightLevel = lightLevel;
  o.button = s.button.state;
  return o;
}

#ifdef HOST_TEST
void testSkipTicks(uint64_t n) { s.ticks += n; }
#endif

bool timerActive() { return timerRunning; }

void configure(const Config& c) {
  Lock l;
  s.openTicks = c.openS * TICK_HZ;
  s.closeTicks = c.closeS * TICK_HZ;
  s.lightDefTicks = c.lightS * TICK_HZ;
  nightLevel = c.nightLevel;
  decideNight(true);
  if (!s.nightSet) {  // at boot: decided from the stored level at once, not 60 s later
    s.night.state = rawNight;
    s.nightSet = true;
  }
}

uint32_t lightDefaultS() {
  Lock l;
  return s.lightDefTicks / TICK_HZ;
}

#ifdef HOST_TEST
void testLightLevel(uint16_t level) {
  lightLevel = level;
  decideNight(false);
}
#endif

uint32_t rev() {
  Lock l;
  return s.rev;
}

size_t recent(LogEntry* out, size_t max) {
  Lock l;
  const size_t n = logCount < max ? logCount : max;
  for (size_t i = 0; i < n; ++i) out[i] = logBuf[(logHead + cfg::LOG_SIZE - 1 - i) % cfg::LOG_SIZE];
  return n;
}

void note(Event e, Source src) {
  Lock l;
  record(e, src);
  ++s.rev;
}

// Open or close when the next pulse would move the door the other way (stopped part way in the opposite
// direction): three pulses, as a person would do it. The door goes the wrong way for ~1 s, stops, then goes.
static Cmd reverseThen(Source src) {
  if (s.queued || !pulse(src)) return Cmd::Busy;
  s.queued = 2;
  s.queuedSrc = src;
  return Cmd::Ok;
}

Cmd doorOpen(Source src) {
  Lock l;
  if (s.queued) return Cmd::Busy;
  switch (s.door) {
    case Door::Closed:  return pulse(src) ? Cmd::Ok : Cmd::Busy;
    case Door::Closing: return Cmd::Busy;
    case Door::Open:
      if (s.stopped == Dir::Up) return reverseThen(src);                      // next pulse would close
      if (s.stopped == Dir::Down) return pulse(src) ? Cmd::Ok : Cmd::Busy;   // next pulse opens
      return Cmd::Noop;                                                       // fully open
    default:            return Cmd::Noop;
  }
}

Cmd doorClose(Source src) {
  Lock l;
  if (s.queued) return Cmd::Busy;
  switch (s.door) {
    case Door::Open:    return s.stopped == Dir::Down ? reverseThen(src) : (pulse(src) ? Cmd::Ok : Cmd::Busy);
    case Door::Opening: return Cmd::Busy;
    default:            return Cmd::Noop;
  }
}

// A stop always leaves the door still: inside the pulse gap (just after an open, or the first pulse of a
// reversal) the stop pulse is queued and sent when the gap ends, instead of being refused.
Cmd doorStop(Source src) {
  Lock l;
  const bool cancelled = s.queued;
  s.queued = 0;
  if (s.door != Door::Opening && s.door != Door::Closing) return cancelled ? Cmd::Ok : Cmd::Noop;
  if (pulse(src)) return Cmd::Ok;
  s.queued = 1;
  s.queuedSrc = src;
  return Cmd::Ok;
}

Cmd doorToggle(Source src) {
  Lock l;
  s.queued = 0;
  return pulse(src) ? Cmd::Ok : Cmd::Busy;
}

Cmd lightOn(uint32_t seconds) {
  Lock l;
  if (seconds == 0 && s.light && !s.lightTimed) return Cmd::Noop;  // a timed request restarts the timer
  setLight(true, seconds * TICK_HZ, Source::Api);
  return Cmd::Ok;
}

Cmd lightOff() {
  Lock l;
  if (!s.light) return Cmd::Noop;
  setLight(false, 0, Source::Api);
  return Cmd::Ok;
}

void lightToggle() {
  Lock l;
  if (s.light) setLight(false, 0, Source::Api);
  else setLight(true, s.lightDefTicks, Source::Api);
}

const char* name(Door d) {
  switch (d) {
    case Door::Closed:  return "closed";
    case Door::Opening: return "opening";
    case Door::Open:    return "open";
    default:            return "closing";
  }
}

const char* name(Dir d) {
  switch (d) {
    case Dir::Up:   return "up";
    case Dir::Down: return "down";
    default:        return "none";
  }
}

const char* name(Event e) {
  switch (e) {
    case Event::Boot:        return "boot";
    case Event::DoorClosed:  return "door_closed";
    case Event::DoorOpening: return "door_opening";
    case Event::DoorOpen:    return "door_open";
    case Event::DoorClosing: return "door_closing";
    case Event::LightOn:     return "light_on";
    case Event::LightOff:    return "light_off";
    case Event::Night:       return "night";
    case Event::Day:         return "day";
    case Event::ButtonIgnored: return "button_ignored";
    case Event::WifiUp:      return "wifi_up";
    case Event::WifiDown:    return "wifi_down";
    case Event::CloseFailed: return "close_failed";
    case Event::WatchdogReset: return "watchdog_reset";
    case Event::SettingsChanged: return "settings_changed";
    case Event::SettingsSaveFailed: return "settings_save_failed";
    case Event::WifiChanged: return "wifi_changed";
    case Event::WifiChangeFailed: return "wifi_change_failed";
    case Event::SetupMode:   return "setup_mode";
    default:                 return "firmware_update_failed";
  }
}

const char* name(Reason r) {
  switch (r) {
    case Reason::Command:        return "command";
    case Reason::Stopped:        return "stopped";
    case Reason::TravelEnd:      return "travel_end";
    case Reason::NoMovement:     return "no_movement";
    case Reason::SensorClosed:   return "sensor_closed";
    case Reason::SensorReleased: return "sensor_released";
    case Reason::CameBack:       return "came_back";
    case Reason::TooSoon:        return "too_soon";
    case Reason::Startup:        return "startup";
    default:                     return "none";
  }
}

const char* name(Source src) {
  switch (src) {
    case Source::Button:   return "button";
    case Source::Api:      return "api";
    case Source::Sensor:   return "sensor";
    case Source::Auto:     return "auto";
    default:               return "none";
  }
}

}  // namespace garage
