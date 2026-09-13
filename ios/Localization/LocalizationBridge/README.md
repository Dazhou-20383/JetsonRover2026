# LocalizationBridge (iOS)

`LocalizationBridge` is a SwiftUI app that turns an iPhone into a wireless localization
sensor and waypoint-picker for the rover. It has two independent jobs, each on its own
socket:

1. **Pose streaming** — `ARSessionManager` reads ARKit's world-tracking camera pose and
   sends a 2D `(x, y, yaw)` estimate to the Jetson several times a second, over **UDP**.
2. **Waypoint / route planning** — `MapViewModel` lets the operator long-press a point on
   an `MKMapView`, then sends that GPS waypoint (plus a MapKit-derived turn-by-turn route)
   to the Jetson as a one-shot goal message, over **TCP**.

Both paths are shown together in a single view, `CombinedNavigationView`, which overlays
the (invisible) AR camera feed, the map, a pose/status HUD, and a debug log.

## Data flow

```
ARKit camera pose ──> ARSessionManager ──> NetworkManager (UDP:5005) ──> Jetson
                                                                          iphone_pose_node.py
CoreLocation + MapKit route ──> MapViewModel ──> NetworkManager (TCP:5006) ──> Jetson
                                                                          waypoint_bridge_node.py
```

- `ARSessionManager` is an `ARSessionDelegate`. On every `session(_:didUpdate:)` callback
  it throttles to `targetHz` (5 Hz by default), extracts `(x, y, yaw)` from the camera
  transform, and fires a JSON `PosePayload` over its own UDP `NetworkManager`.
- `MapViewModel` reacts to long-presses on the map (`selectWaypoint`), previews the
  outgoing JSON, and on `sendGoal()` sends a `WaypointMessage`, then asynchronously asks
  `MKDirections` for a walking route to the same point and sends a derived
  `RouteGuideMessage` with turn-by-turn steps — both over its own TCP `NetworkManager`.
- `NetworkManager` wraps a raw BSD socket and JSON-encodes + sends whatever `Encodable`
  it's given. Each instance owns exactly one socket and one transport (`.udp` or `.tcp`);
  `LocalizationBridgeApp` creates one of each rather than sharing a socket across both
  features. TCP payloads are newline-delimited, since TCP is a byte stream with no
  built-in message boundaries (a UDP datagram is already a whole message, so it needs no
  delimiter).
- `DebugLogStore` is a tiny ring buffer of strings that both features append to, shown
  live in the corner of the screen.

`LocalizationBridgeApp.swift` wires all of this up: it hardcodes the Jetson's
USB-tether address (`10.42.0.1`, port `5005` UDP for pose and port `5006` TCP for
waypoints/routes), constructs the three `@StateObject`s, and starts the AR session on
`.onAppear`, chaining into the location-permission prompt only after the
camera-permission prompt has fully resolved (to avoid iOS queuing overlapping system
alerts).

### Why pose is UDP and waypoints/routes are TCP

Pose is a 5 Hz stream where a dropped sample is immediately superseded by the next one —
loss is cheap, and TCP's retransmission/ordering guarantees would only add latency for no
benefit. A manual goal or route guide is the opposite: it's a rare, one-shot, high-stakes
message where silent loss is a real problem, so it goes over TCP, which gives it
in-order, at-least-delivered-or-erred semantics for free. Splitting them onto separate
sockets also means a slow or blocked waypoint/route send can no longer delay the next
pose sample, and vice versa.

### ROS2 / onboard side

The Jetson side mirrors the same split:

- `sensors/iphone_pose_node.py` binds a UDP socket on `5005`, decodes each datagram as one
  pose JSON object, and republishes it as `geometry_msgs/Pose2D` on `/robot/pose`.
- `sensors/waypoint_bridge_node.py` listens on TCP `5006`, reads newline-delimited JSON
  off each connection, and republishes `manual_goal` / `route_guide` payloads as tagged
  JSON strings on `/bridge/manual_goal_json` / `/bridge/route_guide_json` for downstream
  ROS2/VLM consumers.

## Where this is still inefficient

Splitting the transports, de-duplicating the JSON encoding, and caching MapKit route
requests (see below) removed some of the worst offenders, but a few remain:

- **Network I/O runs on the main actor.** Every pose update does
  `Task { @MainActor in ... networkManager.sendMessage(...) }` in
  [ARSessionManager.swift](ARSessionManager.swift), and the send itself blocks
  synchronously on `sendQueue.sync { ... sendto(...) }` in
  [NetworkManager.swift](NetworkManager.swift). The syscall is usually fast, but there's
  no structural reason pose/UI state and socket I/O share a thread — under any socket
  buffer pressure this stalls SwiftUI's main thread and the whole camera/map UI along
  with it.

- **Hardcoded network config, and TCP makes the crash mode worse.** The Jetson's IP and
  ports are baked into `LocalizationBridgeApp.init()` as `try!`
  ([LocalizationBridgeApp.swift](LocalizationBridgeApp.swift)). This was already true for
  UDP (a bad IP literal fails at launch), but the new TCP `NetworkManager` also calls
  `connect()` synchronously during `init()` — if `waypoint_bridge_node.py` isn't up yet
  when the app launches (e.g. the Jetson is still booting), that `try!` crashes the app
  immediately instead of retrying or degrading to a "waiting for Jetson" state.

- **No reconnection/backoff strategy.** If a send fails after startup, `ARSessionManager`
  and `MapViewModel` just surface the error string in the status/debug UI and move on;
  there's no retry, no exponential backoff, and — now that waypoints are TCP — no
  automatic reconnect if the Jetson reboots or the TCP connection drops mid-session.

- **AR pose updates re-render the whole view tree at 5 Hz.** `x`, `y`, `yaw`,
  `statusText`, and `latestPoseText` are all separate `@Published` properties updated on
  every accepted frame. Because `CombinedNavigationView` observes `ARSessionManager` as a
  single `@EnvironmentObject`, each field change invalidates the entire view body —
  including the `WaypointMapView`/`MKMapView` `UIViewRepresentable` — rather than just the
  small pose HUD that actually needs to redraw.

- **`DebugLogStore.append` is O(n) per call.** Once the buffer hits its cap (20 entries),
  every subsequent append does an array `removeFirst(_:)`, which shifts every remaining
  element down ([DebugLogStore.swift](DebugLogStore.swift)). Trivial at 20 entries and a
  couple Hz, but it's a ring buffer implemented as a shifting array rather than an actual
  ring buffer.

## What was fixed

- **Removed redundant JSON encode/decode.** `MapViewModel.sendGoal()` used to send a
  compactly-encoded `WaypointMessage` through `NetworkManager`'s own encoder, then
  re-parse that JSON string with `JSONSerialization` just to pretty-print it for the
  on-screen preview — three encode/decode passes for one waypoint. It now encodes the
  message once with the view model's own pretty encoder and hands those exact bytes to
  `NetworkManager.send(data:)`, so the same bytes are previewed and sent
  ([MapViewModel.swift](MapViewModel.swift)).
- **MapKit route requests are cached.** `updateRouteGuidance` now keys a small
  origin/destination cache (rounded to ~1 m, 2-minute TTL) and reuses a recent `MKRoute`
  instead of re-querying `MKDirections` for the same or a nearby goal
  ([MapViewModel.swift](MapViewModel.swift)).
- **Pose and waypoint/route traffic no longer share a socket.** See "Why pose is UDP and
  waypoints/routes are TCP" above.
