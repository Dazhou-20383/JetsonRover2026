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

prev_frame_time = 0
new_frame_time = 0

print("Starting performance test... Press Ctrl+C to stop.")

try:
    while True:
        start_time = time.time() # Start latency timer
        
        ret, frame = cap.read()
        if not ret:
            break
        
        cv2.imshow('Performance Test', frame)

        # Calculate FPS
        new_frame_time = time.time()
        fps = 1 / (new_frame_time - prev_frame_time)
        prev_frame_time = new_frame_time
        
        # Calculate Latency (Processing time for this loop)
        latency = (time.time() - start_time) * 1000 # in milliseconds

        # Print to terminal instead of showing window
        print(f"FPS: {fps:.2f} | Latency: {latency:.2f}ms", end="\r")

except KeyboardInterrupt:
    print("\nTest stopped by user.")

cap.release()