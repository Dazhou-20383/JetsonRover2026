import cv2
import time

# Optimized GStreamer pipeline for Logitech on Jetson
pipeline = pipeline = (
    "v4l2src device=/dev/video0 ! "
    "videoconvert ! "
    "video/x-raw, format=BGR ! "
    "appsink drop=1"
)

cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

print("Starting performance test... Press Ctrl+C to stop.")

try:
    while True:
        start_time = time.time() # Start latency timer
        
        ret, frame = cap.read()
        if not ret:
            break
        
        cv2.imshow('Performance Test', frame)

except KeyboardInterrupt:
    print("\nTest stopped by user.")

cap.release()