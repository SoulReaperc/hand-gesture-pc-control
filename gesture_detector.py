"""
gesture_detector.py
───────────────────
Hand-landmark detection using MediaPipe Tasks API (v1.0+).
Uses HandLandmarker with the bundled hand_landmarker.task model.

Hand Landmark indices (MediaPipe):
  0  = Wrist
  4  = Thumb tip
  8  = Index tip
  12 = Middle tip
  16 = Ring tip
  20 = Pinky tip
"""

import cv2
import math
import time
import os
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import (
    HandLandmarker, HandLandmarkerOptions, HandLandmarksConnections
)
from mediapipe.tasks.python.vision import RunningMode
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import drawing_utils, drawing_styles

# Path to the model file (must sit next to this script, or set env var)
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")

# MediaPipe drawing connections for hands
_HAND_CONNECTIONS = HandLandmarksConnections.HAND_CONNECTIONS


class GestureDetector:
    """Wraps MediaPipe HandLandmarker (Tasks API v1.0+) with helper utilities."""

    TIP_IDS = [4, 8, 12, 16, 20]   # thumb, index, middle, ring, pinky tips
    PIP_IDS = [3, 6, 10, 14, 18]   # corresponding second joints

    def __init__(self, max_hands=1, detection_con=0.7, tracking_con=0.7):
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(
                f"[GestureDetector] Model not found: {_MODEL_PATH}\n"
                "Download from:\n"
                "  https://storage.googleapis.com/mediapipe-models/"
                "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            )

        opts = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_MODEL_PATH),
            running_mode=RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=detection_con,
            min_hand_presence_confidence=detection_con,
            min_tracking_confidence=tracking_con,
        )
        self._landmarker = HandLandmarker.create_from_options(opts)

        self.lm_list    = []       # [(id, px, py), ...] for primary hand
        self._raw_landmarks = []   # raw normalized landmarks
        self.hand_type  = "Unknown"
        self._prev_time = 0
        self.fps        = 0
        self._frame_ts  = 0        # frame timestamp in ms for VIDEO mode

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def process(self, frame, draw=True):
        """
        Detect hands in *frame* (BGR).
        Returns annotated frame; updates self.lm_list & self.hand_type.
        """
        h, w = frame.shape[:2]

        # Convert BGR → RGB MediaPipe Image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # VIDEO mode requires monotonically increasing timestamps (ms)
        self._frame_ts += 33          # ~30 fps
        result = self._landmarker.detect_for_video(mp_image, self._frame_ts)

        self.lm_list   = []
        self._raw_landmarks = []
        self.hand_type = "Unknown"

        if result.hand_landmarks:
            # ── Draw all hands ─────────────────────────────────────
            if draw:
                for hand_lms in result.hand_landmarks:
                    self._draw_hand(frame, hand_lms, w, h)

            # ── Primary hand landmarks (pixel coords) ───────────────
            primary_lms = result.hand_landmarks[0]
            self._raw_landmarks = primary_lms
            for lm_id, lm in enumerate(primary_lms):
                px, py = int(lm.x * w), int(lm.y * h)
                self.lm_list.append((lm_id, px, py))

            # ── Hand type ───────────────────────────────────────────
            if result.handedness:
                label = result.handedness[0][0].display_name  # "Left" / "Right"
                # Flip because camera is mirrored
                self.hand_type = "Right" if label == "Left" else "Left"

        # FPS
        cur = time.time()
        self.fps = 1 / (cur - self._prev_time + 1e-9)
        self._prev_time = cur

        return frame

    def is_fully_visible(self, margin=0.015) -> bool:
        """
        Check if all hand landmarks are fully within frame borders
        (with specified margin fraction from frame edges).
        Returns False if hand is missing or touching/partially cut off by frame edges.
        """
        if not self.lm_list or not self._raw_landmarks:
            return False
        for lm in self._raw_landmarks:
            if lm.x < margin or lm.x > (1.0 - margin) or lm.y < margin or lm.y > (1.0 - margin):
                return False
        return True

    def get_palm_size(self) -> float:
        """
        Returns pixel distance between Wrist (lm 0) and Middle MCP (lm 9).
        Serves as a dynamic hand scale reference for distance-invariant gestures.
        """
        if not self.lm_list or len(self.lm_list) < 21:
            return 100.0   # default fallback
        wx, wy = self.lm_list[0][1], self.lm_list[0][2]
        mx, my = self.lm_list[9][1], self.lm_list[9][2]
        return max(10.0, math.hypot(mx - wx, my - wy))

    def is_palm_facing(self) -> bool:
        """
        Returns True if the PALM of the hand is facing the camera,
        False if the BACK of the hand is facing the camera.
        Uses 2D cross-product of (Wrist->Index_MCP) x (Wrist->Pinky_MCP).
        """
        if not self.lm_list or len(self.lm_list) < 21:
            return False

        # Wrist (0), Index MCP (5), Pinky MCP (17)
        x0, y0 = self.lm_list[0][1],  self.lm_list[0][2]
        x5, y5 = self.lm_list[5][1],  self.lm_list[5][2]
        x17, y17 = self.lm_list[17][1], self.lm_list[17][2]

        dx1, dy1 = x5 - x0, y5 - y0
        dx2, dy2 = x17 - x0, y17 - y0

        cross = dx1 * dy2 - dy1 * dx2

        # In OpenCV mirrored view:
        # Right hand: Palm facing -> cross > 0
        # Left hand: Palm facing -> cross < 0
        if self.hand_type == "Right":
            return cross > 0
        else:
            return cross < 0

    def fingers_up(self):
        """
        Return list of 5 booleans [thumb, index, middle, ring, pinky].
        True = finger extended / up.
        """
        if not self.lm_list or len(self.lm_list) < 21:
            return [False] * 5

        fingers = []

        # Wrist coords
        wx, wy = self.lm_list[0][1], self.lm_list[0][2]

        # Thumb: compare x-coord (depends on hand side) AND tip distance from wrist vs MCP distance
        t_tip_x, t_tip_y = self.lm_list[4][1], self.lm_list[4][2]
        t_ip_x           = self.lm_list[3][1]
        t_mcp_x, t_mcp_y = self.lm_list[2][1], self.lm_list[2][2]

        t_tip_dist = math.hypot(t_tip_x - wx, t_tip_y - wy)
        t_mcp_dist = math.hypot(t_mcp_x - wx, t_mcp_y - wy)

        if self.hand_type == "Right":
            thumb_open = (t_tip_x < t_ip_x) and (t_tip_dist > t_mcp_dist * 1.15)
        else:
            thumb_open = (t_tip_x > t_ip_x) and (t_tip_dist > t_mcp_dist * 1.15)
        fingers.append(thumb_open)

        # Four fingers: tip y < pip y AND tip y < mcp y AND tip dist > mcp dist * 1.30 & pip dist * 1.10
        mcp_ids = [5, 9, 13, 17]
        for tip, pip, mcp in zip(self.TIP_IDS[1:], self.PIP_IDS[1:], mcp_ids):
            tip_x, tip_y = self.lm_list[tip][1], self.lm_list[tip][2]
            pip_x, pip_y = self.lm_list[pip][1], self.lm_list[pip][2]
            mcp_x, mcp_y = self.lm_list[mcp][1], self.lm_list[mcp][2]

            tip_dist = math.hypot(tip_x - wx, tip_y - wy)
            pip_dist = math.hypot(pip_x - wx, pip_y - wy)
            mcp_dist = math.hypot(mcp_x - wx, mcp_y - wy)

            # Finger is extended ONLY if tip is above pip, tip is above mcp, and clearly extended relative to MCP/PIP
            is_up = (tip_y < pip_y) and (tip_y < mcp_y) and (tip_dist > mcp_dist * 1.30) and (tip_dist > pip_dist * 1.10)
            fingers.append(is_up)

        return fingers  # [thumb, index, middle, ring, pinky]

    def distance(self, id1, id2, frame=None, draw=True, r=8, t=2):
        """
        Euclidean pixel distance between landmark id1 and id2.
        Returns (dist, frame, [x1, y1, x2, y2, cx, cy]).
        """
        if not self.lm_list:
            return 0, frame, []

        _, x1, y1 = self.lm_list[id1]
        _, x2, y2 = self.lm_list[id2]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        if frame is not None and draw:
            cv2.line(frame, (x1, y1), (x2, y2), (255, 165, 0), t)
            cv2.circle(frame, (x1, y1), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(frame, (x2, y2), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(frame, (cx, cy), r // 2, (0, 255, 0), cv2.FILLED)

        dist = math.hypot(x2 - x1, y2 - y1)
        return dist, frame, [x1, y1, x2, y2, cx, cy]

    def landmark(self, lm_id):
        """Return (x, y) pixel coords of landmark lm_id or None."""
        if not self.lm_list or lm_id >= len(self.lm_list):
            return None
        return self.lm_list[lm_id][1], self.lm_list[lm_id][2]

    def num_hands_detected(self):
        return 1 if self.lm_list else 0

    def get_gesture_name(self, fingers):
        """Map finger-state list → human-readable gesture name."""
        if self.is_claw():
            return "Claw"
        combos = {
            (0, 0, 0, 0, 0): "Fist",
            (1, 1, 1, 1, 1): "Open Hand",
            (0, 1, 0, 0, 0): "Index Pointer",
            (0, 1, 1, 0, 0): "Peace / V",
            (0, 1, 1, 1, 0): "Three Fingers",
            (0, 1, 1, 1, 1): "Four Fingers",
            (1, 0, 0, 0, 0): "Thumb Up",
            (1, 0, 0, 0, 1): "Rock On",
            (0, 0, 0, 0, 1): "Pinky Up",
            (0, 1, 0, 0, 1): "Call Me",
            (1, 1, 0, 0, 0): "Thumb + Index",
        }
        return combos.get(tuple(int(x) for x in fingers), "Custom Gesture")

    def is_claw(self) -> bool:
        """
        Detect a 'claw' hand shape:
          - All four fingers are bent (tip_y > pip_y  →  fingers_up = False)
          - But fingertips are NOT pressed to the palm (unlike a tight fist)
        """
        if len(self.lm_list) < 21:
            return False
        fingers = self.fingers_up()
        if any(fingers[1:]):          # index/middle/ring/pinky should all be down
            return False
        palm_size = self.get_palm_size()
        wx, wy = self.lm_list[0][1], self.lm_list[0][2]
        tx, ty = self.lm_list[8][1], self.lm_list[8][2]
        dist = math.hypot(tx - wx, ty - wy)
        return (0.55 * palm_size) < dist < (1.45 * palm_size)

    def draw_fps(self, frame):
        cv2.putText(frame, f"FPS: {int(self.fps)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return frame

    # ──────────────────────────────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────────────────────────────

    def _draw_hand(self, frame, hand_lms, w, h):
        """Draw landmarks and connections on frame."""
        pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lms]

        # Draw connections
        for conn in _HAND_CONNECTIONS:
            start, end = conn.start, conn.end
            if start < len(pts) and end < len(pts):
                cv2.line(frame, pts[start], pts[end], (80, 80, 220), 2)

        # Draw landmark dots
        for i, (px, py) in enumerate(pts):
            r = 8 if i in self.TIP_IDS else 5
            col = (0, 200, 255) if i in self.TIP_IDS else (200, 200, 200)
            cv2.circle(frame, (px, py), r, col, cv2.FILLED)
            cv2.circle(frame, (px, py), r, (0, 0, 0), 1)
