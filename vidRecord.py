import cv2
import time

# Optimized pipeline for Logitech -> Hardware Encoding -> MP4 File
# We use 'omxh264enc' for hardware acceleration on the Orin Nano
pipeline = (
    "v4l2src device=/dev/video0 ! "
    "video/x-raw, width=1280, height=720, framerate=30/1 ! "
    "nvvidconv ! "
    "omxh264enc ! "
    "qtmux ! "
    "filesink location=rover_test.mp4"
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