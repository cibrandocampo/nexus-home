# Garage IoT Controller

Arduino-based IoT controller for an automated garage door and lighting system using Arduino UNO WiFi R4.

## Hardware

- **Board**: Arduino UNO WiFi R4
- **Display**: Integrated 12x8 LED matrix
- **WiFi**: Built-in WiFi module

### Pin Configuration

| Pin | Type | Description |
|-----|------|-------------|
| 2 | OUTPUT | Light Relay (HIGH = ON) |
| 3 | OUTPUT | Door Relay (HIGH = pulse trigger) |
| 9 | INPUT | Button Digital (HIGH = pressed) |
| 11 | INPUT | Door Sensor Digital (HIGH = closed) |
| 12 | INPUT | LDR Digital (HIGH = night) |
| 13 | INPUT_PULLUP | Display Enable (LOW = display OFF, HIGH/floating = display ON) |
| LED_BUILTIN | OUTPUT | Debug LED (ON = door open) |

## System Logic

### Door Control
- **Trigger**: Button press or API call
- **Action**: 400ms pulse to door relay
- **Auto Light**: If door is closed AND it's night, light turns on automatically
- **State Validation**: 
  - `open` action only works if door is closed
  - `close` action only works if door is open

### Light Control
- **Default Duration**: 12 seconds
- **Auto Mode**: Activates when door is triggered and conditions are met (closed + night)
- **Manual Control**: Via API (`lamp` device with `on`/`off` actions)
- **Timeout**: Automatic turn-off after configured duration

### Sensors

#### Door Sensor (Pin 11)
- **Digital Input**: HIGH = door closed, LOW = door open
- **Debouncing**: 10ms delay + confirmation read to prevent false triggers

#### Button (Pin 9)
- **Digital Input**: HIGH = button pressed, LOW = released
- **Debouncing**: 10ms delay + confirmation read + 1200ms refractory period

#### LDR (Pin 12)
- **Digital Input**: HIGH = night (configurable via `LDR_HIGH_IS_NIGHT`)

### LED Matrix Display

The 12x8 LED matrix shows system status:

**Row 0 (Inputs - 2x2 blocks):**
- **N** (Night): Block at (0,0) when night detected
- **C** (Closed): Block at (3,0) when door is closed
- **I** (Interruptor/Button): Block at (6,0) when button is pressed

**Row 4-6 (Outputs - 3x3 blocks):**
- **L** (Light): Block at (0,4) when light is ON
- **P** (Door Pulse): Block at (4,4) when door pulse is active

**WiFi Bar (Columns 10-11):**
- Vertical bar showing WiFi connection status

**IP Display:**
- When WiFi connects, displays last octet of IP address (e.g., "190") for 5 seconds
- Automatically returns to status display after 5 seconds

**Display Control:**
- Connect pin 13 to GND to turn off display (saves power and reduces heat)
- Leave pin 13 floating or disconnected for normal operation

## WiFi & API

### Configuration
Edit `src/wifi_manager.h`:
```cpp
const char* WIFI_SSID     = "YourSSID";
const char* WIFI_PASSWORD = "YourPassword";
```

### WiFi Behavior
- **Startup**: Attempts connection for 15 seconds, then continues regardless of result
- **Reconnection**: Non-blocking attempts every 60 seconds if disconnected
- **System Operation**: Door logic works independently of WiFi status

### API Endpoints

#### GET /status
Returns current system status:
```json
{
  "door": "closed",
  "light": "off",
  "night": false,
  "light_timeout_ms": 0,
  "network": {
    "connected": true,
    "ip": "192.168.1.190",
    "gateway": "192.168.1.1",
    "subnet": "255.255.255.0",
    "rssi": -58,
    "ssid": "YourSSID"
  }
}
```

#### POST /set
Control devices using `device` and `action` fields:

**Door Control:**
```json
{"device": "door", "action": "open"}
{"device": "door", "action": "close"}
```
- `open`: Only works if door is currently closed
- `close`: Only works if door is currently open
- Returns error 400 if action is not valid for current door state

**Lamp Control:**
```json
{"device": "lamp", "action": "on"}
{"device": "lamp", "action": "on", "duration": 30}
{"device": "lamp", "action": "off"}
```
- `on`: Turns lamp on (optional `duration` in seconds, default: 12)
- `off`: Turns lamp off immediately

**Response Format:**
```json
{"result": "ok", "message": "Door open triggered"}
{"result": "error", "message": "Door is already open"}
```

### Postman Collection
Import `test/Garage_IoT_Controller.postman_collection.json` for testing.

## Code Structure

```
garage-iot-controller/
├── src/
│   ├── src.ino          # Main sketch with pin definitions, sensor reading, and control logic
│   ├── display.h        # LED matrix display functions (status, IP display, display control)
│   ├── wifi_manager.h   # WiFi connection and management (non-blocking reconnection)
│   └── api_server.h     # HTTP API server implementation
├── test/
│   └── Garage_IoT_Controller.postman_collection.json  # Postman collection for API testing
└── README.md
```

**Note**: In Arduino IDE, open the `src` folder as a sketch. The main file `src.ino` must have the same name as its parent folder.

## Configuration Constants

Defined in `src/src.ino`:

```cpp
// Configuration
LDR_HIGH_IS_NIGHT = true  // Set false if LOW=night

// Timing
LIGHT_DEFAULT_SECONDS = 12    // Default light timeout
DOOR_PULSE_MS = 400           // Door relay pulse duration
BUTTON_REFRACT_MS = 1200      // Button refractory period
```

## Features

- **Digital Inputs**: All sensors use digital inputs (no analog thresholds needed)
- **Debouncing**: Button and door sensor include confirmation logic to prevent false triggers
- **Auto Light**: Intelligent lighting based on door state and time of day
- **Non-blocking WiFi**: System operates independently of WiFi status
- **WiFi Reconnection**: Automatic non-blocking reconnection attempts every 60 seconds
- **Visual Status**: Real-time status display on LED matrix
- **IP Display**: Shows last octet of IP address when WiFi connects
- **Display Control**: Pin 13 can disable display to save power
- **REST API**: Full control via HTTP API with state validation
- **Error Handling**: API returns descriptive errors for invalid operations

## Libraries Required

- `Arduino_LED_Matrix` (built-in for UNO R4 WiFi)
- `WiFiS3` (built-in for UNO R4 WiFi)

## License

See LICENSE file.
