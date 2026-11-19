#include "settings.h"
#include "config.h"

#ifndef HOST_TEST
#include <DataFlashBlockDevice.h>
#endif

namespace settings {
namespace {

// Two 1 KB data flash blocks used in turn: a save writes the block not holding the current copy,
// so a power cut during a save leaves the previous settings intact.
constexpr uint32_t MAGIC = 0x47415232;  // "GAR2": since 2.0.3 (light timer and night level)
constexpr uint32_t BLOCK = 1024;
constexpr uint32_t SLOTS = 2;

struct Record {
  uint32_t magic;
  uint32_t seq;   // higher = newer
  Data     data;
  uint32_t crc;   // over everything before it
};
static_assert(sizeof(Record) <= BLOCK, "settings record must fit in one flash block");

// Format written by 2.0.0-2.0.2. Read once after the update; the next save writes the new format to
// the other block, so the old copy stays as a fallback until then.
constexpr uint32_t MAGIC_V1 = 0x47415231;  // "GAR1"
struct DataV1 {
  char     ssid[33];
  char     password[64];
  char     token[65];
  char     name[33];
  uint16_t openS;
  uint16_t closeS;
};
struct RecordV1 {
  uint32_t magic;
  uint32_t seq;
  DataV1   data;
  uint32_t crc;
};

Data     cur;
bool     haveStored = false;
uint32_t curSeq = 0;
int      curSlot = -1;

uint32_t crc32(const uint8_t* p, size_t n) {
  uint32_t c = 0xFFFFFFFF;
  while (n--) {
    c ^= *p++;
    for (int k = 0; k < 8; ++k) c = (c >> 1) ^ (0xEDB88320 & (0u - (c & 1)));
  }
  return ~c;
}

uint32_t crcOf(const Record& r) { return crc32((const uint8_t*)&r, offsetof(Record, crc)); }
uint32_t crcOf(const RecordV1& r) { return crc32((const uint8_t*)&r, offsetof(RecordV1, crc)); }

bool terminated(const char* s, size_t n) { return memchr(s, 0, n) != nullptr; }

uint16_t clampTo(uint16_t v, uint16_t lo, uint16_t hi) { return v < lo ? lo : v > hi ? hi : v; }

// Ranges have narrowed over time: a stored value outside the current one must not lose the WiFi settings.
void clampRanges(Data& d) {
  d.openS = clampTo(d.openS, OPEN_MIN_S, OPEN_MAX_S);
  d.closeS = clampTo(d.closeS, CLOSE_MIN_S, CLOSE_MAX_S);
  d.lightS = clampTo(d.lightS, LIGHT_MIN_S, LIGHT_MAX_S);
  d.nightLevel = clampTo(d.nightLevel, NIGHT_MIN, NIGHT_MAX);
  d.display = d.display ? 1 : 0;
}

#ifdef HOST_TEST
uint8_t flash[SLOTS * BLOCK];
bool readSlot(int slot, void* r, size_t n) { memcpy(r, flash + slot * BLOCK, n); return true; }
bool writeSlot(int slot, const void* r, size_t n) {
  memset(flash + slot * BLOCK, 0xFF, BLOCK);
  memcpy(flash + slot * BLOCK, r, n);
  return true;
}
#else
DataFlashBlockDevice& df() { return DataFlashBlockDevice::getInstance(); }
bool readSlot(int slot, void* r, size_t n) { return df().read(r, slot * BLOCK, n) == 0; }
bool writeSlot(int slot, const void* r, size_t n) {
  return df().erase(slot * BLOCK, BLOCK) == 0 && df().program(r, slot * BLOCK, n) == 0;
}
#endif

}  // namespace

Data defaults() {
  Data d;
  memset(&d, 0, sizeof d);
  strcpy(d.name, "Garage");
  d.openS = cfg::DOOR_TRAVEL_MS / 1000;
  d.closeS = cfg::DOOR_CLOSE_TIMEOUT_MS / 1000;
  d.lightS = cfg::LIGHT_DEFAULT_S;
  d.nightLevel = cfg::NIGHT_LEVEL_DEFAULT;
  d.display = 1;
  return d;
}

const char* validate(const Data& d) {
  if (!terminated(d.ssid, sizeof d.ssid) || !terminated(d.password, sizeof d.password) ||
      !terminated(d.token, sizeof d.token) || !terminated(d.name, sizeof d.name))
    return "too_long";
  if (!d.name[0]) return "invalid_name";
  if (d.ssid[0] && strlen(d.password) > 0 && strlen(d.password) < 8) return "invalid_password";  // WPA2 minimum
  const size_t t = strlen(d.token);
  if (t && t < TOKEN_MIN) return "invalid_token";
  for (const char* p = d.token; *p; ++p)
    if (*p <= ' ' || *p > '~') return "invalid_token";  // sent in an HTTP header
  if (d.openS < OPEN_MIN_S || d.openS > OPEN_MAX_S) return "invalid_open_time";
  if (d.closeS < CLOSE_MIN_S || d.closeS > CLOSE_MAX_S) return "invalid_close_time";
  if (d.lightS < LIGHT_MIN_S || d.lightS > LIGHT_MAX_S) return "invalid_light_time";
  if (d.nightLevel < NIGHT_MIN || d.nightLevel > NIGHT_MAX) return "invalid_night_level";
  if (d.display > 1) return "invalid_display";
  return nullptr;
}

void begin() {
  cur = defaults();
  haveStored = false;
  curSlot = -1;
  curSeq = 0;
  for (int slot = 0; slot < (int)SLOTS; ++slot) {
    Record r;
    if (!readSlot(slot, &r, sizeof r) || r.magic != MAGIC || r.crc != crcOf(r)) continue;
    clampRanges(r.data);
    if (validate(r.data)) continue;
    if (curSlot < 0 || r.seq > curSeq) {
      cur = r.data;
      curSeq = r.seq;
      curSlot = slot;
      haveStored = true;
    }
  }
  if (haveStored) return;
  // No copy in the current format: take the newest one in the old format, new fields at their defaults.
  for (int slot = 0; slot < (int)SLOTS; ++slot) {
    RecordV1 r;
    if (!readSlot(slot, &r, sizeof r) || r.magic != MAGIC_V1 || r.crc != crcOf(r)) continue;
    Data d = defaults();
    memcpy(d.ssid, r.data.ssid, sizeof d.ssid);
    memcpy(d.password, r.data.password, sizeof d.password);
    memcpy(d.token, r.data.token, sizeof d.token);
    memcpy(d.name, r.data.name, sizeof d.name);
    d.openS = r.data.openS;
    d.closeS = r.data.closeS;
    clampRanges(d);
    if (validate(d)) continue;
    if (curSlot < 0 || r.seq > curSeq) {
      cur = d;
      curSeq = r.seq;
      curSlot = slot;
      haveStored = true;
    }
  }
}

bool save(const Data& d) {
  if (validate(d)) return false;
  Record r;
  memset(&r, 0, sizeof r);  // padding included in the CRC: keep it deterministic
  r.magic = MAGIC;
  r.seq = curSeq + 1;
  r.data = d;
  r.crc = crcOf(r);
  const int slot = curSlot < 0 ? 0 : (curSlot + 1) % SLOTS;
  if (!writeSlot(slot, &r, sizeof r)) return false;
  Record check;
  if (!readSlot(slot, &check, sizeof check) || memcmp(&check, &r, sizeof r) != 0) return false;
  cur = d;
  curSeq = r.seq;
  curSlot = slot;
  haveStored = true;
  return true;
}

const Data& get() { return cur; }
bool        configured() { return cur.ssid[0] != 0; }
bool        stored() { return haveStored; }

#ifdef HOST_TEST
// Test hook: lets the host test corrupt or wipe the simulated flash.
uint8_t* testFlash() { return flash; }

bool testSaveV1(const Data& d) {
  RecordV1 r;
  memset(&r, 0, sizeof r);
  r.magic = MAGIC_V1;
  r.seq = curSeq + 1;
  memcpy(r.data.ssid, d.ssid, sizeof r.data.ssid);
  memcpy(r.data.password, d.password, sizeof r.data.password);
  memcpy(r.data.token, d.token, sizeof r.data.token);
  memcpy(r.data.name, d.name, sizeof r.data.name);
  r.data.openS = d.openS;
  r.data.closeS = d.closeS;
  r.crc = crcOf(r);
  const int slot = curSlot < 0 ? 0 : (curSlot + 1) % SLOTS;
  if (!writeSlot(slot, &r, sizeof r)) return false;
  curSeq = r.seq;
  curSlot = slot;
  return true;
}
#endif

}  // namespace settings
