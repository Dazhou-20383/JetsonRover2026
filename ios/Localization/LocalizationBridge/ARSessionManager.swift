import ARKit
import AVFoundation
import Combine
import CoreImage
import Foundation
import OSLog
import UIKit
import simd

/// Drives ARKit for pose tracking and, only when the user turns it on,
/// streams a downsampled JPEG of each ARKit camera frame to the Jetson.
///
/// The session only runs while connected to the Jetson (see
/// `ConnectionManager`), so the camera, ISP and VIO pipeline are fully off
/// otherwise. There is no on-screen AR view: rendering the camera feed
/// underneath the (opaque) map was pure GPU cost.
///
/// ARKit's world-tracking session exclusively owns the camera and only ever
/// uses the standard wide (1x) lens, so the optional camera stream reuses
/// `ARFrame.capturedImage` rather than opening a second capture session.
final class ARSessionManager: NSObject, ObservableObject, ARSessionDelegate {
    enum TrackingLevel: Equatable {
        case off
        case starting
        case limited
        case normal
        case failed
    }

    @Published private(set) var x: Float = 0
    @Published private(set) var y: Float = 0
    @Published private(set) var yaw: Float = 0
    @Published private(set) var trackingLevel: TrackingLevel = .off
    @Published private(set) var statusText: String = "Pose tracking is off."
    @Published private(set) var cameraStatusText: String = "Off"
    @Published private(set) var cameraFrameKB: Int?

    /// User-controlled; the camera stream is never turned on automatically.
    @Published var isCameraStreamEnabled = false {
        didSet {
            guard oldValue != isCameraStreamEnabled else { return }
            cameraFrameKB = nil
            cameraStatusText = isCameraStreamEnabled ? "Waiting for frames…" : "Off"
            debugLogStore.append("Camera: stream \(isCameraStreamEnabled ? "enabled" : "disabled")")
        }
    }

    var isRunning: Bool { trackingLevel != .off }

    let session = ARSession()

    private let networkManager: NetworkManager
    private let cameraNetworkManager: NetworkManager
    private let debugLogStore: DebugLogStore
    private let logger = Logger(subsystem: "iSLAM.LocalizationBridge", category: "ARSession")
    private let updateInterval: TimeInterval
    private var lastSentAt: TimeInterval = 0
    private var didReceiveFrame = false
    private var noFrameTimeoutWorkItem: DispatchWorkItem?
    private var lastPoseSendFailed = false

    // Reused across frames: CIContext creation is expensive.
    private let cameraContext = CIContext(options: [.cacheIntermediates: false])
    private let cameraFrameWidth: CGFloat = 320
    private let cameraJPEGQuality: CGFloat = 0.5
    /// Drop frames while one is still being encoded, so a slow encode can
    /// never pile up retained ARFrame buffers (which stalls ARKit).
    private var isEncodingCameraFrame = false

    init(
        networkManager: NetworkManager,
        cameraNetworkManager: NetworkManager,
        debugLogStore: DebugLogStore,
        targetHz: Double = 5
    ) {
        self.networkManager = networkManager
        self.cameraNetworkManager = cameraNetworkManager
        self.debugLogStore = debugLogStore
        updateInterval = 1.0 / max(targetHz, 1)
        super.init()
        session.delegate = self
    }

    // MARK: - Lifecycle

    func start() {
        guard !isRunning else { return }
        debugLogStore.append("AR: starting")

        guard ARWorldTrackingConfiguration.isSupported else {
            setStatus(.failed, "AR world tracking isn't supported on this device.")
            return
        }

        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            runSession()
        case .notDetermined:
            setStatus(.starting, "Requesting camera permission…")
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    guard let self, self.trackingLevel == .starting else { return }
                    if granted {
                        self.runSession()
                    } else {
                        self.setStatus(.failed, "Camera access denied. Enable it in Settings to track pose.")
                    }
                }
            }
        case .denied, .restricted:
            setStatus(.failed, "Camera access denied. Enable it in Settings to track pose.")
        @unknown default:
            setStatus(.failed, "Camera permission unavailable.")
        }
    }

    func stop() {
        noFrameTimeoutWorkItem?.cancel()
        session.pause()
        isCameraStreamEnabled = false
        setStatus(.off, "Pose tracking is off.")
        debugLogStore.append("AR: stopped")
    }

    private func runSession() {
        noFrameTimeoutWorkItem?.cancel()
        didReceiveFrame = false
        lastPoseSendFailed = false

        session.run(Self.lowPowerConfiguration(), options: [.resetTracking, .removeExistingAnchors])
        setStatus(.starting, "Starting pose tracking…")

        let timeoutWorkItem = DispatchWorkItem { [weak self] in
            guard let self, self.isRunning, !self.didReceiveFrame else { return }
            self.setStatus(.limited, "No camera frames yet. Make sure the rear camera isn't covered.")
        }
        noFrameTimeoutWorkItem = timeoutWorkItem
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.0, execute: timeoutWorkItem)
    }

    /// Pose-only tracking: no plane detection, environment texturing, or
    /// light estimation, and the lowest frame rate / resolution video
    /// format the device offers. The streamed camera image is downscaled to
    /// 320 px anyway, so a high-resolution capture buys nothing.
    private static func lowPowerConfiguration() -> ARWorldTrackingConfiguration {
        let configuration = ARWorldTrackingConfiguration()
        configuration.worldAlignment = .gravity
        configuration.planeDetection = []
        configuration.environmentTexturing = .none
        configuration.isLightEstimationEnabled = false
        configuration.providesAudioData = false

        let formats = ARWorldTrackingConfiguration.supportedVideoFormats
        if let format = formats.min(by: { lhs, rhs in
            if lhs.framesPerSecond != rhs.framesPerSecond {
                return lhs.framesPerSecond < rhs.framesPerSecond
            }
            return lhs.imageResolution.width * lhs.imageResolution.height
                < rhs.imageResolution.width * rhs.imageResolution.height
        }) {
            configuration.videoFormat = format
        }
        return configuration
    }

    private func setStatus(_ level: TrackingLevel, _ text: String) {
        trackingLevel = level
        statusText = text
        logger.info("\(text, privacy: .public)")
    }

    // MARK: - ARSessionDelegate

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        if !didReceiveFrame {
            didReceiveFrame = true
            debugLogStore.append("AR: first frame received")
        }

        let now = frame.timestamp
        guard now - lastSentAt >= updateInterval else { return }
        lastSentAt = now

        let pose = Self.extractPose(from: frame.camera.transform).roundedTo4Decimals()
        x = pose.x
        y = pose.y
        yaw = pose.yaw

        do {
            try networkManager.sendMessage(PosePayload(x: pose.x, y: pose.y, yaw: pose.yaw))
            if lastPoseSendFailed {
                lastPoseSendFailed = false
                debugLogStore.append("AR: pose sends recovered")
            }
        } catch {
            // Log once per failure streak rather than at 5 Hz.
            if !lastPoseSendFailed {
                lastPoseSendFailed = true
                debugLogStore.append("AR: pose send failed - \(error.localizedDescription)")
            }
        }

        if isCameraStreamEnabled && !isEncodingCameraFrame {
            streamCameraFrame(frame.capturedImage)
        }
    }

    private func streamCameraFrame(_ pixelBuffer: CVPixelBuffer) {
        isEncodingCameraFrame = true
        let context = cameraContext
        let targetWidth = cameraFrameWidth
        let quality = cameraJPEGQuality
        let cameraNetwork = cameraNetworkManager

        // JPEG encoding is real CPU work; keep it off the main thread.
        Task.detached(priority: .utility) { [weak self] in
            let outcome: Result<Int, CameraSendError>
            if let jpegData = Self.encodeJPEG(
                pixelBuffer: pixelBuffer,
                targetWidth: targetWidth,
                quality: quality,
                context: context
            ) {
                do {
                    try cameraNetwork.send(data: jpegData)
                    outcome = .success(jpegData.count)
                } catch {
                    outcome = .failure(CameraSendError(message: error.localizedDescription))
                }
            } else {
                outcome = .failure(CameraSendError(message: "Couldn't encode frame"))
            }

            await self?.finishCameraFrame(outcome)
        }
    }

    private func finishCameraFrame(_ outcome: Result<Int, CameraSendError>) {
        isEncodingCameraFrame = false
        guard isCameraStreamEnabled else { return }
        switch outcome {
        case .success(let bytes):
            cameraFrameKB = max(1, bytes / 1024)
            cameraStatusText = "Streaming"
        case .failure(let failure):
            cameraFrameKB = nil
            if cameraStatusText != failure.message {
                cameraStatusText = failure.message
                debugLogStore.append("Camera: \(failure.message)")
            }
        }
    }

    /// Downscales an ARKit camera frame and JPEG-encodes it for a single UDP
    /// datagram. `.oriented(.right)` corrects for the camera sensor's native
    /// landscape orientation, since the phone is used portrait.
    nonisolated private static func encodeJPEG(
        pixelBuffer: CVPixelBuffer,
        targetWidth: CGFloat,
        quality: CGFloat,
        context: CIContext
    ) -> Data? {
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer).oriented(.right)
        let extent = ciImage.extent
        guard extent.width > 0 else { return nil }

        let scale = targetWidth / extent.width
        let scaledImage = ciImage.transformed(by: CGAffineTransform(scaleX: scale, y: scale))

        guard let cgImage = context.createCGImage(scaledImage, from: scaledImage.extent) else {
            return nil
        }
        return UIImage(cgImage: cgImage).jpegData(compressionQuality: quality)
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        guard isRunning else { return }
        debugLogStore.append("AR: session failed - \(error.localizedDescription)")
        setStatus(.failed, "Tracking failed: \(error.localizedDescription)")
    }

    func sessionWasInterrupted(_ session: ARSession) {
        guard isRunning else { return }
        debugLogStore.append("AR: session interrupted")
        setStatus(.limited, "Tracking paused while the camera is unavailable.")
    }

    func sessionInterruptionEnded(_ session: ARSession) {
        guard isRunning else { return }
        debugLogStore.append("AR: interruption ended")
        setStatus(.starting, "Resuming tracking…")
    }

    func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
        guard isRunning else { return }

        switch camera.trackingState {
        case .normal:
            setStatus(.normal, "Tracking normally.")
        case .notAvailable:
            setStatus(.limited, "Tracking unavailable right now.")
        case .limited(let reason):
            let text: String
            switch reason {
            case .initializing:
                text = "Initializing — hold the phone steady."
            case .excessiveMotion:
                text = "Moving too fast — slow down."
            case .insufficientFeatures:
                text = "Not enough detail — point at textured surfaces in better light."
            case .relocalizing:
                text = "Relocalizing…"
            @unknown default:
                text = "Tracking limited."
            }
            setStatus(.limited, text)
        }
        debugLogStore.append("AR: \(statusText)")
    }

    // MARK: - Pose math

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

    func roundedTo4Decimals() -> PlanarPose {
        PlanarPose(x: Self.rounded(x), y: Self.rounded(y), yaw: Self.rounded(yaw))
    }

    private static func rounded(_ value: Float) -> Float {
        (value * 10_000).rounded() / 10_000
    }
}

private struct CameraSendError: Error {
    let message: String
}

private struct PosePayload: Codable {
    let x: Float
    let y: Float
    let yaw: Float
}
