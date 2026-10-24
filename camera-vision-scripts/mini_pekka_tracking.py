"""Mini Pekka: ESP32 video plus body-tracking preview on your laptop.

Put pose_landmarker_lite.task beside this file. Download it from:
https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task

Run with the same Python environment as your working camera test.
Requires mediapipe and OpenCV. An optional servo ESP32 receives head-angle commands.
"""

import argparse
import math
import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import cv2
import mediapipe as mp


MODEL_PATH = Path(__file__).with_name("pose_landmarker_lite.task")
MIN_VISIBILITY = 0.6
SMOOTHING = 0.25  # Larger values respond faster; smaller values smooth more.
SERVO_UPDATE_INTERVAL = 0.25
SERVO_MIN_CHANGE = 2
SERVO_MIN_ANGLE = 0
SERVO_MAX_ANGLE = 180
SERVO_UDP_PORT = 4210
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


def normalize_camera_url(value):
    """Accept a board IP, board URL, or stream URL and return the MJPEG URL."""
    value = value.strip()
    if not value:
        raise SystemExit("No camera IP or URL entered.")
    if "://" not in value:
        value = f"http://{value}"

    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SystemExit("Enter an ESP32 IP or an http:// camera URL.")

    hostname = parsed.hostname
    if hostname is None:
        raise SystemExit("Enter a valid ESP32 IP or camera URL.")
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    return urlunsplit((parsed.scheme, f"{hostname}:81", "/stream", "", ""))


def servo_url_from_camera_url(camera_url):
    parsed = urlsplit(camera_url)
    hostname = parsed.hostname
    if hostname is None:
        raise SystemExit("Enter a valid ESP32 IP or camera URL.")
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    return urlunsplit((parsed.scheme, hostname, "", "", ""))


def stream_url_from_user():
    """Ask for the combined camera/servo ESP32 IP or any camera URL."""
    url = input(
        "ESP32 IP or stream URL (for example 192.168.x.x): "
    )
    return normalize_camera_url(url)


class ServoClient:
    def __init__(self, base_url):
        parsed = urlsplit(base_url)
        self.host = parsed.hostname
        if self.host is None:
            raise SystemExit("Invalid servo board URL.")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.pending_angle = None
        self.last_sent_angle = None
        self.last_error_at = 0.0
        self.condition = threading.Condition()
        self.running = True
        self.worker = threading.Thread(target=self._send_pending, daemon=True)
        self.worker.start()

    def send_angle(self, angle):
        with self.condition:
            if (
                self.pending_angle is not None
                and abs(angle - self.pending_angle) < SERVO_MIN_CHANGE
            ) or (
                self.last_sent_angle is not None
                and abs(angle - self.last_sent_angle) < SERVO_MIN_CHANGE
            ):
                return
            self.pending_angle = angle
            self.condition.notify()

    def _send_pending(self):
        while True:
            with self.condition:
                while self.running and self.pending_angle is None:
                    self.condition.wait()
                if not self.running:
                    return
                angle = self.pending_angle
                self.pending_angle = None

            try:
                self.socket.sendto(
                    f"{angle}\n".encode("ascii"),
                    (self.host, SERVO_UDP_PORT),
                )
            except OSError as error:
                now = time.monotonic()
                if now - self.last_error_at >= 2.0:
                    print(f"Servo UDP command failed ({self.host}:{SERVO_UDP_PORT}): {error}")
                    self.last_error_at = now
                continue

            with self.condition:
                self.last_sent_angle = angle
            time.sleep(SERVO_UPDATE_INTERVAL)

    def close(self):
        with self.condition:
            self.running = False
            self.condition.notify()
        self.worker.join(timeout=1.0)
        self.socket.close()


class LatestFrameCapture:
    """Read the network stream continuously while the detector processes frames."""

    def __init__(self, url):
        self.capture = cv2.VideoCapture(url)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame = None
        self.lock = threading.Lock()
        self.running = self.capture.isOpened()
        self.thread = threading.Thread(target=self._read_frames, daemon=True)
        if self.running:
            self.thread.start()

    def _read_frames(self):
        while self.running:
            success, frame = self.capture.read()
            if not success or frame is None:
                self.running = False
                return
            with self.lock:
                self.frame = frame

    def isOpened(self):
        return self.capture.isOpened()

    def read(self):
        with self.lock:
            if self.frame is None:
                return False, None
            return True, self.frame.copy()

    def release(self):
        self.running = False
        self.capture.release()
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)


def head_angle_from_nose_x(nose_x):
    """Map image position to head angle; image-left is servo-right."""
    return round(
        SERVO_MAX_ANGLE
        - nose_x * (SERVO_MAX_ANGLE - SERVO_MIN_ANGLE)
    )


def main(camera_url, servo_url=None):
    camera_url = normalize_camera_url(camera_url)
    servo_url = servo_url or servo_url_from_camera_url(camera_url)
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
    print(f"Sending head commands to {servo_url}")
    servo = ServoClient(servo_url)
    cap = LatestFrameCapture(camera_url)
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
                    if not cap.running:
                        print("Camera stream stopped. Check the connection, then run again.")
                        break
                    time.sleep(0.001)
                    continue

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
                    head_angle = head_angle_from_nose_x(nose.x)
                    servo.send_angle(head_angle)
                    labels.append(f"Head servo: {head_angle} deg")
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
        servo.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Preview ESP32 camera body landmarks with MediaPipe."
        )
        parser.add_argument(
            "--camera-url",
            help="ESP32 IP or camera URL; :81/stream is added when needed",
        )
        parser.add_argument(
            "--servo-url",
            help="Optional separate servo ESP32 URL; defaults to the camera board",
        )
        args = parser.parse_args()
        main(args.camera_url or stream_url_from_user(), args.servo_url)
    except KeyboardInterrupt:
        print("\nTracking stopped.")
