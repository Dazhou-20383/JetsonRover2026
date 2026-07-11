import ARKit
import AVFoundation
import Combine
import Foundation
import OSLog
import simd

final class ARSessionManager: NSObject, ObservableObject, ARSessionDelegate {
    @Published private(set) var x: Float = 0
    @Published private(set) var y: Float = 0
    @Published private(set) var yaw: Float = 0
    @Published private(set) var statusText: String = "Starting AR session..."
    @Published private(set) var latestPoseText: String = "x=0.0000 y=0.0000 yaw=0.0000"

    let session = ARSession()

    private let networkManager: NetworkManager
    private let debugLogStore: DebugLogStore
    private let logger = Logger(subsystem: "iSLAM.LocalizationBridge", category: "ARSession")
    private let updateInterval: TimeInterval
    private var lastSentAt: TimeInterval = 0
    private var didReceiveFrame = false
    private var noFrameTimeoutWorkItem: DispatchWorkItem?


    private var cameraPermissionGranted: Bool = false
    init(networkManager: NetworkManager, debugLogStore: DebugLogStore, targetHz: Double = 5) {
        self.networkManager = networkManager
        self.debugLogStore = debugLogStore
        updateInterval = 1.0 / max(targetHz, 1)
        super.init()
        session.delegate = self
    }

    /// Starts the AR session. `onPermissionResolved` fires exactly once, on the main
    /// thread, after the camera permission question is fully resolved one way or
    /// another (already authorized, granted, denied, restricted, or unsupported).
    /// Callers that need to chain a second permission prompt (e.g. location) should
    /// wait for this callback rather than using a fixed delay — a guessed delay can
    /// fire while the camera system alert is still on screen, causing iOS to queue
    /// the second alert behind it in a way that can stall SwiftUI's update cycle.
    func start(onPermissionResolved: (() -> Void)? = nil) {
        debugLogStore.append("AR: starting AR session")
        logger.info("Starting AR session")

        guard ARWorldTrackingConfiguration.isSupported else {
            statusText = "ARWorldTracking is not supported on this device."
            debugLogStore.append("AR: world tracking not supported")
            logger.error("ARWorldTracking is not supported on this device")
            onPermissionResolved?()
            return
        }

        logger.info("Camera authorization status: \(String(describing: AVCaptureDevice.authorizationStatus(for: .video)), privacy: .public)")


        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            debugLogStore.append("AR: camera already authorized")
            logger.info("Camera already authorized")
            runSession()
            onPermissionResolved?()
        case .notDetermined:
            statusText = "Requesting camera permission..."
            debugLogStore.append("AR: requesting camera permission")
            logger.info("Requesting camera permission")
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    guard let self else {
                        onPermissionResolved?()
                        return
                    }
                    self.debugLogStore.append("AR: camera permission result = \(granted)")
                    self.logger.info("Camera permission result: \(granted, privacy: .public)")
                    if granted {
                        self.runSession()
                    } else {
                        self.statusText = "Camera permission denied. Enable Camera in Settings."
                        self.debugLogStore.append("AR: camera permission denied")
                        self.logger.error("Camera permission denied")
                    }
                    onPermissionResolved?()
                }
            }
        case .denied, .restricted:
            statusText = "Camera permission denied. Enable Camera in Settings."
            debugLogStore.append("AR: camera permission denied or restricted")
            logger.error("Camera permission denied or restricted")
            onPermissionResolved?()
        @unknown default:
            statusText = "Camera permission unavailable."
            debugLogStore.append("AR: camera authorization unavailable")
            logger.error("Camera authorization status unavailable")
            onPermissionResolved?()
        }
    }

    private func runSession() {
        noFrameTimeoutWorkItem?.cancel()
        didReceiveFrame = false

        let configuration = ARWorldTrackingConfiguration()
        configuration.worldAlignment = .gravity

        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
        statusText = "Starting pose stream..."
        debugLogStore.append("AR: session started")
        logger.info("AR session run started")

        let timeoutWorkItem = DispatchWorkItem { [weak self] in
            guard let self, !self.didReceiveFrame else { return }
            self.statusText = "No AR frames received. Check camera permission, lighting, and whether the rear camera is visible."
            self.debugLogStore.append("AR: no frames received within timeout")
            self.logger.error("No AR frames received within timeout window")
        }

        noFrameTimeoutWorkItem = timeoutWorkItem
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0, execute: timeoutWorkItem)
    }

    func stop() {
        session.pause()
        statusText = "AR session paused"
        debugLogStore.append("AR: session paused")
        logger.info("AR session paused")
    }

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        if !didReceiveFrame {
            didReceiveFrame = true
            Task { @MainActor in
                if statusText.hasPrefix("Starting pose stream") || statusText.hasPrefix("No AR frames received") {
                    statusText = "AR frames received. Tracking is active."
                }
            }
            debugLogStore.append("AR: first frame received")
            logger.info("First AR frame received")
        }

        let now = frame.timestamp
        guard now - lastSentAt >= updateInterval else {
            return
        }
        lastSentAt = now

        let pose = Self.extractPose(from: frame.camera.transform)
        let roundedPose = pose.roundedTo4Decimals()

        Task { @MainActor in
            x = roundedPose.x
            y = roundedPose.y
            yaw = roundedPose.yaw
            latestPoseText = Self.poseText(for: roundedPose)
            do {
                _ = try networkManager.sendMessage(
                    PosePayload(x: roundedPose.x, y: roundedPose.y, yaw: roundedPose.yaw)
                )
                debugLogStore.append(String(format: "AR: sent pose x=%.4f y=%.4f yaw=%.4f", roundedPose.x, roundedPose.y, roundedPose.yaw))
            } catch {
                statusText = error.localizedDescription
                debugLogStore.append("AR: send failed - \(error.localizedDescription)")
            }
        }
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        debugLogStore.append("AR: session failed - \(error.localizedDescription)")
        logger.error("AR session failed: \(error.localizedDescription, privacy: .public)")
        Task { @MainActor in
            statusText = "AR session failed: \(error.localizedDescription)"
        }
    }

    func sessionWasInterrupted(_ session: ARSession) {
        debugLogStore.append("AR: session interrupted")
        logger.error("AR session interrupted")
        Task { @MainActor in
            statusText = "AR session interrupted"
        }
    }

    func sessionInterruptionEnded(_ session: ARSession) {
        debugLogStore.append("AR: session interruption ended")
        logger.info("AR session interruption ended")
        Task { @MainActor in
            statusText = "AR session interruption ended"
        }
    }

    func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
        let text: String

        switch camera.trackingState {
        case .normal:
            text = "Tracking normal. Pose stream active."
            debugLogStore.append("AR: tracking normal")
            logger.info("Tracking state normal")
        case .notAvailable:
            text = "Tracking unavailable. Camera feed is not usable right now."
            debugLogStore.append("AR: tracking unavailable")
            logger.error("Tracking state not available")
        case .limited(let reason):
            switch reason {
            case .initializing:
                text = "Tracking limited: initializing. Hold the phone still and let ARKit initialize."
            case .excessiveMotion:
                text = "Tracking limited: excessive motion. Slow down the device movement."
            case .insufficientFeatures:
                text = "Tracking limited: insufficient features. Point at textured surfaces in brighter light."
            case .relocalizing:
                text = "Tracking limited: relocalizing. ARKit is trying to recover tracking."
            @unknown default:
                text = "Tracking limited. ARKit has not reported the exact reason."
            }
            debugLogStore.append("AR: tracking limited - \(String(describing: reason))")
            logger.error("Tracking limited: \(String(describing: reason), privacy: .public)")
        }

        Task { @MainActor in
            statusText = text
        }
    }

    private static func extractPose(from transform: simd_float4x4) -> PlanarPose {
        let translation = transform.columns.3

        // ARKit world axes are right-handed with Y up. For a 2D ground-plane pose,
        // keep world X as output X and map forward motion (-Z in ARKit) to output Y.
        let x = translation.x
        let y = -translation.z

        // The camera looks along its local -Z axis. Column 2 is the camera's local +Z
        // axis in world coordinates, so negating it yields the forward direction in world.
        let forward = SIMD3<Float>(
            -transform.columns.2.x,
            -transform.columns.2.y,
            -transform.columns.2.z
        )

        // Yaw is measured in the horizontal plane relative to the app's output axes:
        // x_out = world X, y_out = -world Z. This makes yaw = 0 at session start when
        // the phone is looking straight ahead.
        let yaw = atan2(forward.x, -forward.z)

        return PlanarPose(x: x, y: y, yaw: yaw)
    }

    private static func poseText(for pose: PlanarPose) -> String {
        String(format: "x=%.4f y=%.4f yaw=%.4f", pose.x, pose.y, pose.yaw)
    }
}

private struct PlanarPose {
    let x: Float
    let y: Float
    let yaw: Float

    func roundedTo4Decimals() -> PlanarPose {
        PlanarPose(
            x: Self.rounded(x),
            y: Self.rounded(y),
            yaw: Self.rounded(yaw)
        )
    }

    private static func rounded(_ value: Float) -> Float {
        (value * 10_000).rounded() / 10_000
    }
}

private struct PosePayload: Codable {
    let x: Float
    let y: Float
    let yaw: Float
}
