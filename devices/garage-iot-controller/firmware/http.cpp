#include "http.h"
#include "config.h"
#include "display.h"
#include "garage.h"
#include "fwupdate.h"
#include "json.h"
#include "net.h"
#include "settings.h"
#include "watchdog.h"
#include "web.h"
#include "web_setup.h"
#include <WiFiS3.h>

namespace http {
namespace {

constexpr uint32_t REQUEST_TIMEOUT_MS = 1500;
constexpr uint32_t ACCEPT_INTERVAL_MS = 5;
constexpr size_t   CHUNK = 1024;

WiFiServer server(80);
WiFiClient cli;
bool       active = false;
uint32_t   startedAt = 0, lastAccept = 0;
char       req[1024];
size_t     reqLen = 0;
char       body[7168];  // sized for the event log (64 entries of up to ~105 bytes)
char       tx[1280];
const char* headers = req;  // where the header search starts
// Actions that must wait until the answer has been sent.
bool       restartAfter = false;
bool       networkAfter = false;
bool       flashAfter = false;
char       nextSsid[sizeof settings::Data::ssid];
char       nextPass[sizeof settings::Data::password];

const char* reason(int code) {
  switch (code) {
    case 200: return "OK";
    case 400: return "Bad Request";
    case 401: return "Unauthorized";
    case 403: return "Forbidden";
    case 404: return "Not Found";
    case 405: return "Method Not Allowed";
    case 409: return "Conflict";
    case 413: return "Payload Too Large";
    case 500: return "Internal Server Error";
    case 502: return "Bad Gateway";
    default:  return "Error";
  }
}

void sendAll(const char* p, size_t n) {
  while (n) {
    const size_t c = n > CHUNK ? CHUNK : n;
    if (cli.write((const uint8_t*)p, c) != c) return;
    p += c;
    n -= c;
  }
}

void respond(int code, const char* type, const char* data, size_t len) {
  const int h = snprintf(tx, sizeof tx,
                         "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %u\r\n"
                         "Cache-Control: no-store\r\nConnection: close\r\n\r\n",
                         code, reason(code), type, (unsigned)len);
  if (h + len <= sizeof tx) {  // small answers go out in a single modem write
    memcpy(tx + h, data, len);
    sendAll(tx, h + len);
  } else {
    sendAll(tx, h);
    sendAll(data, len);
  }
}

void respondJson(int code, size_t len) { respond(code, "application/json", body, len); }

void respondError(int code, const char* errCode, const char* message) {
  respondJson(code, snprintf(body, sizeof body, "{\"error\":{\"code\":\"%s\",\"message\":\"%s\"}}", errCode, message));
}

const char* b(bool v) { return v ? "true" : "false"; }

// Writes s as JSON string content (without quotes) into out; returns the length.
size_t esc(char* out, size_t n, const char* s) {
  size_t k = 0;
  for (; *s && k + 7 < n; ++s) {
    const unsigned char c = (unsigned char)*s;
    if (c == '"' || c == '\\') { out[k++] = '\\'; out[k++] = (char)c; }
    else if (c < 0x20) k += snprintf(out + k, n - k, "\\u%04x", c);
    else out[k++] = (char)c;
  }
  out[k] = 0;
  return k;
}

size_t stateJson(char* out, size_t n) {
  const garage::State s = garage::state();
  const bool moving = s.door == garage::Door::Opening || s.door == garage::Door::Closing;
  return snprintf(out, n,
                  "{\"rev\":%lu,\"uptime_s\":%lu,"
                  "\"door\":{\"state\":\"%s\",\"moving\":%s,\"sensor_closed\":%s,\"close_failed\":%s,\"stopped\":\"%s\",\"since_s\":%lu,\"last_source\":\"%s\"},"
                  "\"light\":{\"state\":\"%s\",\"timed\":%s,\"remaining_s\":%lu},"
                  "\"night\":%s,\"light_level\":%u,\"button\":%s,\"display\":%s,"
                  "\"wifi\":{\"ip\":\"%s\",\"rssi\":%d}}",
                  (unsigned long)s.rev, (unsigned long)s.uptimeS, garage::name(s.door), b(moving), b(s.sensorClosed), b(s.closeFailed), garage::name(s.stopped),
                  (unsigned long)s.doorSinceS, garage::name(s.doorSource), s.light ? "on" : "off", b(s.lightTimed),
                  (unsigned long)s.lightRemainingS, b(s.night), (unsigned)s.lightLevel, b(s.button), b(display::enabled()), net::ip(), net::rssi());
}

void respondState() { respondJson(200, stateJson(body, sizeof body)); }

void respondResult(const char* result) {
  size_t n = snprintf(body, sizeof body, "{\"result\":\"%s\",\"state\":", result);
  n += stateJson(body + n, sizeof body - n);
  if (n < sizeof body - 1) body[n++] = '}';
  respondJson(200, n);
}

void respondLog() {
  static garage::LogEntry entries[cfg::LOG_SIZE];
  const size_t count = garage::recent(entries, cfg::LOG_SIZE);
  size_t n = snprintf(body, sizeof body, "{\"uptime_s\":%lu,\"events\":[", (unsigned long)garage::state().uptimeS);
  for (size_t i = 0; i < count && n + 128 < sizeof body; ++i) {
    const garage::LogEntry& e = entries[i];
    n += snprintf(body + n, sizeof body - n, "%s{\"t\":%lu,\"event\":\"%s\",\"source\":\"%s\",\"reason\":\"%s\",\"value\":%lu}",
                  i ? "," : "", (unsigned long)e.t, garage::name(e.event), garage::name(e.source), garage::name(e.reason),
                  (unsigned long)e.value);
  }
  n += snprintf(body + n, sizeof body - n, "]}");
  respondJson(200, n);
}

const char* modeName() {
  switch (net::mode()) {
    case net::Mode::Setup:   return "setup";
    case net::Mode::Station: return "normal";
    default:                 return "unconfigured";
  }
}

void respondInfo() {
  char name[2 * sizeof settings::Data::name];
  esc(name, sizeof name, settings::get().name);
  respondJson(200, snprintf(body, sizeof body,
                            "{\"id\":\"%s\",\"name\":\"%s\",\"mode\":\"%s\",\"manufacturer\":\"nexusHome\","
                            "\"model\":\"Garage IoT Controller (UNO R4 WiFi)\",\"sw_version\":\"%s\",\"modem_fw\":\"%s\",\"reset_reason\":\"%s\","
                            "\"api\":\"v1\",\"mac\":\"%s\",\"hostname\":\"%s\",\"auth\":%s,"
                            "\"entities\":["
                            "{\"id\":\"door\",\"type\":\"cover\",\"device_class\":\"garage\",\"state\":\"door.state\","
                            "\"commands\":[\"open\",\"close\",\"stop\",\"toggle\"]},"
                            "{\"id\":\"light\",\"type\":\"light\",\"state\":\"light.state\","
                            "\"commands\":[\"on\",\"off\",\"toggle\"]},"
                            "{\"id\":\"door_problem\",\"type\":\"binary_sensor\",\"device_class\":\"problem\","
                            "\"state\":\"door.close_failed\"},"
                            "{\"id\":\"night\",\"type\":\"binary_sensor\",\"state\":\"night\"},"
                            "{\"id\":\"light_level\",\"type\":\"sensor\",\"state\":\"light_level\"},"
                            "{\"id\":\"rssi\",\"type\":\"sensor\",\"device_class\":\"signal_strength\","
                            "\"unit\":\"dBm\",\"state\":\"wifi.rssi\"}]}",
                            net::deviceId(), name, modeName(), FW_VERSION, net::modemVersion(), watchdog::resetReason(), net::mac(),
                            net::deviceId(), b(settings::get().token[0] != 0)));
}

// Finds a header (case-insensitive) and returns its value; len receives the value length.
const char* header(const char* name, const char* headEnd, size_t& len) {
  const size_t n = strlen(name);
  const char* p = strstr(headers, "\r\n");
  while (p && p < headEnd) {
    p += 2;
    if (strncasecmp(p, name, n) == 0 && p[n] == ':') {
      p += n + 1;
      while (*p == ' ') ++p;
      const char* e = strstr(p, "\r\n");
      len = e ? (size_t)(e - p) : 0;
      return p;
    }
    p = strstr(p, "\r\n");
  }
  len = 0;
  return nullptr;
}

bool authorized(const char* headEnd) {
  const char* token = settings::get().token;
  const size_t tokenLen = strlen(token);
  if (tokenLen == 0) return true;
  size_t len;
  const char* v = header("Authorization", headEnd, len);
  return v && len == tokenLen + 7 && strncasecmp(v, "Bearer ", 7) == 0 && memcmp(v + 7, token, tokenLen) == 0;
}

// Browsers send Origin on cross-site POSTs: reject them so other web pages cannot open the door.
bool sameOrigin(const char* headEnd) {
  size_t ol, hl;
  const char* origin = header("Origin", headEnd, ol);
  if (!origin) return true;
  const char* host = header("Host", headEnd, hl);
  return host && ol == hl + 7 && strncmp(origin, "http://", 7) == 0 && memcmp(origin + 7, host, hl) == 0;
}

// Reads "duration" from the query string (?duration=30) or a JSON body ({"duration":30}).
bool findDuration(const char* query, const char* payload, uint32_t& out) {
  const char* p = query ? strstr(query, "duration=") : nullptr;
  if (p) {
    p += 9;
  } else if ((p = strstr(payload, "\"duration\"")) != nullptr) {
    p += 10;
    while (*p == ' ' || *p == ':') ++p;
  } else {
    return true;  // not given: keep the default
  }
  if (*p < '0' || *p > '9') return false;
  const unsigned long v = strtoul(p, nullptr, 10);
  if (v > cfg::LIGHT_MAX_S) return false;
  out = v;
  return true;
}

void respondCmd(garage::Cmd r) {
  if (r == garage::Cmd::Busy) respondError(409, "door_busy", "Door is moving or was just triggered, retry later");
  else respondResult(r == garage::Cmd::Ok ? "ok" : "noop");
}

void handleCommand(const char* path, const char* query, const char* payload) {
  if (!strcmp(path, "door/open")) return respondCmd(garage::doorOpen());
  if (!strcmp(path, "door/close")) return respondCmd(garage::doorClose());
  if (!strcmp(path, "door/stop")) return respondCmd(garage::doorStop());
  if (!strcmp(path, "door/toggle")) return respondCmd(garage::doorToggle());
  if (!strcmp(path, "light/on")) {
    uint32_t seconds = garage::lightDefaultS();
    if (!findDuration(query, payload, seconds)) return respondError(400, "invalid_duration", "duration must be 0..86400 seconds");
    return respondCmd(garage::lightOn(seconds));
  }
  if (!strcmp(path, "light/off")) return respondCmd(garage::lightOff());
  if (!strcmp(path, "light/toggle")) { garage::lightToggle(); return respondResult("ok"); }
  respondError(404, "not_found", "Unknown command");
}

// Settings as JSON. The WiFi password is never returned; the token only in setup mode
// (physical access to the board is required to be in that mode).
size_t settingsJson(char* out, size_t n) {
  const settings::Data& d = settings::get();
  char name[2 * sizeof d.name], ssid[2 * sizeof d.ssid], token[2 * sizeof d.token];
  esc(name, sizeof name, d.name);
  esc(ssid, sizeof ssid, d.ssid);
  esc(token, sizeof token, net::mode() == net::Mode::Setup ? d.token : "");
  return snprintf(out, n,
                  "{\"name\":\"%s\",\"wifi_ssid\":\"%s\",\"wifi_password_set\":%s,\"token_set\":%s,%s%s%s"
                  "\"open_s\":%u,\"close_s\":%u,\"light_s\":%u,\"night_level\":%u,\"display\":%s,\"stored\":%s,\"wifi_trying\":%s}",
                  name, ssid, b(d.password[0] != 0), b(d.token[0] != 0), token[0] ? "\"token\":\"" : "", token,
                  token[0] ? "\"," : "", d.openS, d.closeS, d.lightS, d.nightLevel, b(d.display), b(settings::stored()),
                  b(net::trying() || networkAfter));
}

void respondSettings(const char* result) {
  size_t n = 0;
  if (result) n = snprintf(body, sizeof body, "{\"result\":\"%s\",\"settings\":", result);
  n += settingsJson(body + n, sizeof body - n);
  if (result && n < sizeof body - 1) body[n++] = '}';
  respondJson(200, n);
}

const char* errorMessage(const char* code) {
  if (!strcmp(code, "too_long")) return "A text field is too long";
  if (!strcmp(code, "invalid_name")) return "Name must not be empty";
  if (!strcmp(code, "invalid_ssid")) return "WiFi network must not be empty";
  if (!strcmp(code, "invalid_password")) return "WiFi password must be empty or at least 8 characters";
  if (!strcmp(code, "invalid_token")) return "Token must be 8 to 64 characters, no spaces";
  if (!strcmp(code, "invalid_open_time")) return "Opening time must be 5 to 100 seconds";
  if (!strcmp(code, "invalid_close_time")) return "Close confirmation time must be 10 to 100 seconds";
  if (!strcmp(code, "invalid_light_time")) return "Light time must be 10 to 600 seconds";
  if (!strcmp(code, "invalid_night_level")) return "Night level must be 1 to 1023";
  if (!strcmp(code, "invalid_display")) return "display must be true or false";
  if (!strcmp(code, "invalid_json")) return "Malformed field in the request body";
  return "Invalid settings";
}

void respondInvalid(const char* code) { respondError(400, code, errorMessage(code)); }

// Applies the fields present in the body to d and checks the result. Returns an error code or nullptr.
// A network and a token are always required (the token cannot be removed from the web). wifiChanged is set when the network or its password is in the body and differs.
const char* applyFields(const char* payload, settings::Data& d, bool& wifiChanged) {
  wifiChanged = false;
  uint32_t v;
  json::Result r;
  if ((r = json::str(payload, "name", d.name, sizeof d.name)) == json::Invalid) return "invalid_name";
  if ((r = json::str(payload, "token", d.token, sizeof d.token)) == json::Invalid) return "invalid_token";
  if ((r = json::num(payload, "open_s", v)) == json::Invalid || (r == json::Ok && v > 0xFFFF)) return "invalid_open_time";
  if (r == json::Ok) d.openS = (uint16_t)v;
  if ((r = json::num(payload, "close_s", v)) == json::Invalid || (r == json::Ok && v > 0xFFFF)) return "invalid_close_time";
  if (r == json::Ok) d.closeS = (uint16_t)v;
  if ((r = json::num(payload, "light_s", v)) == json::Invalid || (r == json::Ok && v > 0xFFFF)) return "invalid_light_time";
  if (r == json::Ok) d.lightS = (uint16_t)v;
  if ((r = json::num(payload, "night_level", v)) == json::Invalid || (r == json::Ok && v > 0xFFFF)) return "invalid_night_level";
  if (r == json::Ok) d.nightLevel = (uint16_t)v;
  bool on;
  if ((r = json::flag(payload, "display", on)) == json::Invalid) return "invalid_display";
  if (r == json::Ok) d.display = on ? 1 : 0;
  char ssid[sizeof d.ssid], pass[sizeof d.password];
  const json::Result rs = json::str(payload, "wifi_ssid", ssid, sizeof ssid);
  const json::Result rp = json::str(payload, "wifi_password", pass, sizeof pass);
  if (rs == json::Invalid) return "invalid_ssid";
  if (rp == json::Invalid) return "invalid_password";
  if (rs == json::Ok && strcmp(ssid, d.ssid) != 0) { strcpy(d.ssid, ssid); wifiChanged = true; }
  if (rp == json::Ok) {  // an empty password keeps the current one, unless the network changed
    if (pass[0] || wifiChanged) {
      if (strcmp(pass, d.password) != 0) wifiChanged = true;
      strcpy(d.password, pass);
    }
  }
  if (!d.ssid[0]) return "invalid_ssid";
  if (!d.token[0]) return "invalid_token";
  return settings::validate(d);
}

// Settings that take effect at once, after a save.
void useSettings(const settings::Data& d) {
  garage::configure({d.openS, d.closeS, d.lightS, d.nightLevel});
  display::setEnabled(d.display);
}

// Restart and firmware update are refused while the door moves, so they never cut a movement.
bool doorBusy() {
  const garage::State st = garage::state();
  return st.door == garage::Door::Opening || st.door == garage::Door::Closing || st.relayPulse;
}

// POST /api/v1/settings (normal mode, token). Name, token and timings are saved at once;
// a new WiFi network is tried first and only saved once it connects (net::tryNetwork).
void handleSettings(const char* payload) {
  const settings::Data old = settings::get();
  settings::Data d = old;
  bool wifiChanged;
  if (const char* err = applyFields(payload, d, wifiChanged)) return respondInvalid(err);

  settings::Data keep = d;  // what is saved now: everything except a new network
  strcpy(keep.ssid, old.ssid);
  strcpy(keep.password, old.password);
  const bool changed = strcmp(keep.name, old.name) || strcmp(keep.token, old.token) || keep.openS != old.openS ||
                      keep.closeS != old.closeS || keep.lightS != old.lightS ||
                      keep.nightLevel != old.nightLevel || keep.display != old.display;  // field by field: bytes after a string's end may differ
  if (changed) {
    if (!settings::save(keep)) {
      garage::note(garage::Event::SettingsSaveFailed, garage::Source::Api);
      return respondError(500, "save_failed", "Could not write the settings to flash");
    }
    useSettings(keep);
    garage::note(garage::Event::SettingsChanged, garage::Source::Api);
  }
  if (wifiChanged) {
    strcpy(nextSsid, d.ssid);
    strcpy(nextPass, d.password);
    networkAfter = true;  // after the answer: the connection drops while switching
    return respondSettings("testing_wifi");
  }
  respondSettings("ok");
}

// POST /api/v1/setup (setup mode only, no token: the jumper on the setup pin is the protection).
void handleSetup(const char* payload) {
  settings::Data d = settings::get();
  bool wifiChanged;
  if (const char* err = applyFields(payload, d, wifiChanged)) return respondInvalid(err);
  if (!settings::save(d)) return respondError(500, "save_failed", "Could not write the settings to flash");
  useSettings(d);
  garage::note(garage::Event::SettingsChanged);
  respondSettings("ok");
}

// POST /api/v1/restart.
void handleRestart() {
  if (doorBusy()) return respondError(409, "door_busy", "Door is moving, restart refused");
  restartAfter = true;
  respondJson(200, snprintf(body, sizeof body, "{\"result\":\"restarting\"}"));
}

// POST /api/v1/firmware {"url": "http://host:port/garage-x.y.z.ota"} (token required).
// The WiFi module downloads and verifies the file while this request waits; the answer says whether it
// is good. Only then, after the answer has been sent, the module reflashes the board (finish()).
void handleFirmware(const char* payload) {
  char url[160];
  if (json::str(payload, "url", url, sizeof url) != json::Ok) return respondError(400, "invalid_url", "url required");
  // The URL goes into an AT command: only plain http:// and no separators of that command.
  if (strncmp(url, "http://", 7) != 0 || strpbrk(url, ",\" \r\n"))
    return respondError(400, "invalid_url", "url must be http:// without spaces, commas or quotes");
  if (doorBusy()) return respondError(409, "door_busy", "Door is moving, update refused");
  const char* err = fwupdate::fetch(url);
  if (err) {
    garage::note(garage::Event::FirmwareUpdateFailed, garage::Source::Api);
    return respondError(502, err, "The firmware could not be downloaded or did not pass the checks");
  }
  flashAfter = true;
  respondJson(200, snprintf(body, sizeof body, "{\"result\":\"flashing\",\"from\":\"%s\"}", FW_VERSION));
}

void handle(char* headEnd, const char* payload) {
  // Request line: METHOD SP target SP HTTP/x
  char* sp1 = strchr(req, ' ');
  char* sp2 = sp1 ? strchr(sp1 + 1, ' ') : nullptr;
  if (!sp2 || sp2 > headEnd) return respondError(400, "bad_request", "Malformed request");
  *sp1 = *sp2 = 0;
  headers = sp2 + 1;
  const char* method = req;
  char* path = sp1 + 1;
  char* query = strchr(path, '?');
  if (query) *query++ = 0;
  const bool get = !strcmp(method, "GET");
  const bool post = !strcmp(method, "POST");

  const bool setup = net::mode() == net::Mode::Setup;
  if (!strcmp(path, "/")) {
    if (!get) return respondError(405, "method_not_allowed", "Use GET");
    if (setup) return respond(200, "text/html; charset=utf-8", SETUP_PAGE, sizeof SETUP_PAGE - 1);
    return respond(200, "text/html; charset=utf-8", WEB_PAGE, sizeof WEB_PAGE - 1);
  }
  if (strncmp(path, "/api/v1/", 8) != 0) return respondError(404, "not_found", "Not found");
  path += 8;

  if (!strcmp(path, "info")) return get ? respondInfo() : respondError(405, "method_not_allowed", "Use GET");
  if (!strcmp(path, "settings") && get) {
    if (!setup && !authorized(headEnd)) return respondError(401, "unauthorized", "Missing or invalid bearer token");
    return respondSettings(nullptr);
  }
  if (setup) {  // only the setup page works in setup mode
    if (!post) return respondError(405, "method_not_allowed", "Use POST");
    if (!sameOrigin(headEnd)) return respondError(403, "forbidden", "Cross-origin request rejected");
    if (!strcmp(path, "setup")) return handleSetup(payload);
    if (!strcmp(path, "restart")) return handleRestart();
    return respondError(404, "setup_mode", "Setup mode: only the setup page is available");
  }
  if (!strcmp(path, "state") || !strcmp(path, "log")) {
    if (!get) return respondError(405, "method_not_allowed", "Use GET");
    return path[0] == 's' ? respondState() : respondLog();
  }
  if (!post) return respondError(405, "method_not_allowed", "Use POST");
  if (!sameOrigin(headEnd)) return respondError(403, "forbidden", "Cross-origin request rejected");
  if (!authorized(headEnd)) return respondError(401, "unauthorized", "Missing or invalid bearer token");
  if (!strcmp(path, "settings")) return handleSettings(payload);
  if (!strcmp(path, "restart")) return handleRestart();
  if (!strcmp(path, "firmware")) return handleFirmware(payload);
  handleCommand(path, query, payload);
}

void finish() {
  delay(1);
  cli.stop();
  active = false;
  if (restartAfter) {
    Serial.println("[http] restart requested");
    Serial.flush();
    delay(300);  // let the modem send the last bytes
    NVIC_SystemReset();
  }
  if (flashAfter) {
    flashAfter = false;
    delay(500);
    fwupdate::apply();  // does not return when the module starts the reflash
    garage::note(garage::Event::FirmwareUpdateFailed);
  }
  if (networkAfter) {
    networkAfter = false;
    delay(300);
    net::tryNetwork(nextSsid, nextPass);
  }
}

}  // namespace

void begin() { server.begin(); }

void loop() {
  if (!net::connected()) {
    if (active) finish();
    return;
  }
  if (!active) {
    if (millis() - lastAccept < ACCEPT_INTERVAL_MS) return;
    lastAccept = millis();
    cli = server.available();
    if (!cli) return;
    active = true;
    headers = req;
    reqLen = 0;
    startedAt = millis();
  }

  while (reqLen < sizeof req - 1 && cli.available() > 0) req[reqLen++] = (char)cli.read();
  req[reqLen] = 0;

  char* headEnd = strstr(req, "\r\n\r\n");
  if (headEnd) {
    size_t len;
    const char* cl = header("Content-Length", headEnd, len);
    const size_t want = cl ? strtoul(cl, nullptr, 10) : 0;
    const char* payload = headEnd + 4;
    if (want > sizeof req - 1 - (payload - req)) {
      respondError(413, "too_large", "Request too large");
      return finish();
    }
    if (reqLen - (payload - req) >= want) {
      handle(headEnd, payload);
      return finish();
    }
  } else if (reqLen >= sizeof req - 1) {
    respondError(413, "too_large", "Request too large");
    return finish();
  }
  if (millis() - startedAt > REQUEST_TIMEOUT_MS) finish();
}

}  // namespace http
