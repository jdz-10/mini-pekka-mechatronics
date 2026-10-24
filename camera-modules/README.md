
# Camera modules

This folder contains the ESP32-S3 camera firmware. It starts the camera, connects to
Wi-Fi, and serves both a browser-based camera control page and an MJPEG stream for the
laptop vision script.

## Hardware and board setup

The pin definitions in [board_config.h](board_config.h) target the nulllaborg
ESP32-S3-CAM:

| Signal | GPIO |
| --- | ---: |
| XCLK | 15 |
| SCCB SDA / SCL | 4 / 5 |
| D0-D7 | 11, 9, 8, 10, 12, 18, 17, 16 |
| VSYNC / HREF / PCLK | 6 / 7 / 13 |
| Camera LED | 3 |

The sketch does not use a camera power-down or reset GPIO (`-1` for both). Confirm
your board matches this mapping before flashing.

In Arduino IDE:

1. Install the **esp32 by Espressif Systems** board package through Boards Manager.
2. Open `CameraWebServer-mecha.ino`; the other `.cpp`, `.h`, and `.csv` files stay in
   the same sketch folder.
3. Select the ESP32-S3 board configuration matching the `esp32s3` entries in
   [ci.yml](ci.yml). The intended runtime is an ESP32-S3 with PSRAM enabled.
4. In `CameraWebServer-mecha.ino`, set `ssid` and `password` to a trusted local
   network. These are currently source constants, so keep real credentials out of
   commits.
5. Select the correct COM port and upload.

The sketch uses JPEG frames, starts at a high camera configuration when memory allows,
and reduces the sensor output to QVGA for streaming. The custom
[partitions.csv](partitions.csv) reserves application, filesystem, and coredump
regions. Keep the custom partition scheme selected when compiling.

## Running it

Open Serial Monitor at **115200 baud**. On success, the board prints a line similar
to:

```text
Camera Ready! Use 'http://192.168.x.x' to connect
```

The camera server uses port 80 for the control page and port 81 for the stream:

| URL | Purpose |
| --- | --- |
| `http://<ip>/` | Embedded camera control UI |
| `http://<ip>:81/stream` | MJPEG stream consumed by OpenCV |
| `http://<ip>/capture` | Single JPEG capture |
| `http://<ip>/status` | Camera status |
| `http://<ip>/control?...` | Camera control commands from the UI |

Additional low-level sensor endpoints (`/bmp`, `/xclk`, `/reg`, `/greg`, `/pll`, and
`/resolution`) are registered by `app_httpd.cpp` for the embedded UI. They are not
needed by the Python preview.

## Files

- `CameraWebServer-mecha.ino` — startup, camera configuration, Wi-Fi, and server
  startup.
- `board_config.h` — board-specific camera pin map.
- `app_httpd.cpp` — embedded web UI handlers, camera controls, capture, and stream
  server.
- `camera_index.h` — compressed HTML assets for the embedded camera UI.
- `camera_pins.h` — alternate/reference camera pin definitions retained with the
  project.
- `partitions.csv` — custom flash partition layout.
- `ci.yml` — ESP32 Arduino CI build matrix/configuration.

## Troubleshooting and limitations

- Both the board and laptop must be on the same network. The IP can change after
  reboot; always use the current address from Serial Monitor.
- A bad Wi-Fi credential causes the firmware to wait in `setup()` while it retries.
- The stream is unauthenticated HTTP. Use a private network only; do not port-forward
  it.
- If initialization fails, check the board model, PSRAM setting, pin map, power, and
  serial error code before changing camera settings.
