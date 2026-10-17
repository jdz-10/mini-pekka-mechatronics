#include <Arduino.h>
#include <Audio.h>
#include <LittleFS.h>

#define I2S_BCLK 47
#define I2S_LRC  14
#define I2S_DOUT 1

Audio audio;

unsigned long lastPlay = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  if (!LittleFS.begin(false)) {
    Serial.println("LittleFS failed");
    while (true);
  }

  audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);

  audio.setVolumeSteps(255);
  audio.setVolume(20);

  audio.forceMono(true);

  Serial.println("Playing...");
  audio.connecttoFS(LittleFS, "/ben.mp3");
}

void loop() {
  audio.loop();

  if (!audio.isRunning() && millis() - lastPlay > 3000) {
    Serial.println("Playing Ben");
    audio.connecttoFS(LittleFS, "/ben.mp3");
    lastPlay = millis();
  }

  vTaskDelay(1);
}