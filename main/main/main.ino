#include <Arduino.h>
#include "esp_camera.h"
#include <ESP32Servo.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#include "board_config.h"
#include "secrets.h"

const char *ssid = WIFI_SSID;
const char *password = WIFI_PASSWORD;

const int SERVO_PIN = 14;
const int MIN_ANGLE = 0;
const int MAX_ANGLE = 180;
const unsigned int SERVO_UDP_PORT = 4210;

Servo headServo;
WiFiUDP servoUdp;
int headAngle = 90;

void startCameraServer();
void setupLedFlash();

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("\nStarting combined camera and servo setup...");
  Serial.setDebugOutput(true);

  headServo.setPeriodHertz(50);
  if (!headServo.attach(SERVO_PIN, 500, 2400)) {
    Serial.println("Servo attach failed.");
  }
  headServo.write(headAngle);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_QVGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 15;
  config.fb_count = 2;
  config.grab_mode = CAMERA_GRAB_LATEST;

  if (config.pixel_format == PIXFORMAT_JPEG) {
    if (psramFound()) {
      config.jpeg_quality = 15;
    } else {
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    config.frame_size = FRAMESIZE_240X240;
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

  esp_err_t error = esp_camera_init(&config);
  if (error != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", error);
    return;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  if (sensor->id.PID == OV3660_PID) {
    sensor->set_vflip(sensor, 1);
    sensor->set_brightness(sensor, 1);
    sensor->set_saturation(sensor, -2);
  }
  if (config.pixel_format == PIXFORMAT_JPEG) {
    sensor->set_framesize(sensor, FRAMESIZE_QVGA);
  }

#if defined(LED_GPIO_NUM)
  setupLedFlash();
#endif

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  WiFi.setSleep(false);
  Serial.print("Wi-Fi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWi-Fi connected.");
  servoUdp.begin(SERVO_UDP_PORT);
  Serial.print("Combined camera/servo address: http://");
  Serial.println(WiFi.localIP());

  startCameraServer();
  Serial.println("Camera page: port 80 | MJPEG stream: port 81");
  Serial.println("Servo endpoint: /servo?angle=90");
  Serial.println("Servo UDP port: 4210");
}

void loop() {
  int packetSize = servoUdp.parsePacket();
  if (packetSize > 0) {
    char packet[16];
    int length = servoUdp.read(packet, sizeof(packet) - 1);
    packet[length] = '\0';

    char *end = nullptr;
    long requestedAngle = strtol(packet, &end, 10);
    if (end != packet && (*end == '\0' || *end == '\r' || *end == '\n') &&
        requestedAngle >= MIN_ANGLE && requestedAngle <= MAX_ANGLE) {
      headAngle = static_cast<int>(requestedAngle);
      headServo.write(headAngle);
    }
  }

  delay(1);
}
