"""
Punch detection: closed fist + fast motion toward camera.
Emits events to a thread-safe queue.
"""

import collections
import math
import threading
import time
from typing import Optional

import cv2
import numpy as np

from cv.camera import Camera
from cv.hand_tracker import HandTracker


# Landmark indices (MediaPipe Hands)
WRIST = 0
MIDDLE_FINGER_MCP = 9
INDEX_TIP = 8
INDEX_PIP = 6
MIDDLE_TIP = 12
MIDDLE_PIP = 10
RING_TIP = 16
RING_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18
THUMB_TIP = 4
THUMB_IP = 3
THUMB_MCP = 2

# Smoothing: EMA alpha (higher = more responsive, lower = smoother)
LANDMARK_SMOOTH_ALPHA = 0.35


def _smooth_landmarks(
    hands_data: list,
    prev_smoothed: dict,
) -> tuple[list, dict]:
    """Apply EMA smoothing to landmarks. Returns (smoothed_hands_data, updated_prev)."""
    result = []
    new_prev = {}
    seen = set()
    for hd in hands_data:
        handedness = hd["handedness"].lower()
        seen.add(handedness)
        landmarks = hd["landmarks"]
        prev = prev_smoothed.get(handedness)
        smoothed = []
        for i, lm in enumerate(landmarks):
            x, y, z = lm[0], lm[1], lm[2]
            if prev and i < len(prev):
                px, py, pz = prev[i]
                x = LANDMARK_SMOOTH_ALPHA * x + (1 - LANDMARK_SMOOTH_ALPHA) * px
                y = LANDMARK_SMOOTH_ALPHA * y + (1 - LANDMARK_SMOOTH_ALPHA) * py
                z = LANDMARK_SMOOTH_ALPHA * z + (1 - LANDMARK_SMOOTH_ALPHA) * pz
            smoothed.append((x, y, z))
        new_prev[handedness] = smoothed
        result.append({"landmarks": smoothed, "handedness": hd["handedness"]})
    # Drop prev for hands no longer visible
    return result, {k: v for k, v in new_prev.items() if k in seen}


def _is_fist(landmarks: list) -> bool:
    """Check if hand landmarks indicate a closed fist."""
    # Fingers curled: fingertip y is closer to wrist than PIP (for fingers pointing down)
    # Or fingertip is closer to palm (check distances)
    try:
        thumb_tip = landmarks[THUMB_TIP]
        thumb_mcp = landmarks[THUMB_MCP]
        index_tip = landmarks[INDEX_TIP]
        index_pip = landmarks[INDEX_PIP]
        middle_tip = landmarks[MIDDLE_TIP]
        middle_pip = landmarks[MIDDLE_PIP]
        ring_tip = landmarks[RING_TIP]
        ring_pip = landmarks[RING_PIP]
        pinky_tip = landmarks[PINKY_TIP]
        pinky_pip = landmarks[PINKY_PIP]

        # Fist: fingertips are close to palm (low z or small extent)
        # Simpler: check that fingertips are "below" (higher y in image) their PIPs for curled fingers
        # Or: distance from tips to wrist is small relative to hand size
        wrist = landmarks[WRIST]
        hand_span = math.sqrt(
            (thumb_tip[0] - pinky_tip[0]) ** 2 + (thumb_tip[1] - pinky_tip[1]) ** 2
        )
        if hand_span < 0.05:
            return False

        # Fingers curled: tip-to-wrist distance < pip-to-wrist for each finger
        def tip_closer_than_pip(tip, pip):
            d_tip = (tip[0] - wrist[0]) ** 2 + (tip[1] - wrist[1]) ** 2
            d_pip = (pip[0] - wrist[0]) ** 2 + (pip[1] - wrist[1]) ** 2
            return d_tip <= d_pip * 1.3  # tip closer or similar = curled

        fingers_curled = (
            tip_closer_than_pip(index_tip, index_pip)
            and tip_closer_than_pip(middle_tip, middle_pip)
            and tip_closer_than_pip(ring_tip, ring_pip)
            and tip_closer_than_pip(pinky_tip, pinky_pip)
        )
        return fingers_curled
    except (IndexError, KeyError):
        return False


def _hand_size(landmarks: list) -> float:
    """Approximate hand size (bounding box diagonal) for motion-toward-camera detection."""
    xs = [lm[0] for lm in landmarks]
    ys = [lm[1] for lm in landmarks]
    return math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2)


def _avg_z(landmarks: list) -> float:
    """Average z of landmarks (smaller = closer to camera)."""
    return sum(lm[2] for lm in landmarks) / len(landmarks)


class PunchDetector:
    """Detects punches from hand tracking and puts events into a queue."""

    def __init__(
        self,
        event_queue,
        velocity_threshold: float = 0.15,
        cooldown_ms: float = 300,
        history_frames: int = 5,
    ):
        self.event_queue = event_queue
        self.velocity_threshold = velocity_threshold
        self.cooldown_sec = cooldown_ms / 1000.0
        self.history_frames = history_frames
        self._history: dict[str, collections.deque] = {}  # hand_id -> deque of (t, size, z)
        self._last_punch: dict[str, float] = {}  # hand_id -> timestamp
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _hand_id(self, handedness: str) -> str:
        return handedness.lower()

    def _update_and_detect(self, handedness: str, landmarks: list, t: float):
        """Update history and check for punch. Toward camera = increasing size or decreasing z."""
        hid = self._hand_id(handedness)
        if hid not in self._history:
            self._history[hid] = collections.deque(maxlen=self.history_frames)
        h = self._history[hid]

        size = _hand_size(landmarks)
        z = _avg_z(landmarks)
        h.append((t, size, z))

        if not _is_fist(landmarks):
            return
        if t - self._last_punch.get(hid, -10) < self.cooldown_sec:
            return
        if len(h) < 2:
            return

        # Motion toward camera: size increasing (hand getting bigger) or z decreasing
        (t0, s0, z0) = h[0]
        (t1, s1, z1) = h[-1]
        dt = t1 - t0
        if dt <= 0:
            return

        size_velocity = (s1 - s0) / dt
        z_velocity = (z1 - z0) / dt  # negative z_velocity = moving toward camera

        # Punch = moving toward camera (negative z or increasing size)
        toward_camera = (size_velocity > self.velocity_threshold) or (
            z_velocity < -0.35
        )
        if toward_camera:
            strength = min(1.0, abs(size_velocity) / (self.velocity_threshold * 2))
            self._last_punch[hid] = t
            self.event_queue.put(
                {"type": "punch", "hand": hid, "strength": strength}
            )

    def process_hands(self, hands_data: list, timestamp: float):
        """Process hand data from tracker and emit punch events."""
        for h in hands_data:
            self._update_and_detect(
                h["handedness"], h["landmarks"], timestamp
            )


# Block: hands high threshold (looser = 0.50). Require both hands + guard pose.
BLOCK_Y_THRESHOLD = 0.50
BLOCK_MAX_WRIST_DISTANCE = 0.4  # max horizontal distance for "guard" pose


def _compute_hand_state(hands_data: list) -> dict:
    """Compute dodge/block state from hand positions. Block = both hands high and near (guard)."""
    state = {"left_wrist": None, "right_wrist": None, "blocking": False, "dodging": None}
    for h in hands_data:
        landmarks = h["landmarks"]
        wrist = landmarks[WRIST]
        handedness = h["handedness"].lower()
        key = "left_wrist" if handedness == "left" else "right_wrist"
        state[key] = (wrist[0], wrist[1])
    left = state["left_wrist"]
    right = state["right_wrist"]
    # Blocking: require BOTH hands high and near each other (guard pose)
    if left and right:
        both_high = left[1] < BLOCK_Y_THRESHOLD and right[1] < BLOCK_Y_THRESHOLD
        wrist_dist = abs(left[0] - right[0])
        guard_pose = wrist_dist < BLOCK_MAX_WRIST_DISTANCE
        state["blocking"] = both_high and guard_pose
        avg_x = (left[0] + right[0]) / 2
        if avg_x < 0.35:
            state["dodging"] = "left"
        elif avg_x > 0.65:
            state["dodging"] = "right"
        else:
            state["dodging"] = None
    else:
        state["blocking"] = False
        if left:
            state["dodging"] = "left" if left[0] < 0.35 else ("right" if left[0] > 0.65 else None)
        elif right:
            state["dodging"] = "left" if right[0] < 0.35 else ("right" if right[0] > 0.65 else None)
    return state


def _draw_hand_landmarks(frame: np.ndarray, hands_data: list, blocking: bool = False) -> np.ndarray:
    """Draw dots at hand landmarks: blue when blocking, green otherwise."""
    h, w = frame.shape[:2]
    color = (255, 0, 0) if blocking else (0, 255, 0)  # BGR: blue or green
    for hd in hands_data:
        landmarks = hd["landmarks"]
        for lm in landmarks:
            x = int(lm[0] * w)
            y = int(lm[1] * h)
            cv2.circle(frame, (x, y), 5, color, -1)
    return frame


def run_cv_thread(event_queue, stop_event: threading.Event, hand_state_ref: list, preview_ref: list | None = None):
    """
    Run camera + hand tracking + punch detection in a background thread.
    Puts punch events into event_queue. Stops when stop_event is set.
    """
    try:
        camera = Camera(width=640, height=480)
        if not camera.open():
            event_queue.put({"type": "error", "message": "Could not open webcam"})
            return
    except Exception as e:
        event_queue.put({"type": "error", "message": str(e)})
        return

    with HandTracker(max_num_hands=2) as tracker:
        detector = PunchDetector(
            event_queue,
            cooldown_ms=200,
            velocity_threshold=0.07,
        )
        frame_interval = 1.0 / 45  # 45 fps for smoother tracking
        next_frame_time = time.monotonic()
        prev_smoothed: dict = {}

        while not stop_event.is_set():
            ok, frame = camera.read()
            if not ok or frame is None:
                break
            now = time.monotonic()
            if now >= next_frame_time:
                hands_data = tracker.process(frame)
                hands_data, prev_smoothed = _smooth_landmarks(hands_data, prev_smoothed)
                detector.process_hands(hands_data, now)
                # Update shared hand state for dodge/block
                if hand_state_ref:
                    hand_state_ref[0] = _compute_hand_state(hands_data)
                # Update webcam preview with hand landmarks (blue when blocking, green otherwise)
                if preview_ref is not None:
                    preview_frame = frame.copy()
                    if hands_data:
                        state = hand_state_ref[0] if hand_state_ref else {}
                        preview_frame = _draw_hand_landmarks(
                            preview_frame, hands_data, state.get("blocking", False)
                        )
                    preview_ref[0] = preview_frame
                next_frame_time = now + frame_interval
            time.sleep(0.005)

    camera.release()
