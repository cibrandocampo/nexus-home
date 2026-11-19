// Minimal non-blocking HTTP server: web UI on "/" and JSON API under /api/v1.
#pragma once
#include <Arduino.h>

namespace http {

void begin();  // (re)starts listening; call after every WiFi connection
void loop();

}  // namespace http
