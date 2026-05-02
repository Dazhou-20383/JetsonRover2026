import cv2
import time

# Optimized pipeline for Logitech -> Hardware Encoding -> Matroska File
# Simplified pipeline with videoconvert and MKV output
pipeline = (
    "v4l2src device=/dev/video0 ! "
    "video/x-raw, width=1280, height=720, framerate=30/1 ! "
    "videoconvert ! "
    "x264enc tune=zerolatency speed-preset=ultrafast ! "
    "matroskamux ! "
    "filesink location=rover_test.mkv"
)

# Using GStreamer directly for saving is more efficient than cv2.VideoWriter
import subprocess

print("Recording started... will record for 10 seconds.")
try:
    # Run the GStreamer command via shell for direct hardware-to-disk recording
    cmd = f"gst-launch-1.0 {pipeline}"
    process = subprocess.Popen(cmd, shell=True)
    
    # Record for 10 seconds
    time.sleep(10)
    
    # Gracefully terminate
    process.terminate()
    print("\nRecording finished. File saved as rover_test.mp4")

except KeyboardInterrupt:
    process.terminate()
    print("\nRecording stopped early.")