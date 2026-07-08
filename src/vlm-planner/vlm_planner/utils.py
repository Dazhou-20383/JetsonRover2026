import json
import base64
import cv2
import numpy as np
import urllib.error
import urllib.request


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
    def __init__(self, server_url="http://127.0.0.1:8080"):
        self.server_url = server_url.rstrip("/")
        self.matrix = None
        self.dst_points = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
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

    def get_source_points(self):
        """Fetch annotated source points from the homography server."""
        if not self.image_b64:
            raise ValueError("No image set. Call set_image() first.")

        payload = _json_request(f"{self.server_url}/annotations")
        annotations = payload.get("annotations", [])
        if len(annotations) < 4:
            raise ValueError("Need at least four annotations from the homography server.")

        image = cv2.imdecode(
            np.frombuffer(base64.b64decode(self.image_b64), dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        height, width = image.shape[:2]
        return np.array(
            [[point["x"] * width / 100.0, point["y"] * height / 100.0] for point in annotations[:4]],
            dtype=np.float32,
        )

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