tools = [
  {
    "type": "function",
    "function": {
      "name": "observe",
      "description": "Retrieves a wider, detailed field-of-view of the surroundings. Use this to find specific paths or signs, resolve uncertainty, or verify traffic lights at intersections. Do not use during routine, safe navigation on clear paths. Returns a large image of surrounding objects, hazards, and environmental states.",
      "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "stop",
      "description": "Stops the rover completely by deleting the active waypoint. Use when encountering uncertainty, safety hazards, pedestrians, or waiting for environmental changes such as red lights. Do not use when the current trajectory is safe and unobstructed. Returns confirmation that the rover has stopped.",
      "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "turn_right",
      "description": "Turns the rover exactly 30 degrees to the right in place. Use to adjust the camera view for better observation or align the chassis for micromaneuvers. Returns the new absolute compass heading.",
      "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "turn_left",
      "description": "Turns the rover exactly 30 degrees to the left in place. Use to adjust the camera view for better observation or align the chassis for micromaneuvers. Returns the new absolute compass heading.",
      "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "turn_towards",
      "description": "Turns the rover towards an absolute compass direction. CRITICAL: stop() must have been successfully executed immediately before this call or the action will fail. Use for aligning the rover with a global target heading during uncertain navigation. Do not use while actively navigating toward a safe waypoint.",
      "parameters": {
        "type": "object",
        "properties": {
          "direction": {
            "type": "integer",
            "description": "Absolute compass heading in degrees from 0-359, where North=0."
          }
        },
        "required": ["direction"],
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "place_waypoint",
      "description": "Places a standard navigational waypoint using rover-relative local coordinates. Use only when the anticipated route is straight, safe, and free of danger. Prefer farther targets such as x=10 for efficient autonomous travel. Do not use in safety-critical areas, intersections, or complex terrain.",
      "parameters": {
        "type": "object",
        "properties": {
          "x": {
            "type": "number",
            "description": "Distance forward from the rover in meters."
          },
          "y": {
            "type": "number",
            "description": "Distance right from the rover in meters. Use negative values for left."
          }
        },
        "required": ["x", "y"],
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "place_waypoint_precise",
      "description": "Places a precise waypoint based on visual scene understanding. Use in safety-critical locations such as crosswalks or for micromaneuvers. Targets should remain close to the rover. Do not use for far-away targets. Always use grounded reasoning to ensure the target is safe. Returns translated pixel coordinates and waypoint placement confirmation.",
      "parameters": {
        "type": "object",
        "properties": {
          "loc_description": {
            "type": "string",
            "description": "Detailed visual description of the target location, such as 'The tactile paving at the start of the crosswalk directly ahead'."
          }
        },
        "required": ["loc_description"],
      }
    }
  }
]