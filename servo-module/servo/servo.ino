#include <Arduino.h>
#include <ESP32Servo.h>
#include <WebServer.h>
#include <WiFi.h>

const char *ssid = "YOUR_WIFI_NAME";
const char *password = "YOUR_WIFI_PASSWORD";

const int SERVO_PIN = 14;
const int MIN_ANGLE = 0;
const int MAX_ANGLE = 180;

Servo headServo;
WebServer server(80);
int headAngle = 90;

void sendJson(int statusCode, const String &body) {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(statusCode, "application/json", body);
}

void handleRoot() {
  sendJson(200, "{\"name\":\"mini-pekka-servo\",\"endpoint\":\"/servo?angle=90\"}");
}

void handleStatus() {
  sendJson(200, "{\"angle\":" + String(headAngle) + "}");
}

void handleServo() {
  if (!server.hasArg("angle")) {
    sendJson(400, "{\"error\":\"missing angle query parameter\"}");
    return;
  }

  int requestedAngle = server.arg("angle").toInt();
  if (requestedAngle < MIN_ANGLE || requestedAngle > MAX_ANGLE) {
    sendJson(400, "{\"error\":\"angle must be between 0 and 180\"}");
    return;
  }

  headAngle = requestedAngle;
  headServo.write(headAngle);
  Serial.printf("Servo angle: %d\n", headAngle);
  sendJson(200, "{\"angle\":" + String(headAngle) + "}");
}

void connectToWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to Wi-Fi");

  const unsigned long timeout = 20000;
  const unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < timeout) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWi-Fi connection failed.");
    return;
  }

  Serial.println("\nWi-Fi connected.");
  Serial.print("Servo address: http://");
  Serial.println(WiFi.localIP());
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  headServo.setPeriodHertz(50);
  if (!headServo.attach(SERVO_PIN, 500, 2400)) {
    Serial.println("Servo attach failed.");
  }
  headServo.write(headAngle);

  connectToWifi();

  server.on("/", HTTP_GET, handleRoot);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/servo", HTTP_GET, handleServo);
  server.begin();
  Serial.println("HTTP server started.");
}

void loop() {
  server.handleClient();
}
