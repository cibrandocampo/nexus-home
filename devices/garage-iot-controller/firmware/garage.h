// Core garage logic: inputs, door state machine, light timer and relays.
// Runs from a 100 Hz timer interrupt so it keeps working while the network stalls.
#pragma once
#include <Arduino.h>

namespace garage {

enum class Door : uint8_t { Closed, Opening, Open, Closing };
// Sensor: change detected by the closed sensor without a pulse from this board (cause unknown).
// Auto: light timer / auto light.
enum class Source : uint8_t { None, Button, Api, Sensor, Auto };
enum class Event : uint8_t {
  Boot, DoorClosed, DoorOpening, DoorOpen, DoorClosing, LightOn, LightOff, Night, Day, ButtonIgnored, WifiUp, WifiDown,
  CloseFailed, WatchdogReset,
  SettingsChanged, SettingsSaveFailed, WifiChanged, WifiChangeFailed, SetupMode, FirmwareUpdateFailed
};
// Why a door event happened, so the log reads as cause -> effect.
enum class Reason : uint8_t {
  None,
  Command,         // pulse with the door stopped: closed -> opening, open -> closing
  Stopped,         // pulse while moving: the opener stops
  TravelEnd,       // opening time over, sensor not closed -> open
  NoMovement,      // opening time over, sensor never released -> still closed
  SensorClosed,    // closed sensor activated -> closed
  SensorReleased,  // closed sensor released without a pulse from this board -> opening
  CameBack,        // closed sensor active again during an opening -> closed
  TooSoon,         // button pressed less than DOOR_PULSE_GAP_MS after the last pulse
  Startup,         // door state read from the sensor at boot
};

struct LogEntry {
  uint32_t t;       // uptime in seconds when it happened
  Event    event;
  Source   source;  // who caused it, when known
  Reason   reason;  // why, for door events
  uint32_t value;   // light_on: timer in seconds (0 = no limit); close_failed: timeout in seconds
};
enum class Cmd : uint8_t { Ok, Noop, Busy };

struct State {
  uint32_t rev;               // increments on every state change
  uint32_t uptimeS;
  Door     door;
  Source   doorSource;        // what caused the last door movement
  uint32_t doorSinceS;        // seconds in the current door state
  bool     sensorClosed;
  bool     closeFailed;       // a close was sent and the sensor did not confirm it in time
  bool     relayPulse;
  bool     light;
  bool     lightTimed;
  uint32_t lightRemainingS;
  bool     night;
  uint16_t lightLevel;        // raw analog light sensor reading, 0-1023 (meaning depends on the module)
  bool     button;
};

void  begin();
void  loop();                 // only does work if the hardware timer is unavailable
void  tick();                 // one 10 ms step (public for host tests)
State state();
uint32_t rev();
bool  timerActive();           // false: no hardware timer, the logic runs from the main loop
void  setTimings(uint32_t openS, uint32_t closeS);  // door timings; apply from the next movement
#ifdef HOST_TEST
void testSkipTicks(uint64_t n);  // jumps the clock forward without running the logic
#endif

Cmd doorOpen(Source src = Source::Api);
Cmd doorClose(Source src = Source::Api);
Cmd doorStop(Source src = Source::Api);
Cmd doorToggle(Source src = Source::Api);

Cmd  lightOn(uint32_t seconds);  // 0 = stay on until turned off
Cmd  lightOff();
void lightToggle();

// Event log: the last cfg::LOG_SIZE events, kept in RAM only.
size_t recent(LogEntry* out, size_t max);  // newest first; returns how many were copied
void   note(Event e, Source src = Source::None);  // for events from outside the core (network, settings)

const char* name(Door d);
const char* name(Event e);
const char* name(Source s);
const char* name(Reason r);

}  // namespace garage
