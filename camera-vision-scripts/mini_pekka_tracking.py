"""Mini Pekka: ESP32 video plus body-tracking preview on your laptop.

Put pose_landmarker_lite.task beside this file. Download it from:
https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task

Run with the same Python environment as your working camera test.
Requires mediapipe and OpenCV. This preview does not send motor commands.
"""

import argparse
import math
import time
from pathlib import Path

import cv2
import mediapipe as mp


MODEL_PATH = Path(__file__).with_name("pose_landmarker_lite.task")
MIN_VISIBILITY = 0.6
SMOOTHING = 0.25  # Larger values respond faster; smaller values smooth more.
WINDOW = "Mini Pekka - body tracking (Q to quit)"

# Left/right refer to YOUR body, not the left/right sides of the picture.
# Each tuple contains the shoulder, elbow, wrist, and hip landmark numbers.
ARMS = {"Left": (11, 13, 15, 23), "Right": (12, 14, 16, 24)}
CONNECTIONS = (
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (0, 2), (0, 5), (2, 7), (5, 8),
)
POINT_IDS = sorted({index for pair in CONNECTIONS for index in pair})


def is_visible(landmark):
    """Skip uncertain or off-screen points instead of using stale estimates."""
    return (
        (landmark.visibility or 0.0) >= MIN_VISIBILITY
        and (landmark.presence or 0.0) >= MIN_VISIBILITY
        and 0.0 <= landmark.x <= 1.0
        and 0.0 <= landmark.y <= 1.0
    )


def arm_elevation(shoulder, elbow, hip, width, height):
    """Upper-arm angle relative to the torso, measured in the image plane.

    Approximately 0 degrees = down, 90 = sideways, 180 = overhead.
    This is a body measurement, not a calibrated motor position.
    """
    if not all(is_visible(point) for point in (shoulder, elbow, hip)):
        return None

    # Use pixels so a rectangular image does not distort the angle.
    arm_x = (elbow.x - shoulder.x) * width
    arm_y = (elbow.y - shoulder.y) * height
    torso_x = (hip.x - shoulder.x) * width
    torso_y = (hip.y - shoulder.y) * height
    denominator = math.hypot(arm_x, arm_y) * math.hypot(torso_x, torso_y)
    if denominator < 1e-6:
        return None

    cosine = (arm_x * torso_x + arm_y * torso_y) / denominator
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def draw_points(image, landmarks):
    height, width = image.shape[:2]
    points = {
        index: (int(landmarks[index].x * (width - 1)),
                int(landmarks[index].y * (height - 1)))
        for index in POINT_IDS if is_visible(landmarks[index])
    }
    for start, end in CONNECTIONS:
        if start in points and end in points:
            cv2.line(image, points[start], points[end], (0, 220, 0), 2)
    for index, point in points.items():
        color = (0, 255, 255) if index == 0 else (255, 80, 255)
        cv2.circle(image, point, 6 if index == 0 else 4, color, -1)


def stream_url_from_user():
    """Ask for the IP printed by the ESP32's most recent Serial Monitor run."""
    url = input(
        "ESP32 stream URL (for example http://192.168.x.x:81/stream): "
    ).strip()
    if not url:
        raise SystemExit("No stream URL entered.")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise SystemExit("Use a plain URL beginning with http://, not Markdown link formatting.")
    return url


def main(camera_url):
    if not MODEL_PATH.is_file():
        raise SystemExit(
            "Missing pose model. Save pose_landmarker_lite.task beside this script:\n"
            f"{MODEL_PATH}\nThe download URL is at the top of this file."
        )

    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    print(f"Connecting to {camera_url}")
    cap = cv2.VideoCapture(camera_url)
    try:
        if not cap.isOpened():
            raise SystemExit("Could not open the camera. Check its power, IP, and Wi-Fi.")

        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, 800, 700)
        smoothed = {side: None for side in ARMS}
        last_timestamp = -1
        start = time.monotonic()
        print("Stand facing the camera with your shoulders, elbows and hips visible.")
        print("Raise a straight arm sideways, then overhead. Click the window; Q quits.")

        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            while True:
                success, frame = cap.read()
                if not success or frame is None:
                    print("Camera stream stopped. Check the connection, then run again.")
                    break

                height, width = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp = max(last_timestamp + 1, int((time.monotonic() - start) * 1000))
                last_timestamp = timestamp
                result = detector.detect_for_video(image, timestamp)
                landmarks = result.pose_landmarks[0] if result.pose_landmarks else None

                # Enlarge only the display; model input keeps the camera's resolution.
                preview = cv2.resize(frame, (640, round(height * 640 / width)))
                labels = []
                if landmarks:
                    draw_points(preview, landmarks)

                for side, (shoulder, elbow, wrist, hip) in ARMS.items():
                    angle = arm_elevation(
                        landmarks[shoulder], landmarks[elbow], landmarks[hip], width, height
                    ) if landmarks else None

                    if angle is None:
                        smoothed[side] = None
                        labels.append(f"{side} upper arm: show shoulder, elbow and hip")
                    else:
                        previous = smoothed[side]
                        smoothed[side] = angle if previous is None else previous + SMOOTHING * (angle - previous)
                        labels.append(f"{side} upper arm: {smoothed[side]:.0f} deg")

                if landmarks and is_visible(landmarks[0]):
                    nose = landmarks[0]
                    labels.append(f"Nose position: x={nose.x:.2f}, y={nose.y:.2f} (image coordinates)")
                else:
                    labels.append("Face marker unavailable - face the camera")

                labels.append("0=arm down | 90=sideways | 180=overhead | Q=quit")
                panel_y = preview.shape[0]
                preview = cv2.copyMakeBorder(
                    preview, 0, 112, 0, 0, cv2.BORDER_CONSTANT, value=(20, 20, 20)
                )
                for row, label in enumerate(labels):
                    cv2.putText(preview, label, (12, panel_y + 23 + row * 27),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (240, 240, 240), 1, cv2.LINE_AA)

                cv2.imshow(WINDOW, preview)
                if (cv2.waitKey(1) & 0xFF) in (ord("q"), ord("Q"), 27):
                    break
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Preview ESP32 camera body landmarks with MediaPipe."
        )
        parser.add_argument(
            "--camera-url",
            help="Current ESP32 stream URL, for example http://192.168.x.x:81/stream",
        )
        args = parser.parse_args()
        main(args.camera_url or stream_url_from_user())
    except KeyboardInterrupt:
        print("\nTracking stopped.")
