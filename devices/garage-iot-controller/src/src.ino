#include "display.h"
#include "wifi_manager.h"
#include "api_server.h"

const int PIN_RELAY_LIGHT   = 2;
const int PIN_RELAY_DOOR    = 3;
const int PIN_BUTTON_DIGITAL = 9;
const int PIN_DOOR_DIGITAL  = 11;
const int PIN_LDR_DIGITAL   = 12;
const int PIN_DISPLAY_ENABLE = 6;
const int PIN_LED_DEBUG     = LED_BUILTIN;

const bool LDR_HIGH_IS_NIGHT = true;
const unsigned long LIGHT_DEFAULT_SECONDS = 120;
const unsigned long DOOR_PULSE_MS         = 400;
const unsigned long BUTTON_REFRACT_MS     = 1200;

bool lightOn = false;
unsigned long lightStartMs = 0;
unsigned long lightDurationMs = LIGHT_DEFAULT_SECONDS * 1000UL;
bool doorPulseActive = false;
unsigned long doorPulseStartMs = 0;

bool buttonLatched = false;
unsigned long lastButtonEventMs = 0;

bool isNightNow() {
  int v = digitalRead(PIN_LDR_DIGITAL);
  return LDR_HIGH_IS_NIGHT ? (v == HIGH) : (v == LOW);
}

bool isDoorClosed() {
  // Double read with delay to filter out noise and floating pin states
  // Only returns true if both reads are HIGH (door closed = HIGH signal)
  int read1 = digitalRead(PIN_DOOR_DIGITAL);
  delayMicroseconds(10);
  int read2 = digitalRead(PIN_DOOR_DIGITAL);
  return (read1 == HIGH && read2 == HIGH);
}

bool buttonJustPressed() {
  // Debounced button press detection with refractory period
  // Uses latching to ensure only one press event per button cycle
  unsigned long now = millis();
  
  if (now - lastButtonEventMs < BUTTON_REFRACT_MS) return false;

  if (!buttonLatched) {
    // Waiting for button press: check if HIGH, debounce, then latch
    if (digitalRead(PIN_BUTTON_DIGITAL) == HIGH) {
      delay(10);
      if (digitalRead(PIN_BUTTON_DIGITAL) == HIGH) {
        buttonLatched = true;
        lastButtonEventMs = now;
        return true;
      }
    }
  } else {
    // Button latched: wait for release to reset latch
    if (digitalRead(PIN_BUTTON_DIGITAL) == LOW) {
      buttonLatched = false;
      lastButtonEventMs = now;
    }
  }
  return false;
}

void setLight(bool on) {
  digitalWrite(PIN_RELAY_LIGHT, on ? HIGH : LOW);
  lightOn = on;
  if (on) lightStartMs = millis();
}

void pulseDoor() {
  digitalWrite(PIN_RELAY_DOOR, HIGH);
  doorPulseActive = true;
  doorPulseStartMs = millis();
  Serial.println("[ACT] Door trigger: PULSE HIGH");
  mxShowStatus();
}

void logDecision(const char* source, bool closed, bool night, bool willLight, unsigned long sec) {
  Serial.println("------------------------------------------------");
  Serial.print("[SRC] "); Serial.println(source);
  Serial.print("[SENS] door="); Serial.print(closed ? "CLOSED" : "OPEN");
  Serial.print(" night="); Serial.println(night ? "YES" : "NO");
  if (willLight) {
    Serial.print("[ACT] Light ON for "); Serial.print(sec); Serial.println(" s");
  } else {
    Serial.println("[ACT] Light stays OFF");
  }
  Serial.println("------------------------------------------------");
}

void handleDoorAction(const char* source, long requestedSeconds) {
  // Main door control logic: reads sensors, triggers door relay, and conditionally enables light
  // Light only turns on if door is closed AND it's night time
  bool closed  = isDoorClosed();
  bool night   = isNightNow();

  bool willLight = (closed && night);
  unsigned long sec = (requestedSeconds > 0) ? (unsigned long)requestedSeconds : LIGHT_DEFAULT_SECONDS;

  logDecision(source, closed, night, willLight, sec);

  pulseDoor();

  if (willLight) {
    lightDurationMs = sec * 1000UL;
    setLight(true);
    mxShowStatus();
  }
}
void setup() {
  pinMode(PIN_RELAY_LIGHT,    OUTPUT);
  pinMode(PIN_RELAY_DOOR,     OUTPUT);
  pinMode(PIN_BUTTON_DIGITAL, INPUT);
  pinMode(PIN_DOOR_DIGITAL,   INPUT);
  pinMode(PIN_LDR_DIGITAL,    INPUT);
  pinMode(PIN_DISPLAY_ENABLE, INPUT_PULLUP);
  pinMode(PIN_LED_DEBUG,      OUTPUT);

  digitalWrite(PIN_RELAY_LIGHT, LOW);
  digitalWrite(PIN_RELAY_DOOR,  LOW);

  Serial.begin(115200);
  delay(200);

  matrix.begin();
  connectWiFiBlocking(15000);
}

void loop() {
  // Handle manual button press
  if (buttonJustPressed()) {
    Serial.println("[BTN] Manual press -> Door action");
    handleDoorAction("BUTTON", -1);
  }

  // Door relay pulse timeout: turn off relay after pulse duration
  if (doorPulseActive && (millis() - doorPulseStartMs >= DOOR_PULSE_MS)) {
    digitalWrite(PIN_RELAY_DOOR, LOW);
    doorPulseActive = false;
  }

  // Light timeout: automatically turn off light after configured duration
  if (lightOn) {
    unsigned long el = millis() - lightStartMs;
    if (el >= lightDurationMs) {
      setLight(false);
      Serial.println("[TMR] Light OFF (timeout)");
      mxShowStatus();
    }
  }

  // Debug LED: ON when door is open, OFF when closed
  digitalWrite(PIN_LED_DEBUG, isDoorClosed() ? LOW : HIGH);

  // Update display status every 500ms
  static unsigned long lastStatusUpdate = 0;
  if (millis() - lastStatusUpdate >= 500) {
    mxShowStatus();
    lastStatusUpdate = millis();
  }

  // Maintain WiFi connection and handle HTTP requests
  ensureWiFi();
  processHttpRequests();
}

