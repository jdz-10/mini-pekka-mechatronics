# Combined camera and servo module

This folder contains firmware for the ESP32-S3 board with both the camera and head
servo attached. It serves the camera stream and receives servo commands in the same
firmware:

```text
ESP32-S3 camera + servo
       ├── port 80  /servo?angle=90
       ├── port 81  /stream
       └── UDP 4210  head,left-arm,right-arm
```

## Setup

Install the Espressif ESP32 board package. The firmware uses the Arduino LEDC
API directly, so no separate servo library is required. Select **ESP32S3 Dev
Module** with PSRAM enabled.

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
At startup, the monitor also reports the configured GPIO pins and whether each
servo attached successfully. Each received UDP packet is printed, and each
changed set of applied angles identifies the right-arm output GPIO. A normal right-arm command should look like:

```text
Applied angles: head=90, left=0, right=90 (right GPIO 42)
```

If packets appear but the right angle never changes, the Python tracking state
is not requesting a new right-arm position. If the right angle changes but the
servo does not move, check the right servo signal wire on GPIO 42, its 5 V
power, and the shared ground. A `right=...` line with `right GPIO 42` confirms
the firmware reached the right-servo write call.

The firmware uses direct Arduino LEDC PWM rather than `ESP32Servo`. The camera
occupies LEDC channel 0, while the Arduino core allocates the three servo
channels separately at 50 Hz with 14-bit resolution. `setTimerWidth()` or assigning different
channel numbers alone does not solve a pin attachment problem; the output pin
must also be valid and physically wired to the matching header pin. GPIO 46 is
not used for the right servo.

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

The endpoint accepts whole-number angles from 0 through 180. On the nulllaborg
ESP32-S3-CAM, the head-servo signal is on GPIO 14; left- and right-arm servos use
GPIO 41 and GPIO 42. These pins are exposed on the board header and are not part
of this board's camera interface. GPIO 43 and GPIO 44 are reserved for the
ESP32-S3's default UART0 serial connection and must not be used for servos. UDP
packets from Python contain three comma-separated angles, for example `90,0,180`.
Power the servos from a separate 5 V supply capable of handling their combined
startup/stall current, and connect that supply ground to ESP32 ground. Do not power
three servos from the ESP32 5 V/USB rail: when pose recognition first moves the
servos, the current spike can brown out or reset the board and make the camera
stream appear to freeze.

## Run with Python

Because both devices are on one ESP32, use the same board IP for both options:

```powershell
python .\mini_pekka_tracking.py `
  --camera-url http://<board-ip>:81/stream `
  --servo-url http://<board-ip>
```

Python reads the MJPEG stream on port 81 and sends head/arm angle commands over UDP
port 4210. The firmware verifies that this port is available during startup and
reports a bind failure in Serial Monitor instead of claiming the endpoint is active.
An arm is raised when its smoothed elevation reaches 90 degrees
(sideways); it returns down below 80 degrees to prevent threshold chatter.

If the right arm does not raise, first confirm that the board reports all three
servo outputs as attached successfully. Then confirm that the log contains
`right=90` when the detected right arm is raised. A log containing only
`right=180` means the tracking threshold has not been reached; a log containing
`right=90` confirms that the software requested the raised position.

If the stream freezes as soon as a pose is recognized, first watch the ESP32
Serial Monitor for a reboot or brownout message and test with the servo power
disconnected. If the stream is stable without servo movement, fix the servo power
and ground wiring before changing the vision code. The Python reader tolerates a
few transient network frame failures, but it cannot keep a stream alive while the
ESP32 is resetting.
