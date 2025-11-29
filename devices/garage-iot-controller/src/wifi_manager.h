#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <WiFiS3.h>

const char* WIFI_SSID     = "iot_wifi";
const char* WIFI_PASSWORD = "iot_password";
WiFiServer server(80);

extern void mxShowStatus();
extern void mxShowIP(uint8_t lastOctet);

const char* wifiStatusToString(int status) {
  switch(status) {
    case WL_IDLE_STATUS:        return "IDLE (esperando configuración)";
    case WL_NO_SSID_AVAIL:      return "NO_SSID_AVAIL (red no encontrada)";
    case WL_SCAN_COMPLETED:     return "SCAN_COMPLETED (escaneo completado)";
    case WL_CONNECTED:          return "CONNECTED (conectado)";
    case WL_CONNECT_FAILED:     return "CONNECT_FAILED (fallo de conexión)";
    case WL_CONNECTION_LOST:    return "CONNECTION_LOST (conexión perdida)";
    case WL_DISCONNECTED:       return "DISCONNECTED (desconectado)";
    default:                    return "UNKNOWN (desconocido)";
  }
}

// Conecta a WiFi de forma bloqueante
bool connectWiFiBlocking(uint16_t timeoutMs = 20000) {
  Serial.print("[WIFI] Connecting to '");
  Serial.print(WIFI_SSID);
  Serial.print("'");
  Serial.print(" (timeout: ");
  Serial.print(timeoutMs);
  Serial.println(" ms)");
  
  // WiFi.config(localIp, gateway, gateway, subnet); // descomenta si usas IP fija
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  unsigned long t0 = millis();
  int status = WiFi.status();
  int lastLoggedStatus = -1;
  unsigned long lastStatusLogTime = 0;
  
  Serial.print("[WIFI] Initial status: ");
  Serial.print(status);
  Serial.print(" (");
  Serial.print(wifiStatusToString(status));
  Serial.println(")");
  
  bool gotConnected = false;
  unsigned long connectedTime = 0;
  const unsigned long DHCP_WAIT_MS = 5000;
  
  while (true) {
    unsigned long elapsed = millis() - t0;
    
    if (gotConnected) {
      IPAddress ip = WiFi.localIP();
      if (ip != IPAddress(0,0,0,0)) {
        Serial.println();
        Serial.print("[WIFI] IP assigned by DHCP: ");
        Serial.println(ip);
        break;
      }
      
      if (millis() - connectedTime > DHCP_WAIT_MS) {
        Serial.println();
        Serial.print("[WIFI] DHCP timeout: connected but no IP after ");
        Serial.print(DHCP_WAIT_MS);
        Serial.println(" ms");
        break;
      }
      
      delay(250);
      Serial.print(".");
      continue;
    }
    
    if (elapsed > timeoutMs) {
      Serial.println();
      Serial.print("[WIFI] Connection timeout after ");
      Serial.print(timeoutMs);
      Serial.println(" ms");
      break;
    }
    
    delay(250);
    int newStatus = WiFi.status();
    
    if (newStatus != status || (millis() - lastStatusLogTime >= 2000)) {
      if (newStatus != lastLoggedStatus || (millis() - lastStatusLogTime >= 2000)) {
        Serial.println();
        Serial.print("[WIFI] [");
        Serial.print(elapsed);
        Serial.print("ms] Status: ");
        Serial.print(newStatus);
        Serial.print(" (");
        Serial.print(wifiStatusToString(newStatus));
        Serial.print(")");
        
        IPAddress ip = WiFi.localIP();
        if (ip != IPAddress(0,0,0,0)) {
          Serial.print(", IP: ");
          Serial.print(ip);
        }
        
        int rssi = WiFi.RSSI();
        if (rssi != 0) {
          Serial.print(", RSSI: ");
          Serial.print(rssi);
          Serial.print(" dBm");
        }
        
        Serial.println();
        lastLoggedStatus = newStatus;
        lastStatusLogTime = millis();
      }
      status = newStatus;
      
      if (newStatus == WL_CONNECTED && !gotConnected) {
        gotConnected = true;
        connectedTime = millis();
        Serial.println();
        Serial.println("[WIFI] WiFi connected! Waiting for DHCP to assign IP...");
      }
    } else {
      Serial.print(".");
    }
  }
  Serial.println();

  int finalStatus = WiFi.status();
  IPAddress finalIP = WiFi.localIP();
  
  if (finalStatus == WL_CONNECTED && finalIP != IPAddress(0,0,0,0)) {
    Serial.print("[WIFI] ✓ Connected successfully! IP: ");
    Serial.println(finalIP);
    Serial.print("[WIFI] Signal strength (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    Serial.print("[WIFI] Subnet mask: ");
    Serial.println(WiFi.subnetMask());
    Serial.print("[WIFI] Gateway: ");
    Serial.println(WiFi.gatewayIP());
    mxShowIP(finalIP[3]); // Show last octet on LED matrix
    server.begin();
    Serial.println("[WIFI] HTTP server started on port 80");
    return true;
  } else {
    Serial.println("[WIFI] ✗ Connection FAILED");
    Serial.print("[WIFI] Final status: ");
    Serial.print(finalStatus);
    Serial.print(" (");
    Serial.print(wifiStatusToString(finalStatus));
    Serial.println(")");
    Serial.print("[WIFI] IP address: ");
    Serial.println(finalIP);
    
    if (finalStatus == WL_CONNECTED && finalIP == IPAddress(0,0,0,0)) {
      Serial.println("[WIFI] WARNING: Status is CONNECTED but IP is 0.0.0.0");
      Serial.println("[WIFI] This may indicate DHCP failure or network configuration issue");
    } else if (finalStatus == WL_NO_SSID_AVAIL) {
      Serial.println("[WIFI] The SSID was not found. Check:");
      Serial.println("[WIFI]   - SSID name is correct");
      Serial.println("[WIFI]   - Router is powered on and broadcasting");
      Serial.println("[WIFI]   - You are within range");
    } else if (finalStatus == WL_CONNECT_FAILED) {
      Serial.println("[WIFI] Connection failed. Check:");
      Serial.println("[WIFI]   - Password is correct");
      Serial.println("[WIFI]   - Router security settings");
    }
    
    return false;
  }
}

// Non-blocking WiFi reconnection attempt
// Returns true if connection attempt is in progress, false otherwise
bool attemptWiFiReconnect() {
  static unsigned long reconnectStartTime = 0;
  static bool reconnectInProgress = false;
  const unsigned long RECONNECT_TIMEOUT_MS = 10000; // 10 seconds max per attempt
  
  int status = WiFi.status();
  
  // If already connected, reset reconnect state
  if (status == WL_CONNECTED && WiFi.localIP() != IPAddress(0,0,0,0)) {
    if (reconnectInProgress) {
      IPAddress ip = WiFi.localIP();
      Serial.print("[WIFI] Reconnection successful! IP: ");
      Serial.println(ip);
      mxShowIP(ip[3]); // Show last octet on LED matrix
      reconnectInProgress = false;
      server.begin();
      Serial.println("[WIFI] HTTP server started on port 80");
    }
    return false;
  }
  
  // If not connected and not trying to reconnect, start attempt
  if (!reconnectInProgress) {
    Serial.println("[WIFI] Connection lost - starting non-blocking reconnect attempt...");
    WiFi.disconnect();
    delay(100);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    reconnectStartTime = millis();
    reconnectInProgress = true;
    return true;
  }
  
  // Check if reconnect attempt timed out
  if (millis() - reconnectStartTime > RECONNECT_TIMEOUT_MS) {
    Serial.println("[WIFI] Reconnect attempt timeout - will retry later");
    reconnectInProgress = false;
    WiFi.disconnect();
    return false;
  }
  
  // Reconnection in progress - just check status periodically
  static unsigned long lastStatusCheck = 0;
  if (millis() - lastStatusCheck >= 2000) {
    int newStatus = WiFi.status();
    if (newStatus == WL_CONNECTED) {
      IPAddress ip = WiFi.localIP();
      if (ip != IPAddress(0,0,0,0)) {
        Serial.print("[WIFI] Reconnected! IP: ");
        Serial.println(ip);
        mxShowIP(ip[3]); // Show last octet on LED matrix
        reconnectInProgress = false;
        server.begin();
        Serial.println("[WIFI] HTTP server started on port 80");
        return false;
      }
    }
    lastStatusCheck = millis();
  }
  
  return true; // Still trying
}

void ensureWiFi() {
  static unsigned long lastStatusLog = 0;
  static unsigned long lastReconnectAttempt = 0;
  const unsigned long RECONNECT_INTERVAL_MS = 60000; // Try every 60 seconds
  
  unsigned long now = millis();
  
  // Log status every 30 seconds
  if (now - lastStatusLog >= 30000) {
    int status = WiFi.status();
    if (status == WL_CONNECTED && WiFi.localIP() != IPAddress(0,0,0,0)) {
      Serial.print("[WIFI] Status OK - IP: ");
      Serial.print(WiFi.localIP());
      Serial.print(", RSSI: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
    } else {
      Serial.print("[WIFI] Status: ");
      Serial.print(status);
      Serial.print(" (");
      Serial.print(wifiStatusToString(status));
      Serial.println(") - Door logic operational");
    }
    lastStatusLog = now;
  }
  
  // Check connection status and attempt reconnect if needed (every 60 seconds)
  if (now - lastReconnectAttempt < RECONNECT_INTERVAL_MS) {
    // If reconnect is in progress, continue it (non-blocking)
    attemptWiFiReconnect();
    return;
  }
  
  lastReconnectAttempt = now;
  
  // Check if WiFi is disconnected
  if (WiFi.status() != WL_CONNECTED || WiFi.localIP() == IPAddress(0,0,0,0)) {
    // Start non-blocking reconnect attempt
    attemptWiFiReconnect();
  }
}

#endif

