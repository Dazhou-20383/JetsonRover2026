from wakepy import keep
import time

# Keeps the system awake for a long-running process (e.g., training a model)
with keep.running():
    print("System will stay awake for the duration of this script.")
    print("===============================================")
    # Execute blocking task
    time.sleep(3600)  # Sleep for 1 hour (3600 seconds)
    pass