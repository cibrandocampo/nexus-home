# nexusHome

A modular home automation hub for managing IoT devices in your home. This project consists of two main components: a web platform for centralized device management and Arduino-based controllers for each IoT device.

## Architecture

The project is structured in two main blocks:

### 1. Web Platform
A centralized web application for managing all IoT devices:
- **Backend**: Django or FastAPI (to be implemented)
- **Frontend**: Angular or Vue.js (to be implemented)
- **Purpose**: Provides a unified interface to monitor, control, and configure all connected IoT devices

### 2. Arduino Device Controllers
Individual Arduino-based controllers for each IoT device:
- Each device has its own controller module
- Controllers communicate with the web platform via WiFi
- Each controller exposes a REST API for device control and status monitoring

## Project Structure

```
nexus-home/
├── devices/                    # Arduino device controllers
│   ├── garage-iot-controller/ # Garage door and lighting controller
│   │   ├── src/               # Arduino source code
│   │   ├── test/              # API tests (Postman collection)
│   │   └── README.md          # Device-specific documentation
│   └── sound-system/          # Smart sound system controller
│       ├── audio.ino          # Arduino source code
│       └── README.md          # Device-specific documentation
├── platform/                   # Web platform (to be implemented)
│   ├── backend/               # Django/FastAPI backend
│   └── frontend/              # Angular/Vue.js frontend
└── README.md                  # This file
```

## Current Devices

### Garage IoT Controller
An Arduino-based controller for automated garage door and lighting system using Arduino UNO WiFi R4.

**Features:**
- Garage door control via button or API
- Automatic lighting based on door state and time of day
- Real-time status display on LED matrix
- REST API for remote control
- WiFi connectivity with automatic reconnection

See [devices/garage-iot-controller/README.md](devices/garage-iot-controller/README.md) for detailed documentation.

### Smart Sound System Controller
An Arduino-based controller for automating legacy sound systems (compatible with Sony HCD-H150/H500) using Arduino UNO.

**Features:**
- Automatic audio signal detection from multiple inputs (TV and Chromecast)
- Priority-based input switching (TV has priority over Chromecast)
- Automatic system power management (turns on/off based on signal presence)
- Signal confirmation system to prevent false activations
- Real-time signal monitoring and response
- Serial logging for debugging and monitoring

**How it works:**
The controller continuously monitors audio signal levels from two inputs. When a signal is detected and confirmed, it automatically turns on the sound system and switches to the appropriate input. When no signal is detected for a configured period, it automatically turns off the system to save power.

See [devices/sound-system/README.md](devices/sound-system/README.md) for detailed documentation.

## Getting Started

### Prerequisites
- Arduino IDE (for device controllers)
- Python 3.x (for web platform, when implemented)
- Node.js (for frontend, when implemented)

### Adding a New Device

1. Create a new directory under `devices/` with a descriptive name
2. Implement the Arduino controller following the structure of existing devices
3. Document the device in its own README.md
4. Update this README to include the new device

## Future Development

- [ ] Implement web platform backend (Django/FastAPI)
- [ ] Implement web platform frontend (Angular/Vue.js)
- [ ] Add device discovery and registration system
- [ ] Implement centralized device management dashboard
- [ ] Add authentication and security features
- [ ] Support for device scheduling and automation rules

## License

See [LICENSE](LICENSE) file for details.
