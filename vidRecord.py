import cv2
import time
import numpy as np

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

frames = []
fps_values = []

try:
    while True:
        start_time = time.time() # Start latency timer
        
        ret, frame = cap.read()
        if not ret:
            break

        frames.append(frame)

        # Calculate FPS
        new_frame_time = time.time()
        fps = 1 / (new_frame_time - prev_frame_time)
        prev_frame_time = new_frame_time
        
        # Calculate Latency (Processing time for this loop)
        latency = (time.time() - start_time) * 1000 # in milliseconds

        # Print to terminal instead of showing window
        print(f"FPS: {fps:.2f} | Latency: {latency:.2f}ms", end="\r")
        fps_values.append(fps)

except KeyboardInterrupt:
    print("\nTest stopped by user.")
finally:
    if frames:
        height, width, layers = frames[0].shape
        average_fps = np.mean(fps_values)
        print(f"\nAverage FPS: {average_fps:.2f}")
        out = cv2.VideoWriter('output.mp4', cv2.VideoWriter_fourcc(*'mp4v'), average_fps, (width, height))
        for f in frames:
            out.write(f)
        out.release()
        print(f"\nSaved {len(frames)} frames to output.mp4")

    cap.release()