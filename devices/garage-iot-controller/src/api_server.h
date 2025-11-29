#ifndef API_SERVER_H
#define API_SERVER_H

#include <WiFiS3.h>

extern WiFiServer server;
extern bool isDoorClosed();
extern bool isNightNow();
extern bool lightOn;
extern unsigned long lightStartMs;
extern unsigned long lightDurationMs;
extern const unsigned long LIGHT_DEFAULT_SECONDS;
extern void handleDoorAction(const char* source, long requestedSeconds);
extern void setLight(bool on);
extern void mxShowStatus();
void sendJson(WiFiClient& client, int code, const String& body) {
  client.println("HTTP/1.1 " + String(code) + " OK");
  client.println("Content-Type: application/json");
  client.println("Connection: close");
  client.print("Content-Length: "); client.println(body.length());
  client.println();
  client.print(body);
}

String ipToString(IPAddress ip) {
  return String(ip[0]) + "." + String(ip[1]) + "." + String(ip[2]) + "." + String(ip[3]);
}

bool jsonHas(const String& body, const char* key, const char* val) {
  String patterns[] = {
    String("\"") + String(key) + "\":\"" + String(val) + "\"",
    String("\"") + String(key) + "\" : \"" + String(val) + "\"",
    String("\"") + String(key) + "\": \"" + String(val) + "\"",
    String("\"") + String(key) + "\" :\"" + String(val) + "\"",
  };
  
  for (int i = 0; i < 4; i++) {
    if (body.indexOf(patterns[i]) >= 0) {
      return true;
    }
  }
  
  String keyPattern = String("\"") + String(key) + "\"";
  int keyPos = body.indexOf(keyPattern);
  if (keyPos < 0) return false;
  
  int searchEnd = keyPos + keyPattern.length() + 50;
  if (searchEnd > (int)body.length()) searchEnd = body.length();
  String searchArea = body.substring(keyPos, searchEnd);
  
  String valWithQuotes = String("\"") + String(val) + "\"";
  if (searchArea.indexOf(valWithQuotes) >= 0) {
    return true;
  }
  
  return false;
}

String jsonGetValue(const String& body, const char* key) {
  String keyPattern = String("\"") + String(key) + "\"";
  int keyPos = body.indexOf(keyPattern);
  if (keyPos < 0) return "";
  
  int colonPos = body.indexOf(':', keyPos);
  if (colonPos < 0) return "";
  
  int startPos = colonPos + 1;
  while (startPos < (int)body.length() && (body[startPos] == ' ' || body[startPos] == '\t')) startPos++;
  
  if (startPos >= (int)body.length()) return "";
  
  // Check if value is a string (quoted) or number
  if (body[startPos] == '"') {
    startPos++; // Skip opening quote
    int endPos = body.indexOf('"', startPos);
    if (endPos < 0) return "";
    return body.substring(startPos, endPos);
  } else {
    // Number or boolean
    int endPos = startPos;
    while (endPos < (int)body.length() && 
           (isDigit(body[endPos]) || body[endPos] == '.' || 
            body[endPos] == '-' || body[endPos] == 'e' || 
            body[endPos] == 'E' || body[endPos] == '+' ||
            (body[endPos] >= 'a' && body[endPos] <= 'z') ||
            (body[endPos] >= 'A' && body[endPos] <= 'Z'))) {
      endPos++;
    }
    return body.substring(startPos, endPos);
  }
}

long jsonDurationSec(const String& body, long fallback) {
  int i = body.indexOf("\"duration\"");
  if (i < 0) return fallback;
  i = body.indexOf(':', i);
  if (i < 0) return fallback;
  while (i < (int)body.length() && (body[i] == ':' || body[i] == ' ')) i++;
  String num;
  while (i < (int)body.length() && isDigit(body[i])) num += body[i++];
  return num.length() ? num.toInt() : fallback;
}

void handleStatus(WiFiClient& client) {
  Serial.print("[API] GET /status from ");
  Serial.println(client.remoteIP());
  
  bool closed = isDoorClosed();
  bool night  = isNightNow();

  String doorStr  = closed ? "closed" : "open";
  String lightStr = lightOn ? "on" : "off";
  unsigned long remaining = 0;
  if (lightOn) {
    unsigned long el = millis() - lightStartMs;
    remaining = (el >= lightDurationMs) ? 0 : (lightDurationMs - el);
  }

  bool wifiConnected = (WiFi.status() == WL_CONNECTED);
  String localIP = wifiConnected ? ipToString(WiFi.localIP()) : "0.0.0.0";
  String gateway = wifiConnected ? ipToString(WiFi.gatewayIP()) : "0.0.0.0";
  String subnet = wifiConnected ? ipToString(WiFi.subnetMask()) : "0.0.0.0";
  int rssi = wifiConnected ? WiFi.RSSI() : 0;
  String ssid = wifiConnected ? WiFi.SSID() : "";

  String json = "{";
  json += "\"door\":\"" + doorStr + "\",";
  json += "\"light\":\"" + lightStr + "\",";
  json += "\"night\":" + String(night ? "true" : "false") + ",";
  json += "\"light_timeout_ms\":" + String(remaining) + ",";
  json += "\"network\":{";
  json += "\"connected\":" + String(wifiConnected ? "true" : "false") + ",";
  json += "\"ip\":\"" + localIP + "\",";
  json += "\"gateway\":\"" + gateway + "\",";
  json += "\"subnet\":\"" + subnet + "\",";
  json += "\"rssi\":" + String(rssi) + ",";
  json += "\"ssid\":\"" + ssid + "\"";
  json += "}";
  json += "}";
  sendJson(client, 200, json);
}

void handleSet(WiFiClient& client, const String& body) {
  Serial.print("[API] POST /set from ");
  Serial.print(client.remoteIP());
  Serial.print(" - Body: ");
  Serial.println(body);
  Serial.print("[API] Body length: ");
  Serial.println(body.length());
  
  String normalizedBody = body;
  normalizedBody.replace("\n", "");
  normalizedBody.replace("\r", "");
  normalizedBody.replace("\t", " ");
  while (normalizedBody.indexOf("  ") >= 0) {
    normalizedBody.replace("  ", " ");
  }
  Serial.print("[API] Normalized body: ");
  Serial.println(normalizedBody);
  
  // Get device and action from JSON
  String device = jsonGetValue(normalizedBody, "device");
  String action = jsonGetValue(normalizedBody, "action");
  
  device.toLowerCase();
  action.toLowerCase();
  
  Serial.print("[API] Device: ");
  Serial.print(device);
  Serial.print(", Action: ");
  Serial.println(action);
  
  // Handle door device
  if (device == "door") {
    bool doorClosed = isDoorClosed();
    
    if (action == "open") {
      if (!doorClosed) {
        Serial.println("[API] Door is already open - action ignored");
        sendJson(client, 400, "{\"result\":\"error\",\"message\":\"Door is already open\"}");
        return;
      }
      Serial.println("[API] Door OPEN requested (door is closed)");
      handleDoorAction("API", -1);
      sendJson(client, 200, "{\"result\":\"ok\",\"message\":\"Door open triggered\"}");
      return;
    }
    
    if (action == "close") {
      if (doorClosed) {
        Serial.println("[API] Door is already closed - action ignored");
        sendJson(client, 400, "{\"result\":\"error\",\"message\":\"Door is already closed\"}");
        return;
      }
      Serial.println("[API] Door CLOSE requested (door is open)");
      handleDoorAction("API", -1);
      sendJson(client, 200, "{\"result\":\"ok\",\"message\":\"Door close triggered\"}");
      return;
    }
    
    Serial.println("[API] Unknown door action");
    sendJson(client, 400, "{\"result\":\"error\",\"message\":\"Unknown door action. Use 'open' or 'close'\"}");
    return;
  }
  
  // Handle lamp device
  if (device == "lamp") {
    if (action == "on") {
      long dur = jsonDurationSec(normalizedBody, (long)LIGHT_DEFAULT_SECONDS);
      if (dur <= 0) dur = LIGHT_DEFAULT_SECONDS;
      lightDurationMs = (unsigned long)dur * 1000UL;
      setLight(true);
      Serial.print("[API] Lamp ON requested (duration: ");
      Serial.print(dur);
      Serial.println(" s)");
      mxShowStatus();
      sendJson(client, 200, "{\"result\":\"ok\",\"message\":\"Lamp on\"}");
      return;
    }
    
    if (action == "off") {
      setLight(false);
      Serial.println("[API] Lamp OFF requested");
      mxShowStatus();
      sendJson(client, 200, "{\"result\":\"ok\",\"message\":\"Lamp off\"}");
      return;
    }
    
    Serial.println("[API] Unknown lamp action");
    sendJson(client, 400, "{\"result\":\"error\",\"message\":\"Unknown lamp action. Use 'on' or 'off'\"}");
    return;
  }
  
  Serial.println("[API] Unknown device");
  sendJson(client, 400, "{\"result\":\"error\",\"message\":\"Unknown device. Use 'door' or 'lamp'\"}");
}

void processHttpRequests() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client = server.available();
    if (client) {
      client.setTimeout(600);
      String reqLine = client.readStringUntil('\n');
      reqLine.trim();
      
      int contentLength = 0;
      while (true) {
        String h = client.readStringUntil('\n');
        if (h == "\r" || h.length() == 0) break;
        if (h.startsWith("Content-Length:")) {
          contentLength = h.substring(strlen("Content-Length:")).toInt();
        }
      }
      
      bool getStatus = reqLine.startsWith("GET /status");
      bool postSet   = reqLine.startsWith("POST /set");

      if (getStatus) {
        handleStatus(client);
      } else if (postSet) {
        String body;
        for (int i=0; i<contentLength; ++i) {
          while (!client.available()) { delay(1); }
          body += (char)client.read();
        }
        handleSet(client, body);
      } else {
        Serial.print("[API] 404 - Unknown request: ");
        Serial.println(reqLine);
        sendJson(client, 404, "{\"result\":\"error\",\"message\":\"Not found\"}");
      }
      delay(1);
      client.stop();
    }
  }
}

#endif

