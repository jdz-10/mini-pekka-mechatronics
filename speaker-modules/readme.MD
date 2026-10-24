# Speaker modules

This folder contains a standalone ESP32 sketch that plays an MP3 through an I2S
amplifier. It is independent of the camera firmware.

## Hardware and wiring

The sketch is written for an ESP32-S3 and uses these GPIO assignments:

| MAX98357A signal | ESP32 GPIO |
| --- | ---: |
| BCLK | 47 |
| LRC / word select | 14 |
| DIN | 1 |

Connect amplifier power and ground according to the board's electrical requirements,
connect the speaker to the amplifier output, and share ground between the ESP32 and
amplifier. The sketch currently forces mono output. The LRC connection is known to
need troubleshooting in the current hardware setup; if audio only works with LRC
disconnected, do not treat that as a finished wiring configuration.

## Arduino IDE setup

Install:

- **esp32 by Espressif Systems** through Arduino IDE Boards Manager.
- **ESP32Servo** through Library Manager for the broader project hardware (the current
  `speaker.cpp` does not include it).
- **ESP32-audioI2S** for MP3/WAV playback through the MAX98357A.
- A LittleFS data uploader plugin for the IDE. This is a VSIX/tool, not an Arduino
  library.

Select **ESP32S3 Dev Module**. Select the board's matching flash/partition settings
before uploading.

## Uploading firmware and audio

1. Open `speaker.cpp` as the sketch source.
2. Confirm the I2S pin constants and the `/ben.mp3` filename.
3. Compile and upload the firmware.
4. Upload the contents of the `data` folder to LittleFS using the installed uploader.
   The resulting filesystem must contain `/ben.mp3`.
5. Open Serial Monitor at **115200 baud**.

On startup the sketch mounts LittleFS, configures I2S, sets volume to 20 out of 255,
and starts `/ben.mp3`. When playback finishes, it waits at least three seconds before
starting the file again.

## Files

- `speaker.cpp` — LittleFS initialization, I2S setup, playback loop, and repeat delay.
- `data/ben.mp3` — audio file expected at `/ben.mp3` in LittleFS after upload.

## Troubleshooting

- **`LittleFS failed`:** format/upload the filesystem and verify that `ben.mp3` is
  inside the uploaded `data` folder with the exact lowercase filename.
- **No sound:** check amplifier power, shared ground, BCLK/LRC/DIN wiring, speaker
  impedance, and the selected board. Confirm the amplifier input is connected to
  ESP32 GPIO 1 (DIN).
- **Distorted or quiet audio:** the current gain/volume behavior is not finalized;
  adjust `audio.setVolume(20)` cautiously and avoid unsafe amplifier levels.
- **Playback does not repeat:** verify the file is present and watch Serial Monitor
  for the `LittleFS failed` message.
