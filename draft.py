
def observe():
    """Gets a larger observation of the surrounds. Use when trying to find a specific path or sign. Always use this to verify traffic lights status at intersection. Don't use this during safe navigation. Returns a list of observations of surroundings."""
    pass

def stop():
    """Stop the rover completely by removing waypoint. Useful when encountering situations that requires more careful thinking or need to wait for change of situation. (e.g. encountering red light at an intersection, construction site). Returns success or failure."""
    pass

def turn_right():
    """Turns the rover 30 deg right. This is useful to observe or to place waypoint for micromanuevers."""
    pass

def turn_left():
    """Turns the rover 30 deg left. This is useful to observe or to place waypoint for micromanuevers."""
    pass

def turn_towards(direction):
    """Turn towards an absolute direction in compass degrees(e.g. magnetic north is 0 deg and southwest is 225 deg). Always stop() the rover before calling turn_towards(). This can be used when navigating uncertainty to observe more surroundings or to align rover's axis with the direction that it needs to head towards. Don't use this when navigating towards a safe waypoint, the low-level policy handles object avoidance and path following. Returns success or failure"""
    pass

def place_waypoint(x, y):
    """This function places a waypoint at location x, y. This is an generic navigation function. Only use this when the anticipated route is straight and without any danger. Could be used in park or when goal is almost directly aligned with the sidewalk. The function takes argument in the robot's reference frame. x, y are distances in meters, where +x is front and +y is right. Often waypoints placed with this function are somewhat far away to allow the robot to autonomously travel a decent distance in a simple environment. Returns success or failure"""
    pass

def place_waypoint_precise(loc_description):
    """This function places a waypoint. Use this function when navigating safety critical loctions like a cross walk or for micro navigations like choosing a specific route among alternatives. Give a detailed description of the location where the rover should navigate to. E.g. loc_description =  "The beginning of the closest cross walk on the right". Always use grounded reasoning before placing the waypoint; good idea to observe surrounding first or turn to correct direction before placing waypoint.Don't place the waypoint far away where safety is critical. The function places the waypoint and returns the location of the waypoint in pixel coordinate of the observation. Returns success or failure"""
    pass

tools = [
    observe,
    stop,
    turn_right,
    turn_left,
    turn_towards,
    place_waypoint,
    place_waypoint_precise,
]