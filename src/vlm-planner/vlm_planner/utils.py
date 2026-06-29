import cv2
import numpy as np


class Homography:
    def __init__(self,):
        self.matrix = None
        # Example dst_points in the rover frame in meters
        self.dst_points = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)

    def set_matrix(self):
        """Set the homography matrix using source and destination points."""
        src_points = self.get_src_points()
        self.matrix, mask = cv2.findHomography(src_points, self.matrix)

    def get_src_points(self):
        """Get the source points for homography transformation."""
        return np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)

    def project_point(self, x, y):
        """Project a point (x, y) using the homography matrix."""
        if not self.matrix:
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

        if sum(self.conv_len) > self.conv_limit:
            while sum(self.conv_len) > self.conv_limit:
                removed_length = self.conv_len.pop(0)
                self.history = self.history[removed_length:]

    def get_history(self):
        """Return the current history."""
        return self.history