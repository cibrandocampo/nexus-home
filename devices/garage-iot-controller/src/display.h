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

// State for IP display
unsigned long ipDisplayStartTime = 0;
bool ipDisplayActive = false;
uint8_t ipLastOctet = 0;

// Set pixel in 12x8 LED matrix (row-major mapping with bit inversion)
void setPixel(uint32_t frame[3], int x, int y) {
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

// Draw a digit (3x4 pixels) at position x, y
void drawDigit(uint32_t frame[3], int x, int y, int digit) {
  // Patterns for digits 0-9 (3x4 pixels)
  // Each digit is represented as 4 rows of 3 bits
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

// Draw a dot (1x1 pixel)
void drawDot(uint32_t frame[3], int x, int y) {
  setPixel(frame, x, y);
}

// Display IP last octet (e.g., ".190")
void mxShowIP(uint8_t lastOctet) {
  ipDisplayStartTime = millis();
  ipDisplayActive = true;
  ipLastOctet = lastOctet;
}

// Check if IP display should be shown
bool shouldShowIP() {
  if (!ipDisplayActive) return false;
  if (millis() - ipDisplayStartTime > 5000) { // 5 seconds
    ipDisplayActive = false;
    return false;
  }
  return true;
}

// Display status on 12x8 LED matrix
// Layout: Inputs (2x2 blocks), Outputs (3x3 blocks), WiFi bar
// Or IP display if active
void mxShowStatus() {
  // Check if display is enabled (pin 13: LOW = OFF, HIGH/floating = ON)
  if (digitalRead(PIN_DISPLAY_ENABLE) == LOW) {
    // Display disabled: show empty frame
    uint32_t frame[3] = {0, 0, 0};
    matrix.loadFrame(frame);
    return;
  }
  
  uint32_t frame[3] = {0, 0, 0};
  
  // If IP display is active, show IP instead of status
  if (shouldShowIP()) {
    // Display "XXX" format (last octet of IP, without dot)
    // Extract digits from last octet (0-255)
    int hundreds = ipLastOctet / 100;
    int tens = (ipLastOctet / 10) % 10;
    int ones = ipLastOctet % 10;
    
    // Calculate starting position to center the display
    // Digits are 3x4, spacing is 1 pixel between digits
    int numDigits = (hundreds > 0 ? 3 : (tens > 0 ? 2 : 1));
    int totalWidth = (numDigits * 3) + (numDigits > 1 ? (numDigits - 1) : 0); // digits(3 each) + spacing(1 between)
    int startX = (12 - totalWidth) / 2; // Center horizontally
    
    // Draw digits (y=2 for 4-row digits, centered in 8-row matrix)
    int digitX = startX;
    if (hundreds > 0) {
      drawDigit(frame, digitX, 2, hundreds);
      digitX += 4; // 3 pixels digit + 1 pixel spacing
    }
    if (hundreds > 0 || tens > 0) {
      drawDigit(frame, digitX, 2, tens);
      digitX += 4;
    }
    drawDigit(frame, digitX, 2, ones);
    
    matrix.loadFrame(frame);
    return;
  }
  
  // Normal status display
  bool doorClosed = isDoorClosed();
  bool night = isNightNow();
  bool wifiConnected = (WiFi.status() == WL_CONNECTED);
  
  // Row 0: Inputs (2x2 blocks with 1px spacing)
  if (night) drawBlock2x2(frame, 0, 0);        // N (Night)
  if (doorClosed) drawBlock2x2(frame, 3, 0);   // C (Closed)
  if (buttonLatched) drawBlock2x2(frame, 6, 0); // I (Interruptor/Button)
  
  // Row 4-6: Outputs (3x3 blocks with 1px spacing)
  if (lightOn) drawBlock3x3(frame, 0, 4);     // L (Light)
  if (doorPulseActive) drawBlock3x3(frame, 4, 4); // P (Door Pulse)
  
  // WiFi bar (columns 10-11, vertical)
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


