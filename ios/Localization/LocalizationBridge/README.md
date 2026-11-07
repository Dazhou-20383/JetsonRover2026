# LocalizationBridge (iOS)

`LocalizationBridge` is a SwiftUI app that turns an iPhone into a wireless localization
sensor, waypoint-picker, and camera-fallback for the rover. It has three independent
jobs, each on its own socket:

1. **Pose streaming** — `ARSessionManager` reads ARKit's world-tracking camera pose and
   sends a 2D `(x, y, yaw)` estimate to the Jetson several times a second, over **UDP**.
2. **Waypoint / route planning** — `MapViewModel` lets the operator long-press a point on
   an `MKMapView`, then sends that GPS waypoint (plus a MapKit-derived turn-by-turn route)
   to the Jetson as a one-shot goal message, over **TCP**.
3. **Optional camera streaming** — when the operator turns on **Stream iPhone camera**
   (off by default, never enabled automatically), `ARSessionManager` also downsamples and
   JPEG-encodes ARKit camera frames and streams them to the Jetson at the same rate as
   pose, over **UDP**, so `camera_node.py` has an image source when the rover has no
   camera of its own.

## Using the app

1. Launch the app. Only the map runs, and nothing connects to the network yet.
2. Tap **Connect** (you can also do this after step 3). A spinner shows while the app opens the TCP link to the Jetson
   (3 s timeout). On success, ARKit pose tracking starts and the status pill turns green
   once tracking is normal. On failure, the card shows why, with a **Retry** button.
3. Long-press the map to drop a goal. A walking route is planned right away and drawn on
   the map. You don't need to be connected for this. Route planning uses Apple Maps over
   cellular or Wi-Fi, and the phone usually loses internet once it's tethered to the
   Jetson, so plan first and then connect. Then tap **Send goal + route**, which sends
   the stored route over the tether with no internet needed. If planning failed, you can
   tap **Re-plan** or send the goal on its own.
4. Optionally, turn on **Stream iPhone camera** in the tracking card.
5. Tap **Disconnect** to stop ARKit and the camera completely. If the Jetson drops the
   link (closed socket, or a TCP keep-alive timeout after about 11 s), the app does the
   same thing and shows **Retry**.

The UI is a full-screen map with a floating status pill and a Maps-style bottom sheet:
connection, tracking (pose and camera toggle), goal, route, details/payloads, and a
debug-log sheet.

### Power

- ARKit, the camera and the pose stream only run while connected.
- ARKit uses a pose-only configuration: no plane detection, environment texturing or
  light estimation, and the lowest frame rate and resolution video format.
- There is no AR camera preview. The old hidden `ARView` rendered every frame under the
  opaque map.
- The camera stream is opt-in and drops frames while a previous encode is still in
  flight.
- 5 Hz pose updates only redraw the small views that show pose, not the map.
- Per-frame debug logging was removed; send failures log once per failure streak.
- The heading filter is set to 2°.
- The idle timer is disabled only while connected, because a screen lock would suspend
  the app and stop the pose stream.

## Data flow

```
ARKit camera pose ──> ARSessionManager ──> NetworkManager (UDP:5005) ──> Jetson
                                                                          iphone_pose_node.py
ARKit camera frame ──> ARSessionManager ──> NetworkManager (UDP:5007) ──> Jetson
                                                                          camera_node.py (fallback)
CoreLocation + MapKit route ──> MapViewModel ──> NetworkManager (TCP:5006) ──> Jetson
                                                                          waypoint_bridge_node.py
```

- `ARSessionManager` is an `ARSessionDelegate`. On every `session(_:didUpdate:)` callback
  it throttles to `targetHz` (5 Hz by default), extracts `(x, y, yaw)` from the camera
  transform, and fires a JSON `PosePayload` over its own UDP `NetworkManager`. In the same
  throttled callback it also hands `frame.capturedImage` to a `Task.detached` that
  downscales it (~320px wide), JPEG-encodes it, and sends the bytes over a second,
  independent UDP `NetworkManager` — the encode runs off the main actor so a slow JPEG
  encode can never stall the pose send or the UI.
- `MapViewModel` reacts to long-presses on the map (`selectWaypoint`), previews the
  outgoing JSON, and on `sendGoal()` sends a `WaypointMessage`, then asynchronously asks
  `MKDirections` for a walking route to the same point and sends a derived
  `RouteGuideMessage` with turn-by-turn steps — both over its own TCP `NetworkManager`.
- `NetworkManager` wraps a raw BSD socket and JSON-encodes + sends whatever `Encodable`
  it's given (or sends pre-encoded `Data` directly via `send(data:)`). Each instance owns
  exactly one socket and one transport (`.udp` or `.tcp`); `LocalizationBridgeApp` creates
  one per feature rather than sharing a socket across them. TCP payloads are
  newline-delimited, since TCP is a byte stream with no built-in message boundaries (a UDP
  datagram is already a whole message — pose JSON or a JPEG frame — so it needs no
  delimiter).
- `DebugLogStore` is a tiny ring buffer of strings that all three paths append to, shown
  live in the corner of the screen.

`LocalizationBridgeApp.swift` wires all of this up: it hardcodes the Jetson's
Wi-Fi hotspot address (`10.42.0.1`, port `5005` UDP for pose, port `5006` TCP for
waypoints/routes, and port `5007` UDP for the optional camera stream) and constructs the
`@StateObject`s. At launch it only requests location permission. `ConnectionManager`
owns the Connect/Disconnect state machine: it opens the TCP link off the main thread,
then starts the AR session, which requests camera permission on the first connect.

### Camera fallback: why it's the wide (1x) lens, not ultra-wide (0.5x)

ARKit's world-tracking session exclusively owns the camera and only ever uses the
standard wide (1x) lens — it cannot select the ultra-wide (0.5x) lens, and running a
second, independent `AVCaptureSession` for the ultra-wide lens at the same time as ARKit
is not reliably supported on iOS (camera hardware exclusivity). Rather than add a second
capture session — which risks one session interrupting the other — this reuses the same
wide-angle frames ARKit is already capturing for pose (`ARFrame.capturedImage`). The
tradeoff: the streamed feed is the 1x lens, not a true 0.5x ultra-wide feed, in exchange
for pose tracking and camera streaming running fully concurrently with no extra
permission/session cost. See the doc comment on `ARSessionManager` for the same
rationale in code.

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
- `sensors/camera_node.py` tries the onboard camera first (`/dev/video0` via GStreamer,
  with a warm-up read check since a GStreamer pipeline can report "opened" without ever
  producing frames); only if that fails does it bind a UDP socket on `5007` and treat each
  received datagram as one full JPEG frame from the phone, decoding and publishing it
  exactly like a locally-captured frame (`/camera/image_raw`, `/sensor/image`) — so
  downstream consumers (`vlm_node`, `LogoNav_ros`, `dashboard_node`) need no changes.

## Where this is still inefficient

Splitting the transports, de-duplicating the JSON encoding, and caching MapKit route
requests (see below) removed some of the worst offenders, but a few remain:

- **Pose sends run on the main thread.** Every pose update calls
  `networkManager.sendMessage(...)` directly from the main-queue `ARSessionDelegate`
  callback in [ARSessionManager.swift](ARSessionManager.swift), and the send itself blocks
  synchronously on `queue.sync { ... sendto(...) }` in
  [NetworkManager.swift](NetworkManager.swift). The syscall is usually fast, but there's
  no structural reason pose/UI state and socket I/O share a thread — under any socket
  buffer pressure this stalls SwiftUI's main thread and the whole map UI along
  with it.

- **Hardcoded network config.** The Jetson's IP and ports are constants in
  `LocalizationBridgeApp.init()`; there's no in-app setting.

- **No automatic reconnect.** If the link drops, the app stops streaming and shows
  **Retry**, but it doesn't reconnect by itself.

- **`DebugLogStore.append` is O(n) per call.** Once the buffer hits its cap (200 entries),
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
- **Fixed a launch crash when the Jetson isn't reachable.** The TCP `NetworkManager` used
  to `connect()` inside `init()`, which was `try!`-ed from the App initializer. It now
  connects only when the user taps Connect, with a bounded timeout. TCP sockets also set
  `SO_NOSIGPIPE`, so a write after the Jetson closes the socket no longer kills the app
  with SIGPIPE.
- **Camera frames now fit in a UDP send.** iOS's default 9 KB UDP send buffer was smaller
  than a JPEG frame, so every camera send failed with `EMSGSIZE`. The buffer is now 64 KB.
- **Pose and waypoint/route traffic no longer share a socket.** See "Why pose is UDP and
  waypoints/routes are TCP" above.
