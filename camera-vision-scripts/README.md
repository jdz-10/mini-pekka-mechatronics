
# Camera vision scripts

This folder contains the laptop-side body-tracking preview. It connects to the
ESP32 camera's MJPEG stream, runs MediaPipe pose tracking, and displays the detected
landmarks and smoothed upper-arm angles.

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
python mini_pekka_tracking.py --camera-url http://<camera-ip>:81/stream
```

Or omit the option and enter the URL when prompted:

```powershell
python mini_pekka_tracking.py
```

The camera URL must be a plain `http://` or `https://` URL, not Markdown formatting.
Click the preview window before using keyboard controls. Press `Q`, `q`, or `Esc` to
quit.

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

This preview intentionally does not send motor commands. A future control layer should
add calibration, safety limits, and an explicit transport to the robot rather than
using the displayed angle directly.

## Troubleshooting

- **Could not open the camera:** verify the camera is powered and use the latest IP
  printed by the ESP32. Test `http://<camera-ip>/` in a browser and confirm port 81 is
  reachable.
- **Missing pose model:** keep `pose_landmarker_lite.task` beside the Python file and
  use the download URL in the script's module documentation if it is missing.
- **No landmarks:** improve lighting, face the camera, and keep shoulders, elbows,
  hips, and face visible.
- **Window does not quit:** click the OpenCV window first, then press `Q` or `Esc`.
