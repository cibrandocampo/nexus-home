// WiFi: home network (normal mode) or the board's own open network (setup mode).
// Status is cached so the rest of the code never waits on the modem.
#pragma once
#include <Arduino.h>

namespace net {

enum class Mode : uint8_t {
  Unconfigured,  // no network stored: WiFi stays off, the door keeps working
  Station,       // joins the home network from the settings
  Setup,         // jumper on the setup pin at boot: own open network for the setup page
};

void begin(Mode mode);
void loop();

Mode        mode();
bool        connected();     // home network joined, or own network up in setup mode
int         rssi();
const char* ip();            // "0.0.0.0" when offline
const uint8_t* ipBytes();
const char* mac();           // "AA:BB:CC:DD:EE:FF"
const char* deviceId();      // "garage-ddeeff", also the hostname and the setup network name
uint32_t    connectCount();
const char* modemVersion();  // firmware of the WiFi module, "" if unknown

// Switches to another home network. If it has not connected within cfg::WIFI_TRIAL_S, the stored
// network is restored. On success the new network is saved through settings::save().
void        tryNetwork(const char* ssid, const char* password);
bool        trying();        // a network switch is in progress

}  // namespace net
