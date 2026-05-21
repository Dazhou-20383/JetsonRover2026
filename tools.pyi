def observe():
    """
    Retrieves a wider, detailed field-of-view of the surroundings.
    
    * WHEN TO USE: To find specific paths/signs, resolve uncertainty, or verify traffic lights at intersections.
    * WHEN NOT TO USE: During routine, safe navigation on clear paths.
    * YIELDS: A large image of surrounding objects, hazards, and states in the current environment.
    """

def stop():
    """
    Stops the rover completely by deleting the active waypoint.
    
    * WHEN TO USE: Encountering high uncertainty, safety hazards, or waiting for environmental changes (e.g., red lights, pedestrians).
    * WHEN NOT TO USE: When the current trajectory is safe and unobstructed.
    * YIELDS: Confirmation string: "Rover stopped. Speed is 0."
    """

def turn_right():
    """
    Pans the rover exactly 30 degrees to the right in place.
    
    * WHEN TO USE: To adjust the camera view for better observation or align the chassis for micromanuevers.
    * YIELDS: The new absolute compass heading of the rover.
    """

def turn_left():
    """
    Pans the rover exactly 30 degrees to the left in place.
    
    * WHEN TO USE: To adjust the camera view for better observation or align the chassis for micromanuevers.
    * YIELDS: The new absolute compass heading of the rover.
    """

def turn_towards(direction: int):
    """
    Turns the rover towards an absolute compass direction.
    
    * CRITICAL RULE: You MUST successfully execute stop() in the previous step before calling this tool. Calling this while moving will fail.
    * WHEN TO USE: Navigating uncertainty to align the rover's axis with the global target heading.
    * WHEN NOT TO USE: When actively navigating towards a safe waypoint.
    * PARAMETERS:
        - direction (int): Absolute global compass direction in degrees (0-359, where North=0).
    * YIELDS: Confirmation of the new heading or a failure error if the rover was moving.
    """

def place_waypoint(x: float, y: float):
    """
    Places a standard navigational waypoint using the robot's RELATIVE local coordinates.
    
    * WHEN TO USE: ONLY when the anticipated route is straight, safe, and free of danger. Place far away (e.g., x=10) to maximize autonomous travel.
    * WHEN NOT TO USE: In safety-critical areas, intersections, or complex terrain.
    * PARAMETERS:
        - x (float): Distance FORWARD from the rover in meters.
        - y (float): Distance RIGHT from the rover in meters (use negative for left).
    * YIELDS: Confirmation string of successful placement and distance to waypoint.
    """

def place_waypoint_precise(loc_description: str):
    """
    Places a precise waypoint based on visual scene understanding.
    
    * WHEN TO USE: In safety-critical locations (e.g., crosswalks) or for micromanuevers. Keep the target close.
    * WHEN NOT TO USE: Do not place far away. Do not use without first grounding reasoning via observe().
    * PARAMETERS:
        - loc_description (str): A highly detailed visual description of the target (e.g., "The tactile paving at the start of the crosswalk directly ahead").
    * YIELDS: The translated pixel coordinates of the waypoint and confirmation of placement.
    """