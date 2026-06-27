import cv2
import numpy as np


class Homography:
    def __init__(self, matrix):
        self.matrix = matrix
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
        point = np.array([x, y, 1])
        projected_point = self.matrix @ point
        projected_point /= projected_point[2]  # Normalize by the third coordinate
        return projected_point[0], projected_point[1]
