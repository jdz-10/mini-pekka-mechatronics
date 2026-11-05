#include <Arduino.h>
#include "esp_camera.h"
#if __has_include("esp_arduino_version.h")
#include "esp_arduino_version.h"
#else
#define ESP_ARDUINO_VERSION_MAJOR 2
#endif
#include <WiFi.h>
#include <WiFiUdp.h>

#include "board_config.h"
#include "secrets.h"

const char *ssid = WIFI_SSID;
const char *password = WIFI_PASSWORD;

// GPIO 14, 41, and 42 are used for servo outputs on this board configuration.
// GPIO 46 is input-only on the ESP32-S3 and cannot drive a servo.
const int SERVO_PIN = 14;
const int LEFT_ARM_SERVO_PIN = 41;
const int RIGHT_ARM_SERVO_PIN = 42;
const int HEAD_PWM_CHANNEL = 4;
const int LEFT_ARM_PWM_CHANNEL = 5;
const int RIGHT_ARM_PWM_CHANNEL = 6;
const int SERVO_PWM_FREQUENCY = 50;
const int SERVO_PWM_RESOLUTION = 14;
const int SERVO_MIN_PULSE_US = 500;
const int SERVO_MAX_PULSE_US = 2400;
const int MIN_ANGLE = 0;
const int MAX_ANGLE = 180;
const unsigned int SERVO_UDP_PORT = 4210;

WiFiUDP servoUdp;
bool servoUdpReady = false;
int headAngle = 90;
int lastLoggedHead = -1;
int lastLoggedLeft = -1;
int lastLoggedRight = -1;

void startCameraServer();
void setupLedFlash();

int servoDutyForAngle(int angle) {
  const int pulseUs = map(angle, MIN_ANGLE, MAX_ANGLE,
                           SERVO_MIN_PULSE_US, SERVO_MAX_PULSE_US);
  const uint32_t maxDuty = (1UL << SERVO_PWM_RESOLUTION) - 1;
  return static_cast<int>((static_cast<uint64_t>(pulseUs) * maxDuty) / 20000);
}

bool attachServoPwm(int pin, int channel) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  // Core 3 allocates the LEDC channel from the pin attachment.
  return ledcAttach(pin, SERVO_PWM_FREQUENCY, SERVO_PWM_RESOLUTION);
#else
  if (ledcSetup(channel, SERVO_PWM_FREQUENCY, SERVO_PWM_RESOLUTION) == 0) {
    return false;
  }
  ledcAttachPin(pin, channel);
  return true;
#endif
}

void writeServoAngle(int channel, int angle) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  const int pin = channel == HEAD_PWM_CHANNEL
                      ? SERVO_PIN
                      : channel == LEFT_ARM_PWM_CHANNEL
                          ? LEFT_ARM_SERVO_PIN
                          : RIGHT_ARM_SERVO_PIN;
  ledcWrite(pin, servoDutyForAngle(angle));
#else
  ledcWrite(channel, servoDutyForAngle(angle));
#endif
}

void writeHeadServo(int angle) {
  writeServoAngle(HEAD_PWM_CHANNEL, angle);
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("\nStarting combined camera and servo setup...");
  Serial.setDebugOutput(true);
  Serial.printf("Servo pins: head=%d (LEDC %d), left=%d (LEDC %d), "
                "right=%d (LEDC %d)\n",
                SERVO_PIN, HEAD_PWM_CHANNEL, LEFT_ARM_SERVO_PIN,
                LEFT_ARM_PWM_CHANNEL, RIGHT_ARM_SERVO_PIN, RIGHT_ARM_PWM_CHANNEL);

  bool headAttached = attachServoPwm(SERVO_PIN, HEAD_PWM_CHANNEL);
  bool leftAttached = attachServoPwm(LEFT_ARM_SERVO_PIN, LEFT_ARM_PWM_CHANNEL);
  bool rightAttached = attachServoPwm(RIGHT_ARM_SERVO_PIN, RIGHT_ARM_PWM_CHANNEL);
  writeHeadServo(headAngle);
  writeServoAngle(LEFT_ARM_PWM_CHANNEL, 0);
  writeServoAngle(RIGHT_ARM_PWM_CHANNEL, 180);
  Serial.printf("Servo attach status: head=%s, left=%s, right=%s\n",
                headAttached ? "OK" : "FAILED",
                leftAttached ? "OK" : "FAILED",
                rightAttached ? "OK" : "FAILED");
  Serial.println("Initial servo angles: head=90, left=0, right=180");

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
  servoUdpReady = servoUdp.begin(SERVO_UDP_PORT) == 1;
  if (!servoUdpReady) {
    Serial.printf("Failed to bind servo UDP port %u. Retrying...\n",
                  SERVO_UDP_PORT);
    servoUdp.stop();
    delay(100);
    servoUdpReady = servoUdp.begin(SERVO_UDP_PORT) == 1;
  }
  if (!servoUdpReady) {
    Serial.printf("Servo UDP unavailable on port %u.\n", SERVO_UDP_PORT);
  }
  Serial.print("Combined camera/servo address: http://");
  Serial.println(WiFi.localIP());

  startCameraServer();
  Serial.println("Camera page: port 80 | MJPEG stream: port 81");
  Serial.println("Servo endpoint: /servo?angle=90");
  if (servoUdpReady) {
    Serial.printf("Servo UDP port: %u\n", SERVO_UDP_PORT);
  }
}

void loop() {
  if (!servoUdpReady) {
    delay(1000);
    return;
  }

  int packetSize = servoUdp.parsePacket();
  if (packetSize > 0) {
    char packet[32];
    int length = servoUdp.read(packet, sizeof(packet) - 1);
    packet[length] = '\0';
    Serial.printf("UDP packet from %s:%u (%d bytes): \"%s\"\n",
                  servoUdp.remoteIP().toString().c_str(), servoUdp.remotePort(),
                  packetSize, packet);

    int requestedHead;
    int requestedLeft;
    int requestedRight;
    int values = sscanf(packet, "%d,%d,%d", &requestedHead, &requestedLeft,
                        &requestedRight);
    if (values == 3 &&
        requestedHead >= MIN_ANGLE && requestedHead <= MAX_ANGLE &&
        requestedLeft >= MIN_ANGLE && requestedLeft <= MAX_ANGLE &&
        requestedRight >= MIN_ANGLE && requestedRight <= MAX_ANGLE) {
      headAngle = requestedHead;
      writeHeadServo(requestedHead);
      writeServoAngle(LEFT_ARM_PWM_CHANNEL, requestedLeft);
      writeServoAngle(RIGHT_ARM_PWM_CHANNEL, requestedRight);
      if (requestedHead != lastLoggedHead ||
          requestedLeft != lastLoggedLeft ||
          requestedRight != lastLoggedRight) {
        Serial.printf("Applied angles: head=%d, left=%d, right=%d (right GPIO %d)\n",
                      requestedHead, requestedLeft, requestedRight,
                      RIGHT_ARM_SERVO_PIN);
        lastLoggedHead = requestedHead;
        lastLoggedLeft = requestedLeft;
        lastLoggedRight = requestedRight;
      }
    } else {
      Serial.printf("Rejected UDP packet: parsed %d value(s); expected three "
                    "angles from %d to %d.\n",
                    values, MIN_ANGLE, MAX_ANGLE);
    }
  }

  delay(1);
}
