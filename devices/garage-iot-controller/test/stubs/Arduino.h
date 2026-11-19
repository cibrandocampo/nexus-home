// Minimal Arduino stand-in so garage.cpp can be compiled and tested on a PC.
#pragma once
#include <cstdint>
#include <cstring>
#include <cstddef>
#include <cstdio>
#include <cstdlib>

enum { LOW = 0, HIGH = 1, INPUT = 0, OUTPUT = 1, INPUT_PULLUP = 2, LED_BUILTIN = 13 };
extern int pins[32];
extern uint32_t fakeMillis;
inline void pinMode(int, int) {}
inline int digitalRead(int p) { return pins[p]; }
constexpr int A0 = 14;
inline int analogRead(int p) { return pins[p]; }
inline void digitalWrite(int p, int v) { pins[p] = v; }
inline void noInterrupts() {}
inline void interrupts() {}
inline uint32_t millis() { return fakeMillis; }
