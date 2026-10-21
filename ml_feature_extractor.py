"""
ml_feature_extractor.py
───────────────────────
High-performance geometric feature extractor for Hand Landmark vectors.
Converts 21 MediaPipe hand landmarks into an invariant 78-dimensional feature vector:
1. Wrist-centered coordinates (normalized by dynamic palm scale) -> 63 features
2. Fingertip-to-wrist and fingertip-to-fingertip distance ratios -> 10 features
3. Inter-joint bending angles (MCP-PIP-DIP/TIP) -> 5 features

Features are strictly translation-invariant and scale-invariant, ensuring robust
generalization regardless of camera distance or hand position in the video frame.
"""

import math
import numpy as np


GESTURE_CLASSES = [
    "Neutral",          # 0: Relaxed hand or transition
    "Index Point",      # 1: Index finger up (mouse cursor movement)
    "Pinch Click",      # 2: Index + Middle pinch or Index + Thumb (left click)
    "Thumb Pinch",      # 3: Thumb + Index tip pinch (right click)
    "Three Fin Scroll", # 4: Index, Middle, Ring up (vertical scroll)
    "Open Spread",      # 5: All 5 fingers extended wide (rotary volume / slideshow)
    "Fist Hold",        # 6: All fingers folded (mute toggle / stop slideshow)
    "Horns Rock",       # 7: Index + Pinky up (Spotify play/pause)
    "Peace Two Fin",    # 8: Index + Middle up (PowerPoint slide navigation)
]


class LandmarkFeatureExtractor:
    """Extracts invariant features from 21 MediaPipe 3D hand landmarks."""

    NUM_FEATURES = 78
    FEATURE_NAMES = None  # Lazily populated

    @classmethod
    def _get_feature_names(cls):
        if cls.FEATURE_NAMES is not None:
            return cls.FEATURE_NAMES
        names = []
        # 63 wrist-relative normalized coords
        for i in range(21):
            names.extend([f"lm_{i}_norm_x", f"lm_{i}_norm_y", f"lm_{i}_norm_z"])
        # 10 key distance ratios
        names.extend([
            "dist_thumb_index",
            "dist_index_middle",
            "dist_middle_ring",
            "dist_ring_pinky",
            "dist_thumb_pinky_spread",
            "dist_thumb_wrist",
            "dist_index_wrist",
            "dist_middle_wrist",
            "dist_ring_wrist",
            "dist_pinky_wrist",
        ])
        # 5 joint flexion angles
        names.extend([
            "angle_thumb_flex",
            "angle_index_flex",
            "angle_middle_flex",
            "angle_ring_flex",
            "angle_pinky_flex",
        ])
        cls.FEATURE_NAMES = names
        return names

    @staticmethod
    def extract_from_raw_landmarks(raw_landmarks) -> np.ndarray:
        """
        Extract features from a list of 21 MediaPipe NormalizedLandmark objects.
        Returns a 1D float32 numpy array of shape (78,).
        """
        if not raw_landmarks or len(raw_landmarks) < 21:
            return np.zeros(78, dtype=np.float32)

        # Convert to numpy array (21, 3)
        coords = np.empty((21, 3), dtype=np.float32)
        for i, lm in enumerate(raw_landmarks[:21]):
            coords[i, 0] = lm.x
            coords[i, 1] = lm.y
            coords[i, 2] = getattr(lm, 'z', 0.0)

        return LandmarkFeatureExtractor.extract_from_coords(coords)

    @staticmethod
    def extract_from_pixel_list(lm_list, img_w=1280, img_h=720) -> np.ndarray:
        """
        Extract features from a list of [(id, px, py), ...] landmarks.
        """
        if not lm_list or len(lm_list) < 21:
            return np.zeros(78, dtype=np.float32)

        coords = np.empty((21, 3), dtype=np.float32)
        for item in lm_list[:21]:
            lm_id, px, py = item[0], item[1], item[2]
            coords[lm_id, 0] = px / float(img_w)
            coords[lm_id, 1] = py / float(img_h)
            coords[lm_id, 2] = 0.0

        return LandmarkFeatureExtractor.extract_from_coords(coords)

    @staticmethod
    def extract_from_coords(coords: np.ndarray) -> np.ndarray:
        """
        Vectorized extraction given (21, 3) coordinate array.
        """
        # 1. Wrist-relative centering
        wrist = coords[0]
        rel_coords = coords - wrist  # (21, 3), wrist is now [0, 0, 0]

        # 2. Dynamic palm scale normalization
        # Distance between Wrist (0) and Middle MCP (9)
        palm_vec = coords[9] - coords[0]
        palm_dist = float(np.linalg.norm(palm_vec))
        if palm_dist < 1e-4:
            palm_dist = 1.0

        scale_factor = 1.0 / palm_dist
        normalized_coords = rel_coords * scale_factor  # shape (21, 3)

        # Flatten 63 normalized coordinates
        feat_coords = normalized_coords.flatten()

        # 3. Key Distance Ratios (normalized by palm distance)
        def dist_norm(idx1, idx2):
            return float(np.linalg.norm(coords[idx1] - coords[idx2])) * scale_factor

        feat_distances = np.array([
            dist_norm(4, 8),    # Thumb tip to Index tip
            dist_norm(8, 12),   # Index tip to Middle tip
            dist_norm(12, 16),  # Middle tip to Ring tip
            dist_norm(16, 20),  # Ring tip to Pinky tip
            dist_norm(4, 20),   # Thumb tip to Pinky tip (spread)
            dist_norm(4, 0),    # Thumb tip to Wrist
            dist_norm(8, 0),    # Index tip to Wrist
            dist_norm(12, 0),   # Middle tip to Wrist
            dist_norm(16, 0),   # Ring tip to Wrist
            dist_norm(20, 0),   # Pinky tip to Wrist
        ], dtype=np.float32)

        # 4. Joint Flexion Angles (cosine angle between MCP-PIP and PIP-TIP)
        def joint_angle(mcp, pip, tip):
            v1 = coords[pip] - coords[mcp]
            v2 = coords[tip] - coords[pip]
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 < 1e-6 or norm2 < 1e-6:
                return 0.0
            cos_a = np.dot(v1, v2) / (norm1 * norm2)
            cos_a = np.clip(cos_a, -1.0, 1.0)
            return float(math.acos(cos_a))  # In radians [0, pi]

        feat_angles = np.array([
            joint_angle(2, 3, 4),    # Thumb
            joint_angle(5, 6, 8),    # Index
            joint_angle(9, 10, 12),  # Middle
            joint_angle(13, 14, 16), # Ring
            joint_angle(17, 18, 20), # Pinky
        ], dtype=np.float32)

        features = np.concatenate([feat_coords, feat_distances, feat_angles])
        return features


FEATURE_NAMES = LandmarkFeatureExtractor._get_feature_names()


def extract_ml_features(lm_list, img_w=1280, img_h=720) -> np.ndarray:
    """Convenience wrapper to extract 78 features from pixel landmark list or coords."""
    if lm_list is None or len(lm_list) < 21:
        return np.zeros(78, dtype=np.float32)

    # Check if format is [[id, x, y, z], ...] or [(id, x, y), ...]
    first = lm_list[0]
    if isinstance(first, (list, tuple)) and len(first) >= 3:
        if len(first) == 4:
            # Contains z coordinate
            coords = np.empty((21, 3), dtype=np.float32)
            for item in lm_list[:21]:
                lm_id = int(item[0])
                coords[lm_id, 0] = float(item[1]) / float(img_w)
                coords[lm_id, 1] = float(item[2]) / float(img_h)
                coords[lm_id, 2] = float(item[3]) / float(img_w)
            return LandmarkFeatureExtractor.extract_from_coords(coords)
        else:
            return LandmarkFeatureExtractor.extract_from_pixel_list(lm_list, img_w=img_w, img_h=img_h)
    elif isinstance(first, (int, float)):
        # Already flattened or array
        arr = np.array(lm_list, dtype=np.float32)
        if arr.shape == (21, 3):
            return LandmarkFeatureExtractor.extract_from_coords(arr)
    return np.zeros(78, dtype=np.float32)
