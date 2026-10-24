# Combined camera and servo module

This folder contains firmware for the ESP32-S3 board with both the camera and head
servo attached. It serves the camera stream and receives servo commands in the same
firmware:

```text
ESP32-S3 camera + servo
       ├── port 80  /servo?angle=90
       └── port 81  /stream
```

## Setup

Install the Espressif ESP32 board package and the `ESP32Servo` library. Select
**ESP32S3 Dev Module** with PSRAM enabled.

Before uploading, create `secrets.h` by copying `secrets.h.example` in this folder.
Set `WIFI_SSID` and `WIFI_PASSWORD` there. `secrets.h` is ignored by Git and must
remain local. The repository also includes a root `.env.example` for documenting the
same values, but Arduino IDE does not load `.env` files directly.

Keep these files in the same Arduino sketch folder:

- `main.ino` — camera, Wi-Fi, and servo initialization.
- `secrets.h` — local Wi-Fi credentials; create this from `secrets.h.example`.
- `secrets.h.example` — safe template for local credentials.
- `app_httpd.cpp` — camera UI, MJPEG stream, and servo endpoint.
- `board_config.h` — ESP32-S3 camera pin map.
- `camera_index.h` — embedded camera control page.
- `camera_pins.h` — reference camera pin definitions.

Open Serial Monitor at **115200 baud** and note the IP printed by the board.

## Test the board

Open the camera page and stream:

```text
http://<board-ip>/
http://<board-ip>:81/stream
```

Test the servo:

```powershell
curl.exe "http://<board-ip>/servo?angle=90"
curl.exe "http://<board-ip>/servo?angle=45"
curl.exe "http://<board-ip>/servo?angle=135"
```

The endpoint accepts whole-number angles from 0 through 180. The servo signal is on
GPIO 14. Use appropriate servo power and connect the servo power ground to ESP32
ground.

## Run with Python

Because both devices are on one ESP32, use the same board IP for both options:

```powershell
python .\mini_pekka_tracking.py `
  --camera-url http://<board-ip>:81/stream `
  --servo-url http://<board-ip>
```

Python reads the MJPEG stream on port 81 and sends nose-position-derived angle
commands to `/servo` on port 80.
