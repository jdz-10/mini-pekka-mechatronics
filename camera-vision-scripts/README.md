
# Camera vision scripts

This folder contains the laptop-side body-tracking preview. It connects to the
ESP32 camera's MJPEG stream, runs MediaPipe pose tracking, displays the detected
landmarks and smoothed upper-arm angles, and can send head-angle commands to a
separate servo ESP32.

## Requirements

- Python 3.9 or newer (use the version supported by the installed MediaPipe release).
- A laptop with a webcam-capable OpenCV environment.
- The laptop and ESP32 camera on the same Wi-Fi network.
- Python packages:

  ```powershell
  python -m pip install mediapipe opencv-python
  ```

The repository includes `pose_landmarker_lite.task`. The script also includes the
expected name and download URL for that model. `hand_landmarker.task` is retained for
future hand-tracking work; the current script does not load it.

## Run the preview

From this folder:

```powershell
python mini_pekka_tracking.py --camera-url <board-ip>
```

The script accepts a bare IP, a board URL, or the full stream URL. These inputs are
equivalent:

```text
192.168.137.115
http://192.168.137.115
http://192.168.137.115:81/stream
```

All three are normalized to the port-81 stream. The same board address is used for
servo commands on port 80.

You can omit the option and enter any of those forms when prompted:

```powershell
python mini_pekka_tracking.py
```

Click the preview window before using keyboard controls. Press `Q`, `q`, or `Esc` to
quit.

For the combined camera-and-servo ESP32, provide only one address:

```powershell
python mini_pekka_tracking.py --camera-url <board-ip>
```

The script maps the detected nose position to a servo angle: image-left maps toward
180 degrees, image-right maps toward 0 degrees, and the center maps to 90 degrees.
Commands are rate-limited to avoid flooding the servo board. A separate
`--servo-url` can still be supplied if the camera and servo are on different boards.
Vision control sends angles over UDP port `4210` so servo updates do not wait for the
camera web server. The HTTP `/servo?angle=...` endpoint remains available for manual
testing.

## What the script measures

The script tracks one pose and draws the visible face, shoulder, elbow, wrist, and hip
landmarks. It reports left and right upper-arm elevation relative to the torso:

- approximately `0°` — arm down
- approximately `90°` — arm sideways
- approximately `180°` — arm overhead

Angles are calculated in the image plane and smoothed for display. They are not
calibrated servo positions. Landmarks below the visibility/presence threshold or
outside the image are ignored, so the corresponding arm may temporarily show as
unavailable.

## Files

- `mini_pekka_tracking.py` — OpenCV stream reader, MediaPipe pose detector, angle
  calculation, smoothing, and preview UI.
- `pose_landmarker_lite.task` — MediaPipe pose model loaded by the script.
- `hand_landmarker.task` — available hand model for future work; currently unused.

The current control path only commands the head servo. It does not command arm motors.
The servo board validates angles from 0 through 180 degrees. A future motor-control
layer should add calibration, speed limits, a communication watchdog, and an
emergency stop rather than using pose values without safety checks.

The Python capture loop intentionally keeps only the newest camera frame. This avoids
latency accumulating when MediaPipe takes longer to process a frame than the camera
takes to produce one.

## Troubleshooting

- **Could not open the camera:** verify the camera is powered and use the latest IP
  printed by the ESP32. Test `http://<camera-ip>/` in a browser and confirm port 81 is
  reachable.
- **Missing pose model:** keep `pose_landmarker_lite.task` beside the Python file and
  use the download URL in the script's module documentation if it is missing.
- **No landmarks:** improve lighting, face the camera, and keep shoulders, elbows,
  hips, and face visible.
- **Window does not quit:** click the OpenCV window first, then press `Q` or `Esc`.
