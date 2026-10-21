"""
ml_gesture_classifier.py
────────────────────────
Production runtime inference engine for real-time ML Hand Gesture Recognition.
Features:
- Loads serialized champion model (gesture_model.joblib).
- Extracts invariant geometric hand features in < 0.1ms.
- High-speed batch/single-sample inference with sub-millisecond execution.
- Temporal probability smoothing (rolling buffer) to eliminate flicker.
- Sleek on-screen HUD visualization overlay (class badge + live confidence meter).
"""

import os
import time
from collections import deque
import numpy as np
import cv2
import joblib

from ml_feature_extractor import LandmarkFeatureExtractor, GESTURE_CLASSES


class MLGestureClassifier:
    """Real-time Machine Learning Hand Gesture Classifier."""

    def __init__(self, model_path="gesture_model.joblib", smooth_frames=4, conf_threshold=0.70):
        self.model_path = os.path.abspath(model_path)
        self.smooth_frames = smooth_frames
        self.conf_threshold = conf_threshold
        self.classes = GESTURE_CLASSES
        self.model = None
        self.is_ready = False
        self.last_latency_ms = 0.0

        # Temporal probability smoothing buffer
        self._prob_history = deque(maxlen=smooth_frames)

        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                if hasattr(self.model, "n_jobs"):
                    self.model.n_jobs = 1
                self.is_ready = True
                print(f"[MLGestureClassifier] Successfully loaded champion model from: {self.model_path}")
            except Exception as e:
                print(f"[MLGestureClassifier] Warning: Could not load model: {e}")
                self.is_ready = False
        else:
            print(f"[MLGestureClassifier] Notice: Model not yet found at: {self.model_path}")
            self.is_ready = False

    def predict(self, raw_landmarks):
        """
        Classifies hand gesture from 21 MediaPipe raw landmarks.
        Returns: (predicted_class_name, confidence_float, class_id, is_confident_bool)
        """
        if not self.is_ready or not raw_landmarks or len(raw_landmarks) < 21:
            return "Neutral", 0.0, 0, False

        t0 = time.perf_counter()

        # 1. Feature extraction
        feats = LandmarkFeatureExtractor.extract_from_raw_landmarks(raw_landmarks)
        X = feats.reshape(1, -1)

        # 2. Probability prediction
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(X)[0]
        else:
            probs = np.zeros(len(self.classes), dtype=np.float32)
            pred_id = int(self.model.predict(X)[0])
            probs[pred_id] = 1.0

        # 3. Temporal smoothing
        self._prob_history.append(probs)
        smoothed_probs = np.mean(self._prob_history, axis=0)

        best_id = int(np.argmax(smoothed_probs))
        confidence = float(smoothed_probs[best_id])
        class_name = self.classes[best_id] if best_id < len(self.classes) else "Unknown"

        self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
        is_confident = confidence >= self.conf_threshold

        return class_name, confidence, best_id, is_confident

    def draw_hud(self, frame, class_name, confidence, is_confident, top_left=None):
        """
        Renders a sleek, modern, cyberpunk-styled ML HUD on the OpenCV camera frame.
        """
        w, h = 260, 68
        if top_left is None:
            frame_h, frame_w = frame.shape[:2]
            x = max(10, frame_w - w - 16)
            y = 70
        else:
            x, y = top_left

        # Semi-transparent dark card background
        sub_img = frame[y:y+h, x:x+w]
        if sub_img.shape[0] == h and sub_img.shape[1] == w:
            card = np.full_like(sub_img, 20)
            cv2.addWeighted(card, 0.75, sub_img, 0.25, 0, sub_img)
            frame[y:y+h, x:x+w] = sub_img

        # Card border
        border_color = (0, 242, 254) if is_confident else (100, 116, 139)  # Cyan or Gray
        cv2.rectangle(frame, (x, y), (x+w, y+h), border_color, 1, cv2.LINE_AA)

        # Title: ML Classifier & Latency
        title_text = f"AI GESTURE MODEL [{self.last_latency_ms:.1f}ms]"
        cv2.putText(frame, title_text, (x + 10, y + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (148, 163, 184), 1, cv2.LINE_AA)

        # Gesture Name
        status_color = (0, 255, 128) if is_confident else (148, 163, 184)
        cv2.putText(frame, class_name, (x + 10, y + 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_color, 2, cv2.LINE_AA)

        # Confidence percentage
        conf_str = f"{confidence * 100:.0f}%"
        cv2.putText(frame, conf_str, (x + w - 48, y + 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 1, cv2.LINE_AA)

        # Progress bar
        bar_x = x + 10
        bar_y = y + 52
        bar_w = w - 20
        bar_h = 7

        # Background track
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h),
                      (45, 55, 72), -1, cv2.LINE_AA)

        # Fill track
        fill_w = int(bar_w * min(1.0, max(0.0, confidence)))
        fill_color = (0, 242, 254) if is_confident else (75, 85, 99)
        if fill_w > 0:
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h),
                          fill_color, -1, cv2.LINE_AA)

        return frame
