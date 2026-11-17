#include "settings.h"
#include "config.h"

#ifndef HOST_TEST
#include <DataFlashBlockDevice.h>
#endif

namespace settings {
namespace {

// Two 1 KB data flash blocks used in turn: a save writes the block not holding the current copy,
// so a power cut during a save leaves the previous settings intact.
constexpr uint32_t MAGIC = 0x47415231;  // "GAR1"
constexpr uint32_t BLOCK = 1024;
constexpr uint32_t SLOTS = 2;

struct Record {
  uint32_t magic;
  uint32_t seq;   // higher = newer
  Data     data;
  uint32_t crc;   // over everything before it
};
static_assert(sizeof(Record) <= BLOCK, "settings record must fit in one flash block");

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

bool terminated(const char* s, size_t n) { return memchr(s, 0, n) != nullptr; }

#ifdef HOST_TEST
uint8_t flash[SLOTS * BLOCK];
bool readSlot(int slot, Record& r) { memcpy(&r, flash + slot * BLOCK, sizeof r); return true; }
bool writeSlot(int slot, const Record& r) {
  memset(flash + slot * BLOCK, 0xFF, BLOCK);
  memcpy(flash + slot * BLOCK, &r, sizeof r);
  return true;
}
#else
DataFlashBlockDevice& df() { return DataFlashBlockDevice::getInstance(); }
bool readSlot(int slot, Record& r) { return df().read(&r, slot * BLOCK, sizeof r) == 0; }
bool writeSlot(int slot, const Record& r) {
  return df().erase(slot * BLOCK, BLOCK) == 0 && df().program(&r, slot * BLOCK, sizeof r) == 0;
}
#endif

}  // namespace

Data defaults() {
  Data d;
  memset(&d, 0, sizeof d);
  strcpy(d.name, "Garage");
  d.openS = cfg::DOOR_TRAVEL_MS / 1000;
  d.closeS = cfg::DOOR_CLOSE_TIMEOUT_MS / 1000;
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
  return nullptr;
}

void begin() {
  cur = defaults();
  haveStored = false;
  curSlot = -1;
  curSeq = 0;
  for (int slot = 0; slot < (int)SLOTS; ++slot) {
    Record r;
    if (!readSlot(slot, r) || r.magic != MAGIC || r.crc != crcOf(r) || validate(r.data)) continue;
    if (curSlot < 0 || r.seq > curSeq) {
      cur = r.data;
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
  if (!writeSlot(slot, r)) return false;
  Record check;
  if (!readSlot(slot, check) || memcmp(&check, &r, sizeof r) != 0) return false;
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
#endif

}  // namespace settings
