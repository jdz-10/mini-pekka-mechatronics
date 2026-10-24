# Mini Pekka Mechatronics

Code and configuration for the Mini Pekka mechatronics modules. The repository currently
contains two independent ESP32 firmware projects and one laptop-side computer-vision
preview:

```text
camera-modules/          ESP32-S3 camera firmware and web server
camera-vision-scripts/   Python/OpenCV/MediaPipe body-tracking preview
speaker-modules/         ESP32 speaker playback firmware and audio assets
main/main/               Combined ESP32-S3 camera and servo firmware
```

The camera, combined camera/servo, and speaker sketches are separate programs. They
can be flashed to their respective boards independently; the Python script is not
uploaded to an ESP32.

For the combined camera/servo board, use the sketch in
[main/main](main/main). Its camera stream and servo receiver run on the same ESP32.

## Camera-to-vision workflow

1. Install Arduino IDE, the Espressif ESP32 board package, and the dependencies listed
   in [camera-modules/README.md](camera-modules/README.md).
2. Open `camera-modules/CameraWebServer-mecha.ino`, replace the Wi-Fi credentials with
   a network available to both the ESP32 and laptop, and select the board settings
   described in the camera README.
3. Upload the sketch to the ESP32-S3 camera board. Open Serial Monitor at `115200`
   baud and wait for the `Camera Ready!` message and printed IP address.
4. On the laptop, install the Python packages in
   [camera-vision-scripts/README.md](camera-vision-scripts/README.md), place the
   MediaPipe model files beside the script, and run:

   ```powershell
   python mini_pekka_tracking.py --camera-url http://<camera-ip>:81/stream
   ```

   Run that command from `camera-vision-scripts`, or provide the script's full path.
   If `--camera-url` is omitted, the script prompts for the URL.
5. Stand far enough from the camera for the shoulders, elbows, hips, and face to be
   visible. Press `Q` or `Esc` in the preview window to stop.

The current vision script only displays pose landmarks and smoothed upper-arm angles.
It does **not** send motor commands or control the robot.

## Camera and servo together

The camera and servo use separate ESP32 boards, with the Python computer acting as
the bridge:

```text
camera ESP32 --MJPEG video--> Python/MediaPipe --HTTP angle--> servo ESP32
```

Flash [servo.ino](servo-module/servo/servo.ino) to the servo board, set its Wi-Fi
credentials, and note the IP printed in Serial Monitor. Then run the vision script
with both addresses:

```powershell
cd "C:\Users\carte\OneDrive\Desktop\mini-pekka-mechatronics\camera-vision-scripts"
python .\mini_pekka_tracking.py `
  --camera-url http://<camera-ip>:81/stream `
  --servo-url http://<servo-ip>
```

When a visible nose is detected, Python maps its horizontal image position to a
head-servo angle and sends requests such as
`http://<servo-ip>/servo?angle=90`. The servo board validates the angle and moves
the servo. Without `--servo-url`, the Python script remains display-only.

## Speaker workflow

See [speaker-modules/README.md](speaker-modules/README.md). The speaker sketch plays
`speaker-modules/data/ben.mp3` from LittleFS, then repeats it after a short delay.
The data folder must be uploaded to the board's filesystem separately from the
firmware.

## Repository notes

- Camera HTTP control and stream endpoints are described in
  [camera-modules/README.md](camera-modules/README.md).
- Board pin mappings, camera settings, and the custom partition table are kept next to
  the camera sketch so they are changed together.
- Wi-Fi credentials for the combined `main` sketch belong in the ignored
  `main/main/secrets.h`, copied from `secrets.h.example`. Arduino IDE cannot consume
  `.env` files directly; `.env.example` documents the equivalent names.
- The camera server has no authentication or HTTPS. Use it only on a trusted local
  network and do not expose it to the internet.
- Large `.task` model files and the MP3 asset are runtime inputs, not Python packages
  or Arduino libraries.

## Troubleshooting

- **Camera will not connect:** confirm the board is powered, the laptop is on the same
  Wi-Fi network, and the credentials match the network. Read the IP printed by the
  latest Serial Monitor run rather than reusing an old address.
- **Stream URL fails:** open `http://<camera-ip>/` in a browser first, then use
  `http://<camera-ip>:81/stream` for the Python script.
- **No pose detected:** improve lighting, move farther away, and keep the required
  landmarks in frame. The script intentionally discards low-confidence or off-screen
  landmarks.
- **No speaker audio:** verify the LittleFS upload, MP3 filename, I2S wiring, and the
  board/library versions documented in the speaker README.

## Status

This is a working project repository rather than a packaged library. Build and board
configuration details are maintained in each module's README.
