"""MediaPipe Hand Landmarker wrapper for hand tracking."""

import cv2
import mediapipe as mp
import numpy as np


class HandTracker:
    """Tracks hands in video frames using MediaPipe Hands."""

    def __init__(self, max_num_hands: int = 2, min_detection_confidence: float = 0.5):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=0.3,
        )

    def process(self, frame_bgr: np.ndarray):
        """
        Process a BGR frame. Returns list of dicts with 'landmarks', 'handedness'.
        landmarks: list of (x, y, z) for 21 hand landmarks (normalized 0-1, z relative)
        handedness: 'Left' or 'Right'
        """
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)

        hands_data = []
        if results.multi_hand_landmarks and results.multi_handedness:
            for hand_landmarks, handedness in zip(
                results.multi_hand_landmarks, results.multi_handedness
            ):
                landmarks = [
                    (lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark
                ]
                hand_label = handedness.classification[0].label  # 'Left' or 'Right'
                hands_data.append({
                    "landmarks": landmarks,
                    "handedness": hand_label,
                })
        return hands_data

    def close(self):
        """Release resources."""
        self.hands.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
