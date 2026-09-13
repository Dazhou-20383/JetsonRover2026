==NOTE: PROJECT IN PROGRESS.==
# Urban Autonomous Rover
Embodied intelligence and autonomy is a rapidly expanding area of research. Despite the ample end-to-end navigation and object avoidance work for small ground vehicles, there lack a open source solution for generalized urban navigation.

Urban navigation not only requires planning, path following, object avoidance, etc., it also demands more nuanced scene understanding and decision making, like navigating a controlled intersection.

This project aims to leverage the general knowledge of LLM models and a low-level navigation model to enable small ground rovers to robustly navigate urban environments.

Moreover, we are working under a budget and energy constrain so we choose to use only a commercial webcam for autonomy. For rapid prototyping, we developed ***iSLAM***, a framework to bridge iPhone pose estimation and GPS ability to a onboard computer.

![rover img](assets/rover.JPG)

> Rover under sunlight

# Rover Performance
***We have not tested the autonomy of the rover.*** The manual controller can be run with `bash manuel.bash` after connecting your iPhone joystick to the Jetson hotspot.



https://github.com/user-attachments/assets/c28c2bde-2ef2-4005-b51a-87c4eb4a28e1



**Dashboard**
A dashboard server also can be used to monitor autonomy status wirelessly.

![dashboard img](assets/dashboard.PNG)

# How to Run
**Arduino** — `/arduino/main.cpp`, upload from your computer via the Arduino IDE. Most hardware interaction config lives here (and in `motion-converter`), so this is where you tune hardware behaviour. All motors can currently reach max PWM. Servo initial position is set via `WheelChannel.ServoInitUs`, where `1500` is neutral (maximum left/right range).
```bash
# run 1. manual controller  2. MBRA only  3. full autonomy
bash manuel.bash
bash mbra.bash
bash rover.bash
```

**Manuel Controllerr** — `/ios/Rover-joystick`, build with Xcode. The stop button only works in MBRA mode; the joystick only works in manual mode.

**MBRA Only** — open a second SSH terminal and publish a waypoint:
```bash
ros2 topic pub --once /mbra/waypoints geometry_msgs/msg/Point "{x: 100.0, y: 0.0, z: 0.0}"
```
then hit enable on your phone.

**Dashboard** — on the Jetson: `ros2 run video_logger dashboard_node`. On your computer (connected to the Jetson hotspot): `cd dashboard; npm start`.

# Autonomy Stack
### High-level agent
We used Ollama for local VLM inference. Between open source models, we found that Jetson can inference at our target frequency (0.2Hz) without OOM error for VLMs below 2 billion parameters. We choose `Qwen3.5:2b` for its visual understanding and pointing ability.

The agent receives current observation, pose, and a navigation instruction. An agent harness is written from scratch. We give the following tools to the agent `stop()`, `turn()`, `place_waypoint()`,  `place_waypoint_precise()`. Notably, to enable precise navigation, `place_waypoint_precise()` allows the agent to point to a location on the observation image, which is translated into a corresponding waypoint on the 2D plane.
### Low-level policy
We use the logo_nav model from the paper [MBRA](https://github.com/NHirose/Learning-to-Drive-Anywhere-with-MBRA). Logo_nav receives the observation, pose, and target waypoint and outputs the Twist commands. Logo_nav is training on cross-embodiment data and have gained basic object avoidance ability.

###  Hardware
- [Jakkra's Mars Rover](https://github.com/jakkra/Mars-Rover)
- Jetson Orin Nano Developer Kit 8GB
- Arduino Uno
- iPhone (for manuel control and pose estimation)

---
**Special thanks** to Jeffrey Juncheng Guo, Adit Bhargava, and Daniel Tianhao Yang for sponsoring this project with electronics, accomodation, and, critically, your 3D printer. The progress we made is impossible without you.
