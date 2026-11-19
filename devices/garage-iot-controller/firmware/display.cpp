#include "display.h"
#include "config.h"
#include "garage.h"
#include "net.h"
#include <Arduino_LED_Matrix.h>

// Layout (12 columns x 8 rows):
//
//   rows 0-4  INPUTS   a letter appears while the input is active:
//             N = night (light sensor) | C = door sensor closed | B = button pressed
//   rows 6-7  OUTPUTS  a bar lights while active:
//             light relay | door relay | WiFi (blinks while disconnected, off when not configured)
//
// In setup mode the top rows show "SET" instead of the inputs.
//
// Left column is the light, middle column is the door.
// The IP address is shown in full after connecting and its last octet every
// DISPLAY_IP_EVERY_S seconds.

namespace display {
namespace {

constexpr uint32_t REFRESH_MS = 50;
constexpr uint32_t HOLD_MS = 700;        // short events stay visible at least this long
constexpr uint32_t OCTET_MS = 1300;      // per octet when showing the full IP
constexpr uint32_t LAST_OCTET_MS = 2000;

// Glyphs are 3 pixels wide, one byte per row (bit 2 = left pixel).
const uint8_t LETTER_N[5] = {5, 7, 7, 7, 5};
const uint8_t LETTER_C[5] = {3, 4, 4, 4, 3};
const uint8_t LETTER_B[5] = {6, 5, 6, 5, 6};
const uint8_t BAR[2]      = {7, 7};
const uint8_t LETTER_S[5] = {7, 4, 7, 1, 7};
const uint8_t LETTER_E[5] = {7, 4, 6, 4, 7};
const uint8_t LETTER_T[5] = {7, 2, 2, 2, 2};

const uint8_t DIGITS[10][5] = {
  {7, 5, 5, 5, 7}, {2, 6, 2, 2, 7}, {7, 1, 7, 4, 7}, {7, 1, 7, 1, 7}, {5, 5, 7, 1, 1},
  {7, 4, 7, 1, 7}, {7, 4, 7, 5, 7}, {7, 1, 1, 1, 1}, {7, 5, 7, 5, 7}, {7, 5, 7, 1, 7},
};

ArduinoLEDMatrix matrix;
uint32_t shown[3] = {~0u, ~0u, ~0u};
uint32_t lastRefresh = 0;
uint32_t buttonSeen = 0, relaySeen = 0;
bool     buttonHeld = false, relayHeld = false;

// IP screens: a short queue of numbers, each shown for a while.
uint8_t  queue[4];
uint8_t  queueLen = 0, queuePos = 0;
uint32_t queueStepMs = 0, queueSince = 0;
uint32_t lastIpShown = 0;
uint32_t seenConnects = 0;

void px(uint32_t f[3], int x, int y) {
  if (x < 0 || x >= 12 || y < 0 || y >= 8) return;
  const int bit = y * 12 + x;
  f[bit / 32] |= 1UL << (31 - bit % 32);
}

void icon(uint32_t f[3], int x, int y, const uint8_t* rows, int n) {
  for (int r = 0; r < n; ++r)
    for (int c = 0; c < 3; ++c)
      if (rows[r] & (4 >> c)) px(f, x + c, y + r);
}

void drawNumber(uint32_t f[3], uint8_t n) {
  const int count = n >= 100 ? 3 : n >= 10 ? 2 : 1;
  int x = (12 - (count * 4 - 1)) / 2;
  if (count == 3) { icon(f, x, 1, DIGITS[n / 100], 5); x += 4; }
  if (count >= 2) { icon(f, x, 1, DIGITS[(n / 10) % 10], 5); x += 4; }
  icon(f, x, 1, DIGITS[n % 10], 5);
  for (int i = 0; i <= queuePos; ++i) px(f, i * 2, 7);  // which octet this is
}

// Keeps a short pulse visible for HOLD_MS.
bool held(bool active, bool& flag, uint32_t& since, uint32_t now) {
  if (active) {
    flag = true;
    since = now;
  } else if (flag && now - since >= HOLD_MS) {
    flag = false;
  }
  return flag;
}

void drawStatus(uint32_t f[3], uint32_t now) {
  const garage::State st = garage::state();

  const bool button = held(st.button, buttonHeld, buttonSeen, now);
  if (net::mode() == net::Mode::Setup) {
    icon(f, 0, 0, LETTER_S, 5);
    icon(f, 4, 0, LETTER_E, 5);
    icon(f, 8, 0, LETTER_T, 5);
  } else {
    if (st.night) icon(f, 0, 0, LETTER_N, 5);
    if (st.sensorClosed) icon(f, 4, 0, LETTER_C, 5);
    if (button) icon(f, 8, 0, LETTER_B, 5);
  }

  if (st.light) icon(f, 0, 6, BAR, 2);
  if (held(st.relayPulse, relayHeld, relaySeen, now)) icon(f, 4, 6, BAR, 2);
  if (net::mode() != net::Mode::Unconfigured && (net::connected() || ((now / 400) & 1))) icon(f, 8, 6, BAR, 2);
}

void queueIp(bool full, uint32_t now) {
  const uint8_t* ip = net::ipBytes();
  if (full) {
    memcpy(queue, ip, 4);
    queueLen = 4;
    queueStepMs = OCTET_MS;
  } else {
    queue[0] = ip[3];
    queueLen = 1;
    queueStepMs = LAST_OCTET_MS;
  }
  queuePos = full ? 0 : 3;  // the marker dots tell which octet is on screen
  queueSince = now;
  lastIpShown = now;
}

// Returns true while an IP screen is active.
bool stepIp(uint32_t now) {
  if (!net::connected()) {
    queueLen = 0;
    return false;
  }
  if (net::connectCount() != seenConnects) {
    seenConnects = net::connectCount();
    queueIp(true, now);
  } else if (queueLen == 0 && cfg::DISPLAY_IP_EVERY_S > 0 && now - lastIpShown >= cfg::DISPLAY_IP_EVERY_S * 1000UL) {
    queueIp(false, now);
  }
  if (queueLen == 0) return false;
  if (now - queueSince >= queueStepMs) {
    queueSince = now;
    if (queueLen == 1 || ++queuePos >= queueLen) {
      queueLen = 0;
      lastIpShown = now;
      return false;
    }
  }
  return true;
}

}  // namespace

namespace {
bool isOn = true;  // until the settings are loaded
}

void begin() { matrix.begin(); }

void setEnabled(bool on) { isOn = on; }
bool enabled() { return isOn; }

void loop() {
  const uint32_t now = millis();
  if (now - lastRefresh < REFRESH_MS) return;
  lastRefresh = now;

  uint32_t f[3] = {0, 0, 0};
  const bool ipScreen = stepIp(now);
  if (isOn) {
    if (ipScreen) drawNumber(f, queueLen == 1 ? queue[0] : queue[queuePos]);
    else drawStatus(f, now);
  }
  if (f[0] == shown[0] && f[1] == shown[1] && f[2] == shown[2]) return;
  memcpy(shown, f, sizeof shown);
  matrix.loadFrame(f);
}

}  // namespace display
