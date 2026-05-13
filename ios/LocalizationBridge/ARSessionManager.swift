import ARKit
import Combine
import Foundation
import simd

final class ARSessionManager: NSObject, ObservableObject, ARSessionDelegate {
    @Published private(set) var x: Float = 0
    @Published private(set) var y: Float = 0
    @Published private(set) var yaw: Float = 0
    @Published private(set) var statusText: String = "Starting AR session..."

    let session = ARSession()

    private let sender: PoseSender
    private let updateInterval: TimeInterval
    private var lastSentAt: TimeInterval = 0

    init(host: String, port: UInt16 = 5005, targetHz: Double = 15) throws {
        sender = try PoseSender(host: host, port: port)
        updateInterval = 1.0 / max(targetHz, 1)
        super.init()
        session.delegate = self
    }

    func start() {
        guard ARWorldTrackingConfiguration.isSupported else {
            statusText = "ARWorldTracking is not supported on this device."
            return
        }

        let configuration = ARWorldTrackingConfiguration()
        configuration.worldAlignment = .gravity

        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
        statusText = "Streaming pose over UDP"
    }

    func stop() {
        session.pause()
        statusText = "AR session paused"
    }

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        let now = frame.timestamp
        guard now - lastSentAt >= updateInterval else {
            return
        }
        lastSentAt = now

        let pose = Self.extractPose(from: frame.camera.transform)

        Task { @MainActor in
            x = pose.x
            y = pose.y
            yaw = pose.yaw
            sender.send(x: pose.x, y: pose.y, yaw: pose.yaw)
        }
    }

    func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
        let text: String

        switch camera.trackingState {
        case .normal:
            text = "Tracking normal"
        case .notAvailable:
            text = "Tracking unavailable"
        case .limited(let reason):
            switch reason {
            case .initializing:
                text = "Tracking initializing"
            case .excessiveMotion:
                text = "Tracking limited: excessive motion"
            case .insufficientFeatures:
                text = "Tracking limited: insufficient features"
            case .relocalizing:
                text = "Tracking limited: relocalizing"
            @unknown default:
                text = "Tracking limited"
            }
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
}

private struct PlanarPose {
    let x: Float
    let y: Float
    let yaw: Float
}
