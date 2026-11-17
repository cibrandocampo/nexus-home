#include "net.h"
#include "config.h"
#include "garage.h"
#include "http.h"
#include "settings.h"
#include <WiFiS3.h>

namespace net {
namespace {

constexpr uint32_t CHECK_MS = 2000;
constexpr uint32_t RSSI_MS = 15000;
constexpr uint32_t RETRY_MIN_MS = 5000;
constexpr uint32_t RETRY_MAX_MS = 60000;

Mode     curMode = Mode::Unconfigured;
bool     up = false;
bool     hasModule = true;
int      lastRssi = 0;
uint32_t connects = 0;
uint32_t lastCheck = 0, lastRssiAt = 0, nextTry = 0, retryMs = RETRY_MIN_MS;
char     ipStr[16] = "0.0.0.0";
uint8_t  ipRaw[4] = {0, 0, 0, 0};
char     macStr[18] = "";
char     idStr[16] = "garage";
char     modemStr[12] = "";

// Network switch requested from the settings page.
bool     trial = false;
uint32_t trialStart = 0;
char     trialSsid[sizeof settings::Data::ssid];
char     trialPass[sizeof settings::Data::password];

const char* targetSsid() { return trial ? trialSsid : settings::get().ssid; }
const char* targetPass() { return trial ? trialPass : settings::get().password; }

void readMac() {
  uint8_t m[6] = {0};
  WiFi.macAddress(m);
  snprintf(macStr, sizeof macStr, "%02X:%02X:%02X:%02X:%02X:%02X", m[0], m[1], m[2], m[3], m[4], m[5]);
  snprintf(idStr, sizeof idStr, "garage-%02x%02x%02x", m[3], m[4], m[5]);
}

void setIp(IPAddress a) {
  for (int i = 0; i < 4; ++i) ipRaw[i] = a[i];
  snprintf(ipStr, sizeof ipStr, "%u.%u.%u.%u", a[0], a[1], a[2], a[3]);
}

void onConnected() {
  setIp(WiFi.localIP());
  lastRssi = WiFi.RSSI();
  lastRssiAt = millis();
  retryMs = RETRY_MIN_MS;
  ++connects;
  http::begin();
  garage::note(garage::Event::WifiUp);
  if (trial) {  // the new network works: keep it
    trial = false;
    settings::Data d = settings::get();
    strcpy(d.ssid, trialSsid);
    strcpy(d.password, trialPass);
    const bool ok = settings::save(d);
    garage::note(ok ? garage::Event::WifiChanged : garage::Event::SettingsSaveFailed);
    Serial.println(ok ? "[net] new network saved" : "[net] new network works but could not be saved");
  }
  Serial.print("[net] connected, ip=");
  Serial.print(ipStr);
  Serial.print(" rssi=");
  Serial.println(lastRssi);
}

void startSetupNetwork() {
  Serial.print("[net] setup mode: open network ");
  Serial.println(idStr);
  if (WiFi.beginAP(idStr) != WL_AP_LISTENING) {
    Serial.println("[net] could not start the setup network");
    return;
  }
  delay(500);  // the modem needs a moment before it reports the address
  setIp(WiFi.localIP());
  up = true;
  ++connects;
  http::begin();
  Serial.print("[net] setup page at http://");
  Serial.println(ipStr);
}

void stationLoop(uint32_t now) {
  const bool ok = WiFi.status() == WL_CONNECTED && WiFi.localIP() != IPAddress(0, 0, 0, 0);
  if (ok) {
    if (!up) {
      up = true;
      onConnected();
    } else if (now - lastRssiAt >= RSSI_MS) {
      lastRssi = WiFi.RSSI();
      lastRssiAt = now;
    }
    return;
  }

  if (up) {
    up = false;
    strcpy(ipStr, "0.0.0.0");
    garage::note(garage::Event::WifiDown);
    Serial.println("[net] connection lost");
  }
  if (trial && now - trialStart >= cfg::WIFI_TRIAL_S * 1000UL) {  // new network failed: go back
    trial = false;
    retryMs = RETRY_MIN_MS;
    nextTry = now;
    garage::note(garage::Event::WifiChangeFailed);
    Serial.println("[net] new network did not connect, back to the stored one");
  }
  if ((int32_t)(now - nextTry) < 0) return;

  // WiFi.begin() blocks for up to ~10 s; the garage logic keeps running from its timer.
  Serial.print("[net] connecting to ");
  Serial.println(targetSsid());
  WiFi.disconnect();
  WiFi.begin(targetSsid(), targetPass());
  nextTry = millis() + retryMs;
  retryMs = retryMs * 2 > RETRY_MAX_MS ? RETRY_MAX_MS : retryMs * 2;
  lastCheck = millis() - CHECK_MS + 250;  // re-check shortly: DHCP may need a moment
}

}  // namespace

void begin(Mode m) {
  curMode = m;
  if (WiFi.status() == WL_NO_MODULE) {
    hasModule = false;
    Serial.println("[net] WiFi module not found");
    return;
  }
  strncpy(modemStr, WiFi.firmwareVersion(), sizeof modemStr - 1);
  readMac();
  Serial.print("[net] modem firmware ");
  Serial.println(modemStr);
  if (m == Mode::Setup) {
    startSetupNetwork();
  } else if (m == Mode::Station) {
    WiFi.setHostname(idStr);
  } else {
    Serial.println("[net] no network configured: WiFi off (setup: jumper pin 7 to GND and reset)");
  }
}

void loop() {
  if (!hasModule || curMode != Mode::Station) return;
  const uint32_t now = millis();
  if (now - lastCheck < CHECK_MS && lastCheck != 0) return;
  lastCheck = now ? now : 1;
  stationLoop(now);
}

void tryNetwork(const char* ssid, const char* password) {
  strncpy(trialSsid, ssid, sizeof trialSsid - 1);
  trialSsid[sizeof trialSsid - 1] = 0;
  strncpy(trialPass, password, sizeof trialPass - 1);
  trialPass[sizeof trialPass - 1] = 0;
  trial = true;
  trialStart = millis();
  curMode = Mode::Station;
  WiFi.setHostname(idStr);
  WiFi.disconnect();
  up = false;
  strcpy(ipStr, "0.0.0.0");
  retryMs = RETRY_MIN_MS;
  nextTry = millis();
  lastCheck = 0;
}

Mode        mode() { return curMode; }
bool        trying() { return trial; }
bool        connected() { return up; }
int         rssi() { return up && curMode == Mode::Station ? lastRssi : 0; }
const char* ip() { return ipStr; }
const uint8_t* ipBytes() { return ipRaw; }
const char* mac() { return macStr; }
const char* deviceId() { return idStr; }
uint32_t    connectCount() { return connects; }
const char* modemVersion() { return modemStr; }

}  // namespace net
