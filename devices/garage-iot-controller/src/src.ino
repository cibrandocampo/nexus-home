#include "display.h"
#include "wifi_manager.h"
#include "api_server.h"

// Pin definitions
const int PIN_RELAY_LIGHT   = 2;   // OUTPUT: HIGH = ON
const int PIN_RELAY_DOOR    = 3;   // OUTPUT: HIGH (pulse) = door trigger
const int PIN_BUTTON_DIGITAL = 9;  // INPUT: HIGH = button pressed
const int PIN_DOOR_DIGITAL  = 11;  // INPUT: HIGH = door closed
const int PIN_LDR_DIGITAL   = 12;  // INPUT: HIGH = night
const int PIN_DISPLAY_ENABLE = 13;  // INPUT_PULLUP: LOW = display OFF, HIGH/floating = display ON
const int PIN_LED_DEBUG     = LED_BUILTIN; // ON = door open

// Configuration
const bool LDR_HIGH_IS_NIGHT = true;  // set false if LOW=night

// Timing
const unsigned long LIGHT_DEFAULT_SECONDS = 120;        // Default timeout
const unsigned long DOOR_PULSE_MS         = 400;        // Door relay pulse duration
const unsigned long BUTTON_REFRACT_MS     = 1200;       // Button refractory period

// State variables
bool lightOn = false;
unsigned long lightStartMs = 0;
unsigned long lightDurationMs = LIGHT_DEFAULT_SECONDS * 1000UL;

bool doorPulseActive = false;
unsigned long doorPulseStartMs = 0;

bool buttonLatched = false;          // One-shot: true while "pressed"
unsigned long lastButtonEventMs = 0; // Debounce/security window

// Sensor reading functions
bool isNightNow() {
  int v = digitalRead(PIN_LDR_DIGITAL);
  return LDR_HIGH_IS_NIGHT ? (v == HIGH) : (v == LOW);
}

bool isDoorClosed() {
  return (digitalRead(PIN_DOOR_DIGITAL) == HIGH);
}

bool buttonJustPressed() {
  unsigned long now = millis();
  
  if (now - lastButtonEventMs < BUTTON_REFRACT_MS) return false;

  if (!buttonLatched) {
    if (digitalRead(PIN_BUTTON_DIGITAL) == HIGH) {
      delay(10); // Debounce delay
      if (digitalRead(PIN_BUTTON_DIGITAL) == HIGH) {
        buttonLatched = true;
        lastButtonEventMs = now;
        return true;
      }
    }
  } else {
    if (digitalRead(PIN_BUTTON_DIGITAL) == LOW) {
      buttonLatched = false;
      lastButtonEventMs = now;
    }
  }
  return false;
}

// Actuator control
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
  pinMode(PIN_DISPLAY_ENABLE, INPUT_PULLUP); // Pull-up: LOW = OFF, HIGH/floating = ON
  pinMode(PIN_LED_DEBUG,      OUTPUT);

  digitalWrite(PIN_RELAY_LIGHT, LOW);
  digitalWrite(PIN_RELAY_DOOR,  LOW);

  Serial.begin(115200);
  delay(200);

  matrix.begin();

  // Try to connect WiFi on startup with limited timeout (15 seconds)
  // If it fails, system continues working without WiFi
  Serial.println("[INIT] Attempting WiFi connection (15s timeout)...");
  connectWiFiBlocking(15000);
  Serial.println("[INIT] System ready - door logic operational");
}

void loop() {
  if (buttonJustPressed()) {
    Serial.println("[BTN] Manual press -> Door action");
    handleDoorAction("BUTTON", -1);
  }

  if (doorPulseActive && (millis() - doorPulseStartMs >= DOOR_PULSE_MS)) {
    digitalWrite(PIN_RELAY_DOOR, LOW);
    doorPulseActive = false;
  }

  if (lightOn) {
    unsigned long el = millis() - lightStartMs;
    if (el >= lightDurationMs) {
      setLight(false);
      Serial.println("[TMR] Light OFF (timeout)");
      mxShowStatus();
    }
  }

  digitalWrite(PIN_LED_DEBUG, isDoorClosed() ? LOW : HIGH);

  static unsigned long lastStatusUpdate = 0;
  if (millis() - lastStatusUpdate >= 500) {
    mxShowStatus();
    lastStatusUpdate = millis();
  }

  ensureWiFi();
  processHttpRequests();
}

