import json
import base64
import cv2
import numpy as np
import urllib.error
import urllib.request
import time


def _json_request(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Homography server request failed: {exc}") from exc

class Homography:
    def __init__(self, server_url="http://192.168.55.100:8080"):
        self.server_url = server_url.rstrip("/")
        self.matrix = None
        self.dst_points = np.array([[1, 0.5], [1, -0.5], [2, 0.5], [2, -0.5]], dtype=np.float32)
        self.image_b64 = None
        self.content_type = "image/jpeg"

    def set_image(self, image_b64, content_type="image/jpeg"):
        self.image_b64 = image_b64
        self.content_type = content_type
        _json_request(f"{self.server_url}/image", {"image": image_b64, "content_type": content_type})

    def set_matrix(self):
        """Set the homography matrix using source and destination points."""
        src_points = self.get_source_points()
        self.matrix, _ = cv2.findHomography(src_points, self.dst_points)

    def get_source_points(self, required_points=4, timeout=None, poll_interval=0.5):
        """Wait for annotated source points from the homography server."""
        if not self.image_b64:
            raise ValueError("No image set. Call set_image() first.")

        deadline = None if timeout is None else time.monotonic() + float(timeout)

        while True:
            payload = _json_request(f"{self.server_url}/annotations")
            annotations = payload.get("annotations", [])
            if len(annotations) >= required_points:
                return np.array(
                    [[point["x"], point["y"]] for point in annotations[:required_points]],
                    dtype=np.float32,
                )

            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for {required_points} annotations from the homography server.")

            time.sleep(poll_interval)

    def project_point(self, x, y):
        """Project a point (x, y) using the homography matrix."""
        if self.matrix is None:
            raise ValueError("Homography matrix is not set. Call set_matrix() first.")
        point = np.array([x, y, 1])
        projected_point = self.matrix @ point
        projected_point /= projected_point[2]  # Normalize by the third coordinate
        return projected_point[0], projected_point[1]


class Logger:
    def __init__(self, conv_limit=5):
        self.conv_limit = conv_limit
        self.history = []
        self.conv_len = []

    def log(self, entry):
        """Append a new entry to the history, maintaining the conversation limit."""
        self.history.extend(entry)
        self.conv_len.append(len(entry))

        if len(self.conv_len) > self.conv_limit:
            while len(self.conv_len) > self.conv_limit:
                removed_length = self.conv_len.pop(0)
                self.history = self.history[removed_length:]

    def get_history(self):
        """Return the current history."""
        return self.history