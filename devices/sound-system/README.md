# Smart Arduino Sound System Controller

Automation system for legacy sound equipment using Arduino UNO.

## Description

This project allows you to modernize legacy sound equipment (compatible with Sony HCD-H150/H500) by adding automatic audio signal detection and intelligent system control. The Arduino automatically detects when there is an audio signal on any of the inputs (TV or Chromecast), turns on the equipment and switches to the corresponding input. When no signal is detected for a period of time, it automatically turns off the system.

## Features

- **Automatic signal detection**: Detects audio signals from two independent inputs
- **Input priority**: TV input has priority over Chromecast
- **Signal confirmation**: Confirmation system to prevent false positives
- **Automatic shutdown**: Automatically turns off when there is no signal for a configured period
- **Continuous monitoring**: Monitors the active signal and responds to changes in real time
- **Visual feedback**: LED status indicator
- **Serial logging**: Information output via serial port for debugging

## Required Hardware

### Components
- Arduino UNO (or compatible)
- 3 Relay modules (for power control and input switching)
- 2 Voltage dividers or audio signal detection circuits
- Status LED (optional, Arduino UNO has one integrated on pin 13)
- Appropriate power supply for Arduino and relays

### Connections

#### Analog Pins (Signal Inputs)
- **A4**: Chromecast audio signal (connected to Phono input of the equipment)
- **A5**: TV audio signal (connected to CD input of the equipment)

#### Digital Pins (Control Outputs)
- **Pin 8**: System power on/off relay
- **Pin 9**: Relay to switch to TV input (CD)
- **Pin 10**: Relay to switch to Chromecast input (Phono)
- **Pin 13**: Status LED (integrated in Arduino UNO)

### Compatible Equipment
- Sony HCD-H150
- Sony HCD-H500
- Other equipment with audio inputs and control buttons accessible via relays

## Operation

### Operation Flow

1. **Initialization**: On power-up, the Arduino blinks the LED twice and enters standby mode.

2. **Signal Detection**:
   - The system continuously scans the two audio inputs
   - If it detects a signal on the TV input, it has priority
   - If there is no TV signal but there is a Chromecast signal, it activates Chromecast

3. **System Activation**:
   - When a signal is detected, it pulses the power relay
   - Switches to the corresponding input (TV or Chromecast)
   - Enters active monitoring mode

4. **Continuous Monitoring**:
   - While there is a signal, the system remains active
   - If the signal is lost for more than 1 second, it turns off the system
   - If the signal returns before the time limit, the system continues active

5. **Automatic Shutdown**:
   - When no signal is detected for the configured time, it pulses the power-off relay
   - The system returns to standby mode

### Confirmation System

To prevent false positives and accidental activations, the system implements a confirmation mechanism:

- **Chromecast**: Requires 30 consecutive samples (300ms) with signal to activate
- **TV**: Requires 20 consecutive samples (200ms) with signal to activate
- **Shutdown**: Requires 100 consecutive samples (1 second) without signal to turn off

## Configuration

### Detection Thresholds

Detection thresholds can be adjusted in the code according to your audio signal characteristics:

```cpp
const int CC_THRESHOLD = 2;   // Threshold for Chromecast (0-1023)
const int TV_THRESHOLD = 4;   // Threshold for TV (0-1023)
```

**Note**: Low values (2-4) are typical for line-level audio signals. Adjust these values according to your needs:
- Lower values = more sensitive (may activate with noise)
- Higher values = less sensitive (requires stronger signal)

### Confirmation Times

You can adjust confirmation times by modifying these constants:

```cpp
const int CC_CONFIRM_SAMPLES = 30;      // Samples to confirm CC (30 * 10ms = 300ms)
const int TV_CONFIRM_SAMPLES = 20;      // Samples to confirm TV (20 * 10ms = 200ms)
const int SIGNAL_LOSS_SAMPLES = 100;    // Samples before turning off (100 * 10ms = 1 second)
const int SIGNAL_CONFIRM_DELAY = 10;    // Delay between samples (ms)
```

### Relay Pulse Duration

The pulse duration to activate the relays can be adjusted:

```cpp
const int RELAY_PULSE_DURATION = 500;   // Pulse duration in milliseconds
```

**Note**: 500ms is typical for most equipment. Some equipment may require longer or shorter pulses.

## Installation

1. **Prepare the Hardware**:
   - Connect the relay modules according to the connection diagram
   - Connect the audio signal detection circuits to the analog pins
   - Verify that all connections are correct

2. **Load the Code**:
   - Open `audio.ino` in Arduino IDE
   - Select your Arduino board (Arduino UNO)
   - Select the correct serial port
   - Upload the code to the Arduino

3. **Verify Operation**:
   - Open Serial Monitor (9600 baud)
   - You should see startup messages
   - Test by sending audio signal to each input

## Usage

### Normal Operation

The system works completely automatically:

1. Connect the audio sources (TV and Chromecast) to the corresponding inputs of the equipment
2. The Arduino will automatically detect when there is a signal
3. The system will turn on and switch to the active input
4. When there is no signal, the system will automatically turn off

### Serial Monitor

The system provides detailed information through the serial port (9600 baud):

- Startup and configuration messages
- Signal detection
- State changes
- Debugging information

### Status LED

The LED on pin 13 (integrated in Arduino UNO) blinks twice on startup to indicate that the system is running.

## Troubleshooting

### System does not activate

- Verify that audio signals are connected correctly
- Check detection thresholds (they may be too high)
- Review analog pin connections
- Use Serial Monitor to see analog reading values

### System activates with noise

- Increase detection thresholds (`CC_THRESHOLD` and `TV_THRESHOLD`)
- Increase the number of confirmation samples
- Verify that signal detection circuits are well isolated

### System does not turn off

- Verify that the audio signal is actually being cut
- Review the value of `SIGNAL_LOSS_SAMPLES` (may be too high)
- Check that relays are working correctly

### System constantly switches inputs

- Increase confirmation times
- Verify that there are no interferences in the signals
- Make sure only one source is active at a time

## Code Structure

The code is organized in the following sections:

- **Pin Configuration**: Definition of all pins used
- **Configuration Constants**: Adjustable system values
- **State Management**: State system to track current mode
- **Detection Functions**: Logic to detect and confirm signals
- **Control Functions**: Relay and system control
- **Utility Functions**: Helper functions

## Implemented Improvements

- ✅ Structured and well-commented code
- ✅ Use of constants instead of magic numbers
- ✅ State management system
- ✅ Improved confirmation logic
- ✅ Non-blocking monitoring
- ✅ Better error handling and logging
- ✅ Time and delay optimization
- ✅ Complete code documentation

## Limitations

- Requires external circuits to detect audio signals (voltage dividers)
- Relays must be compatible with Arduino logic (5V)
- System is designed for two specific inputs (TV and Chromecast)
- Does not include WiFi communication (unlike garage-iot-controller)

## Future Improvements

Possible improvements for future versions:

- [ ] Add WiFi communication for integration with web platform
- [ ] Implement REST API for remote control
- [ ] Add more audio inputs
- [ ] Time scheduling system
- [ ] Volume control via PWM
- [ ] More sophisticated signal level detection (RMS)
- [ ] Manual control mode
- [ ] Web-based configuration interface

## Author

Cibran Docampo

## License

See [LICENSE](../../LICENSE) for details.
