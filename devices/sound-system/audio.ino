/*
 * Second life for old audio systems
 * ---------------------------------
 *
 * Compatible with Sony HCD-H150/H500
 * Coded by Cibran Docampo
 *
 * Description:
 * Automatically detects audio signals from TV or Chromecast inputs and
 * controls the sound system accordingly. When audio is detected, the system
 * turns on and switches to the appropriate input. When no audio is detected
 * for a period of time, the system automatically turns off.
 */

// ============================================================================
// PIN CONFIGURATION
// ============================================================================

// Sound inputs (analog pins)
const int CC_SOUND_INPUT_PIN = A4;  // Chromecast in Phono input
const int TV_SOUND_INPUT_PIN = A5;  // TV in CD input

// Action relays output (digital pins)
const int ON_RELAY_PIN = 8;   // Turn on/off the sound system
const int TV_RELAY_PIN = 9;   // Switch to TV input (CD)
const int CC_RELAY_PIN = 10;  // Switch to Chromecast input (Phono)

// Info LED output (digital pin)
const int LED_PIN = 13;

// ============================================================================
// CONFIGURATION CONSTANTS
// ============================================================================

// Signal detection thresholds (0-1023 for 10-bit ADC)
const int CC_THRESHOLD = 2;   // Minimum analog value to detect Chromecast signal
const int TV_THRESHOLD = 4;   // Minimum analog value to detect TV signal

// Timing constants (in milliseconds)
const int RELAY_PULSE_DURATION = 500;      // Duration of relay pulse
const int SIGNAL_CONFIRM_DELAY = 10;       // Delay between signal checks
const int CC_CONFIRM_SAMPLES = 30;         // Number of samples to confirm CC signal (30 * 10ms = 300ms)
const int TV_CONFIRM_SAMPLES = 20;         // Number of samples to confirm TV signal (20 * 10ms = 200ms)
const int SIGNAL_LOSS_SAMPLES = 100;       // Samples before turning off (100 * 10ms = 1 second)
const int LED_BLINK_DURATION = 150;        // LED blink duration on startup
const int LOOP_DELAY = 50;                 // Delay in main loop to prevent excessive CPU usage

// Serial communication
const int SERIAL_BAUD_RATE = 9600;

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

enum SystemState {
  STATE_OFF,           // System is off
  STATE_TV_ACTIVE,     // System is on and using TV input
  STATE_CC_ACTIVE      // System is on and using Chromecast input
};

SystemState currentState = STATE_OFF;

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Configure pins
  pinMode(LED_PIN, OUTPUT);
  pinMode(ON_RELAY_PIN, OUTPUT);
  pinMode(TV_RELAY_PIN, OUTPUT);
  pinMode(CC_RELAY_PIN, OUTPUT);
  
  // Ensure all relays are off initially
  digitalWrite(ON_RELAY_PIN, LOW);
  digitalWrite(TV_RELAY_PIN, LOW);
  digitalWrite(CC_RELAY_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  // Initialize serial communication
  Serial.begin(SERIAL_BAUD_RATE);
  delay(100); // Allow serial port to initialize
  
  // Flash the LED twice to show the program has started
  Serial.println("=== Sound System Controller Starting ===");
  blinkLED(2);
  
  Serial.println("System initialized and ready");
  Serial.print("CC Threshold: "); Serial.println(CC_THRESHOLD);
  Serial.print("TV Threshold: "); Serial.println(TV_THRESHOLD);
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // Check TV signal first (higher priority)
  if (checkTvSignalLevel()) {
    if (currentState != STATE_TV_ACTIVE) {
      Serial.println("TV signal detected - Activating TV mode");
      turnOnSystem();
      switchToTv();
      currentState = STATE_TV_ACTIVE;
    }
    // Monitor TV signal while active
    monitorActiveSignal(TV_SOUND_INPUT_PIN, TV_THRESHOLD, "TV");
  }
  // Check Chromecast signal if TV is not active
  else if (checkCcSignalLevel()) {
    if (currentState != STATE_CC_ACTIVE) {
      Serial.println("Chromecast signal detected - Activating Chromecast mode");
      turnOnSystem();
      switchToCc();
      currentState = STATE_CC_ACTIVE;
    }
    // Monitor Chromecast signal while active
    monitorActiveSignal(CC_SOUND_INPUT_PIN, CC_THRESHOLD, "Chromecast");
  }
  // No signal detected
  else {
    if (currentState != STATE_OFF) {
      Serial.println("No signal detected - Turning off system");
      turnOffSystem();
      currentState = STATE_OFF;
    }
  }
  
  delay(LOOP_DELAY);
}

// ============================================================================
// SIGNAL DETECTION FUNCTIONS
// ============================================================================

/**
 * Checks if Chromecast signal level is above threshold
 * @return true if signal is confirmed, false otherwise
 */
bool checkCcSignalLevel() {
  int signalLevel = analogRead(CC_SOUND_INPUT_PIN);
  if (signalLevel >= CC_THRESHOLD) {
    return confirmSignal(CC_SOUND_INPUT_PIN, CC_THRESHOLD, CC_CONFIRM_SAMPLES);
  }
  return false;
}

/**
 * Checks if TV signal level is above threshold
 * @return true if signal is confirmed, false otherwise
 */
bool checkTvSignalLevel() {
  int signalLevel = analogRead(TV_SOUND_INPUT_PIN);
  if (signalLevel >= TV_THRESHOLD) {
    return confirmSignal(TV_SOUND_INPUT_PIN, TV_THRESHOLD, TV_CONFIRM_SAMPLES);
  }
  return false;
}

/**
 * Confirms that a signal is stable by checking multiple samples
 * @param pin The analog pin to read from
 * @param threshold The minimum value to consider as signal
 * @param samples Number of consecutive samples required
 * @return true if signal is confirmed stable, false otherwise
 */
bool confirmSignal(int pin, int threshold, int samples) {
  int validSamples = 0;
  
  for (int i = 0; i < samples; i++) {
    if (analogRead(pin) >= threshold) {
      validSamples++;
    } else {
      validSamples = 0; // Reset counter if signal drops
    }
    delay(SIGNAL_CONFIRM_DELAY);
  }
  
  return (validSamples >= samples);
}

/**
 * Monitors an active signal and turns off system if signal is lost
 * @param pin The analog pin to monitor
 * @param threshold The minimum value to consider as signal
 * @param sourceName Name of the signal source (for logging)
 */
void monitorActiveSignal(int pin, int threshold, const char* sourceName) {
  int noSignalCount = 0;
  
  for (int i = 0; i < SIGNAL_LOSS_SAMPLES; i++) {
    if (analogRead(pin) < threshold) {
      noSignalCount++;
    } else {
      noSignalCount = 0; // Reset if signal returns
    }
    delay(SIGNAL_CONFIRM_DELAY);
    
    // If signal returns, exit monitoring
    if (noSignalCount == 0) {
      return;
    }
  }
  
  // Signal lost for required duration
  Serial.print(sourceName);
  Serial.println(" signal lost - System will turn off");
}

// ============================================================================
// SYSTEM CONTROL FUNCTIONS
// ============================================================================

/**
 * Pulses the power relay to turn on the system
 */
void turnOnSystem() {
  Serial.println("Turning ON sound system...");
  pulseRelay(ON_RELAY_PIN);
  delay(100); // Small delay after turning on
}

/**
 * Pulses the power relay to turn off the system
 */
void turnOffSystem() {
  Serial.println("Turning OFF sound system...");
  pulseRelay(ON_RELAY_PIN);
  delay(100); // Small delay after turning off
}

/**
 * Switches input to Chromecast (Phono)
 */
void switchToCc() {
  Serial.println("Switching to Chromecast input (Phono)");
  pulseRelay(CC_RELAY_PIN);
}

/**
 * Switches input to TV (CD)
 */
void switchToTv() {
  Serial.println("Switching to TV input (CD)");
  pulseRelay(TV_RELAY_PIN);
}

/**
 * Pulses a relay pin for the configured duration
 * @param pin The relay pin to pulse
 */
void pulseRelay(int pin) {
  digitalWrite(pin, HIGH);
  delay(RELAY_PULSE_DURATION);
  digitalWrite(pin, LOW);
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Blinks the LED a specified number of times
 * @param times Number of times to blink
 */
void blinkLED(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(LED_BLINK_DURATION);
    digitalWrite(LED_PIN, LOW);
    if (i < times - 1) {
      delay(LED_BLINK_DURATION);
    }
  }
}
