"""Webcam capture using OpenCV."""

import cv2


class Camera:
    """Captures frames from the default webcam."""

    def __init__(self, device_id: int = 0, width: int = 640, height: int = 480):
        self.device_id = device_id
        self.width = width
        self.height = height
        self._cap = None

    def open(self) -> bool:
        """Open the webcam. Returns True on success."""
        self._cap = cv2.VideoCapture(self.device_id)
        if not self._cap.isOpened():
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        return True

    def read(self):
        """Read a frame. Returns (success, frame) where frame is BGR numpy array or None."""
        if self._cap is None:
            return False, None
        return self._cap.read()

    def release(self):
        """Release the webcam."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
