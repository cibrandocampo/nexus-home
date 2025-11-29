#ifndef DISPLAY_H
#define DISPLAY_H

#include <Arduino_LED_Matrix.h>
#include <WiFiS3.h>

ArduinoLEDMatrix matrix;

extern bool isDoorClosed();
extern bool isNightNow();
extern bool lightOn;
extern bool doorPulseActive;
extern bool buttonLatched;
extern const int PIN_DISPLAY_ENABLE;

unsigned long ipDisplayStartTime = 0;
bool ipDisplayActive = false;
uint8_t ipLastOctet = 0;

void setPixel(uint32_t frame[3], int x, int y) {
  // Set a pixel in the 12x8 LED matrix frame buffer
  // Frame is stored as 3 uint32_t values (96 bits total for 12x8 = 96 pixels)
  if (x < 0 || x >= 12 || y < 0 || y >= 8) return;
  
  int bitPos = y * 12 + x;
  int frameIdx = bitPos / 32;
  int bitIdx = bitPos % 32;
  
  if (frameIdx < 3) {
    frame[frameIdx] |= (1UL << (31 - bitIdx));
  }
}

void drawBlock2x2(uint32_t frame[3], int x, int y) {
  setPixel(frame, x, y);
  setPixel(frame, x+1, y);
  setPixel(frame, x, y+1);
  setPixel(frame, x+1, y+1);
}

void drawBlock3x3(uint32_t frame[3], int x, int y) {
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      setPixel(frame, x + i, y + j);
    }
  }
}

void drawDigit(uint32_t frame[3], int x, int y, int digit) {
  const uint8_t digitPatterns[10][4] = {
    {0b111, 0b101, 0b101, 0b111}, // 0
    {0b110, 0b010, 0b010, 0b111}, // 1
    {0b111, 0b001, 0b111, 0b111}, // 2
    {0b111, 0b011, 0b001, 0b111}, // 3
    {0b101, 0b101, 0b111, 0b001}, // 4
    {0b111, 0b110, 0b001, 0b111}, // 5
    {0b111, 0b110, 0b101, 0b111}, // 6
    {0b111, 0b001, 0b001, 0b001}, // 7
    {0b111, 0b101, 0b111, 0b111}, // 8
    {0b111, 0b101, 0b011, 0b111}  // 9
  };
  
  if (digit < 0 || digit > 9) return;
  
  for (int row = 0; row < 4; row++) {
    uint8_t pattern = digitPatterns[digit][row];
    for (int col = 0; col < 3; col++) {
      if (pattern & (1 << (2 - col))) {
        setPixel(frame, x + col, y + row);
      }
    }
  }
}

void drawDot(uint32_t frame[3], int x, int y) {
  setPixel(frame, x, y);
}

void mxShowIP(uint8_t lastOctet) {
  ipDisplayStartTime = millis();
  ipDisplayActive = true;
  ipLastOctet = lastOctet;
}

bool shouldShowIP() {
  if (!ipDisplayActive) return false;
  if (millis() - ipDisplayStartTime > 5000) {
    ipDisplayActive = false;
    return false;
  }
  return true;
}

void mxShowStatus() {
  // Check if display is enabled via pin 6 (LOW = disabled, HIGH/floating = enabled)
  if (digitalRead(PIN_DISPLAY_ENABLE) == LOW) {
    uint32_t frame[3] = {0, 0, 0};
    matrix.loadFrame(frame);
    return;
  }
  
  uint32_t frame[3] = {0, 0, 0};
  
  // Priority: Show IP address if recently connected to WiFi
  if (shouldShowIP()) {
    int hundreds = ipLastOctet / 100;
    int tens = (ipLastOctet / 10) % 10;
    int ones = ipLastOctet % 10;
    int numDigits = (hundreds > 0 ? 3 : (tens > 0 ? 2 : 1));
    int totalWidth = (numDigits * 3) + (numDigits > 1 ? (numDigits - 1) : 0);
    int startX = (12 - totalWidth) / 2;
    int digitX = startX;
    if (hundreds > 0) {
      drawDigit(frame, digitX, 2, hundreds);
      digitX += 4;
    }
    if (hundreds > 0 || tens > 0) {
      drawDigit(frame, digitX, 2, tens);
      digitX += 4;
    }
    drawDigit(frame, digitX, 2, ones);
    matrix.loadFrame(frame);
    return;
  }
  
  // Normal status display: show sensor states and outputs
  // Row 0: Input sensors (2x2 blocks)
  bool doorClosed = isDoorClosed();
  bool night = isNightNow();
  bool wifiConnected = (WiFi.status() == WL_CONNECTED);
  
  if (night) drawBlock2x2(frame, 0, 0);        // Night sensor
  if (doorClosed) drawBlock2x2(frame, 3, 0);   // Door closed
  if (buttonLatched) drawBlock2x2(frame, 6, 0); // Button pressed
  
  // Row 4: Outputs (3x3 blocks)
  if (lightOn) drawBlock3x3(frame, 0, 4);      // Light ON
  if (doorPulseActive) drawBlock3x3(frame, 4, 4); // Door relay active
  
  // Column 10-11: WiFi connection indicator (vertical bar)
  if (wifiConnected) {
    drawBlock2x2(frame, 10, 0);
    drawBlock2x2(frame, 10, 3);
    drawBlock2x2(frame, 10, 5);
    setPixel(frame, 10, 7);
    setPixel(frame, 11, 7);
  }
  
  matrix.loadFrame(frame);
}

#endif


