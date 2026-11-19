// Minimal JSON field readers for small, flat request bodies ({"key": "value", "n": 30}).
// Not a full parser: enough for the settings and command bodies this device accepts.
#pragma once
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

namespace json {

// Finds "key": and returns a pointer to its value, or nullptr.
inline const char* find(const char* body, const char* key) {
  const size_t n = strlen(key);
  for (const char* p = body; (p = strchr(p, '"')) != nullptr; ++p) {
    if (strncmp(p + 1, key, n) == 0 && p[n + 1] == '"') {
      const char* v = p + n + 2;
      while (*v == ' ' || *v == '\t' || *v == '\r' || *v == '\n') ++v;
      if (*v != ':') continue;
      ++v;
      while (*v == ' ' || *v == '\t' || *v == '\r' || *v == '\n') ++v;
      return v;
    }
  }
  return nullptr;
}

enum Result { Missing, Ok, Invalid };

// Reads a string value into out (size n, always terminated). Handles the usual escapes and \u00XX;
// other \u escapes (non-ASCII written as escapes) are rejected. Raw UTF-8 passes through unchanged.
inline Result str(const char* body, const char* key, char* out, size_t n) {
  const char* p = find(body, key);
  if (!p) return Missing;
  if (*p != '"') return Invalid;
  ++p;
  size_t len = 0;
  while (*p && *p != '"') {
    char c = *p++;
    if (c == '\\') {
      const char e = *p++;
      switch (e) {
        case '"': case '\\': case '/': c = e; break;
        case 'n': c = '\n'; break;
        case 't': c = '\t'; break;
        case 'r': c = '\r'; break;
        case 'b': c = '\b'; break;
        case 'f': c = '\f'; break;
        case 'u': {
          char hex[5] = {0};
          for (int i = 0; i < 4; ++i) {
            if (!*p) return Invalid;
            hex[i] = *p++;
          }
          char* end;
          const unsigned long v = strtoul(hex, &end, 16);
          if (*end || v == 0 || v > 0x7F) return Invalid;
          c = (char)v;
          break;
        }
        default: return Invalid;
      }
    } else if ((unsigned char)c < 0x20) {
      return Invalid;
    }
    if (len + 1 >= n) return Invalid;  // too long
    out[len++] = c;
  }
  if (*p != '"') return Invalid;
  out[len] = 0;
  return Ok;
}

// Reads a true/false value.
inline Result flag(const char* body, const char* key, bool& out) {
  const char* p = find(body, key);
  if (!p) return Missing;
  if (!strncmp(p, "true", 4)) { out = true; return Ok; }
  if (!strncmp(p, "false", 5)) { out = false; return Ok; }
  return Invalid;
}

// Reads a non-negative integer value.
inline Result num(const char* body, const char* key, uint32_t& out) {
  const char* p = find(body, key);
  if (!p) return Missing;
  if (*p < '0' || *p > '9') return Invalid;
  char* end;
  const unsigned long v = strtoul(p, &end, 10);
  if (*end == '.' || v > 0xFFFFFFFFul) return Invalid;
  out = (uint32_t)v;
  return Ok;
}

}  // namespace json
