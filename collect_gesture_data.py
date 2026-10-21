"""
Interactive Webcam Gesture Data Collector
==========================================
Collect custom real-world hand gesture training data directly from your webcam.
Saves extracted 78-dimensional geometric features into 'gesture_dataset_custom.csv'.

Key Controls:
  [0-8] : Select active label to record:
          0: NONE / RELAXED
          1: INDEX_POINT
          2: V_SIGN
          3: OPEN_PALM
          4: FIST
          5: OK_GESTURE
          6: ROCK_HORNS
          7: THUMBS_UP
          8: PINCH
  [SPACE]: Record a single sample
  [B]    : Record a burst of 50 samples (with 2-second prep delay)
  [S]    : Save dataset to 'gesture_dataset_custom.csv'
  [Q]    : Quit
"""

import cv2
import numpy as np
import time
import os
import csv
from gesture_detector import GestureDetector
from ml_feature_extractor import extract_ml_features, FEATURE_NAMES

LABEL_MAP = {
    0: "NONE",
    1: "INDEX_POINT",
    2: "V_SIGN",
    3: "OPEN_PALM",
    4: "FIST",
    5: "OK_GESTURE",
    6: "ROCK_HORNS",
    7: "THUMBS_UP",
    8: "PINCH",
}

OUTPUT_CSV = "gesture_dataset_custom.csv"

def main():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    detector = GestureDetector(max_hands=1, detection_con=0.75, tracking_con=0.75, enable_ml=False)

    samples = []  # list of [label_id, label_name, feat_0, feat_1, ...]
    current_label = 0
    burst_countdown = 0
    burst_samples_left = 0

    print("=" * 60)
    print("  GESTURE DATA COLLECTOR INITIALIZED")
    print("  Hold hand in frame, select label (0-8), press SPACE or 'B'")
    print("=" * 60)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        frame = detector.process(frame, draw=True)
        lm_list = detector.lm_list

        # Handle burst capture
        if burst_countdown > 0:
            burst_countdown -= 1
            cv2.putText(frame, f"GET READY: {burst_countdown // 10 + 1}", (w // 2 - 120, h // 2),
                        cv2.FONT_HERSHEY_DUPLEX, 1.8, (0, 0, 255), 3)
        elif burst_samples_left > 0:
            if lm_list:
                feats = extract_ml_features(lm_list)
                if feats is not None:
                    samples.append([current_label, LABEL_MAP[current_label]] + feats.tolist())
                    burst_samples_left -= 1
                    cv2.putText(frame, f"RECORDING... ({50 - burst_samples_left}/50)",
                                (w // 2 - 160, h // 2),
                                cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "HAND LOST! Bring hand back into frame",
                            (w // 2 - 250, h // 2), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 165, 255), 2)

        # HUD Overlay
        cv2.rectangle(frame, (10, 10), (450, 140), (20, 20, 20), -1)
        cv2.rectangle(frame, (10, 10), (450, 140), (0, 255, 180), 2)

        cur_name = LABEL_MAP.get(current_label, "UNKNOWN")
        cv2.putText(frame, f"Active Label: [{current_label}] {cur_name}", (25, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, f"Total Samples Collected: {len(samples)}", (25, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # Breakdown by label
        counts = {i: 0 for i in LABEL_MAP}
        for s in samples:
            counts[s[0]] = counts.get(s[0], 0) + 1
        cnt_str = " | ".join([f"{k}:{counts[k]}" for k in sorted(counts.keys())])
        cv2.putText(frame, cnt_str, (25, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)

        # Instructions
        cv2.putText(frame, "[0-8] Select Label | [SPACE] Single | [B] Burst 50 | [S] Save | [Q] Quit",
                    (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 2)

        cv2.imshow("Gesture Data Collector", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q') or key == 27:
            break
        elif ord('0') <= key <= ord('8'):
            current_label = key - ord('0')
            print(f">> Selected label: [{current_label}] {LABEL_MAP[current_label]}")
        elif key == 32:  # SPACE bar
            if lm_list:
                feats = extract_ml_features(lm_list)
                if feats is not None:
                    samples.append([current_label, LABEL_MAP[current_label]] + feats.tolist())
                    print(f"Captured single sample for [{current_label}] {LABEL_MAP[current_label]} (Total: {len(samples)})")
            else:
                print("No hand detected to capture!")
        elif key == ord('b'):
            burst_countdown = 30  # ~1 second delay at 30 fps
            burst_samples_left = 50
            print(f"Starting burst of 50 samples for [{current_label}] {LABEL_MAP[current_label]}...")
        elif key == ord('s'):
            if samples:
                header = ["label_id", "label_name"] + FEATURE_NAMES
                with open(OUTPUT_CSV, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    writer.writerows(samples)
                print(f" Successfully saved {len(samples)} samples to '{OUTPUT_CSV}'!")
            else:
                print("No samples to save.")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
