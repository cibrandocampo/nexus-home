#include "fwupdate.h"
#include "watchdog.h"
#include <OTAUpdate.h>
#include <WiFiS3.h>

namespace fwupdate {
namespace {

constexpr const char* PATH = "/update.bin";
constexpr uint32_t DOWNLOAD_MAX_MS = 120000;

OTAUpdate ota;

// The module's own download hangs the module (network, web and USB serial) when the server does not
// answer: seen on the bench with module firmware 0.6.0. So the URL is tried first with a plain
// connection and a HEAD request; the module download is only started when that answers 200.
const char* probe(const char* url) {
  // url is "http://host[:port]/path" (checked by the caller).
  const char* h = url + 7;
  const char* slash = strchr(h, '/');
  if (!slash) return "invalid_url";
  char host[64];
  const char* colon = (const char*)memchr(h, ':', slash - h);
  const size_t hostLen = (colon ? colon : slash) - h;
  if (hostLen == 0 || hostLen >= sizeof host) return "invalid_url";
  memcpy(host, h, hostLen);
  host[hostLen] = 0;
  const uint16_t port = colon ? (uint16_t)atoi(colon + 1) : 80;
  if (!port) return "invalid_url";

  WiFiClient c;
  if (!c.connect(host, port)) {
    Serial.println("[fw] server not reachable");
    return "server_unreachable";
  }
  c.print("HEAD ");
  c.print(slash);
  c.print(" HTTP/1.0\r\nHost: ");
  c.print(host);
  c.print("\r\nConnection: close\r\n\r\n");
  char line[40];
  size_t n = 0;
  const uint32_t t0 = millis();
  while (millis() - t0 < 5000 && n < sizeof line - 1) {
    watchdog::heartbeat();
    if (c.available() <= 0) {
      if (!c.connected()) break;
      delay(10);
      continue;
    }
    const int ch = c.read();
    if (ch < 0 || ch == '\n') break;
    line[n++] = (char)ch;
  }
  line[n] = 0;
  c.stop();
  Serial.print("[fw] server answered: ");
  Serial.println(line);
  // "HTTP/1.x 200 ..."
  const char* sp = strchr(line, ' ');
  if (strncmp(line, "HTTP/", 5) != 0 || !sp) return "server_unreachable";
  if (strncmp(sp + 1, "200", 3) != 0) return "file_not_found";
  return nullptr;
}

}  // namespace

const char* fetch(const char* url) {
  // begin(path) mounts the module's file system and deletes an old image at that path.
  Serial.print("[fw] fetch ");
  Serial.println(url);
  if (const char* err = probe(url)) return err;
  watchdog::heartbeat();
  const int b = ota.begin(PATH);
  if (b != OTAUpdate::OTA_ERROR_NONE) {
    Serial.print("[fw] begin failed: ");
    Serial.println(b);
    return "storage_error";
  }
  watchdog::heartbeat();
  const int total = ota.startDownload(url, PATH);  // expected size, or a negative error
  Serial.print("[fw] expected size: ");
  Serial.println(total);
  if (total <= 0) return "download_failed";
  const uint32_t started = millis();
  int done = 0;
  while (done < total) {
    watchdog::heartbeat();  // the door logic keeps running in its interrupt
    if (millis() - started > DOWNLOAD_MAX_MS) return "download_timeout";
    delay(100);
    done = ota.downloadProgress();
    if (done < 0) {
      Serial.print("[fw] download failed: ");
      Serial.println(done);
      return "download_failed";
    }
  }
  Serial.print("[fw] downloaded in ");
  Serial.print(millis() - started);
  Serial.println(" ms");
  const int v = ota.verify();  // magic number for this board and CRC of the .ota file
  if (v != OTAUpdate::OTA_ERROR_NONE) {
    Serial.print("[fw] verify failed: ");
    Serial.println(v);
    return "verify_failed";
  }
  return nullptr;
}

void apply() {
  Serial.println("[fw] starting the reflash");
  Serial.flush();
  const int r = ota.update(PATH);  // the module resets this board into its bootloader and flashes it
  Serial.print("[fw] update returned ");  // only reached if the module could not start
  Serial.println(r);
}

}  // namespace fwupdate
