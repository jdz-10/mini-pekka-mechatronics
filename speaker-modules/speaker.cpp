#include <Arduino.h>
#include <ESP_I2S.h>

I2SClass I2S;

#define BCLK_PIN 47
#define LRC_PIN  14
#define DATA_PIN 1

void setup() {
  I2S.setPins(BCLK_PIN, LRC_PIN, DATA_PIN);

  I2S.begin(
    I2S_MODE_STD,
    8000,
    I2S_DATA_BIT_WIDTH_16BIT,
    I2S_SLOT_MODE_STEREO
  );
}

void loop() {
  static bool highState = false;

  int16_t sample = highState ? 12000 : -12000;

  int16_t stereo[2] = {
    sample,
    sample
  };

  // Hold each polarity for ~10 ms
  for (int i = 0; i < 80; i++) {
    I2S.write((uint8_t*)stereo, sizeof(stereo));
  }

  highState = !highState;
}