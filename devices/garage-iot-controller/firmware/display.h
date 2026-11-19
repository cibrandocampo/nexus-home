// 12x8 LED matrix used as a debug panel: raw inputs, outputs, WiFi and IP address.
#pragma once
#include <Arduino.h>

namespace display {

void begin();
void loop();
void setEnabled(bool on);  // LED matrix on or off (setting, from the web page)
bool enabled();

}  // namespace display
