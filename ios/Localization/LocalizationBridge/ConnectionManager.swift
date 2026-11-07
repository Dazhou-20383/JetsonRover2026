import Combine
import Foundation
import UIKit

/// Owns the user-driven link to the Jetson. Nothing power-hungry runs until
/// the user taps Connect: on success the TCP waypoint channel is open and
/// ARKit pose tracking starts; on disconnect (explicit or a dropped link)
/// ARKit and the optional camera stream are stopped again.
@MainActor
final class ConnectionManager: ObservableObject {
    enum State: Equatable {
        case disconnected
        case connecting
        case connected
        case failed(String)
    }

    @Published private(set) var state: State = .disconnected

    var host: String { waypointNetwork.host }
    var isConnected: Bool { state == .connected }

    private let waypointNetwork: NetworkManager
    private let sessionManager: ARSessionManager
    private let debugLogStore: DebugLogStore

    init(waypointNetwork: NetworkManager, sessionManager: ARSessionManager, debugLogStore: DebugLogStore) {
        self.waypointNetwork = waypointNetwork
        self.sessionManager = sessionManager
        self.debugLogStore = debugLogStore

        waypointNetwork.onDisconnect = { [weak self] error in
            let message = error.localizedDescription
            Task { @MainActor [weak self] in
                self?.handleLinkLost(message)
            }
        }
    }

    func connect() {
        switch state {
        case .connecting, .connected:
            return
        case .disconnected, .failed:
            break
        }

        state = .connecting
        debugLogStore.append("Link: connecting to \(host)")
        let network = waypointNetwork

        Task {
            do {
                // Blocking connect (bounded timeout) off the main thread.
                try await Task.detached(priority: .userInitiated) {
                    try network.connect()
                }.value
                guard state == .connecting else {
                    network.disconnect()
                    return
                }
                state = .connected
                debugLogStore.append("Link: connected")
                sessionManager.start()
                // The phone rides on the rover: if the screen auto-locks,
                // iOS suspends the app and the pose stream stops.
                UIApplication.shared.isIdleTimerDisabled = true
            } catch {
                guard state == .connecting else { return }
                state = .failed(error.localizedDescription)
                debugLogStore.append("Link: connect failed - \(error.localizedDescription)")
            }
        }
    }

    func disconnect() {
        waypointNetwork.disconnect()
        tearDown()
        state = .disconnected
        debugLogStore.append("Link: disconnected")
    }

    private func handleLinkLost(_ message: String) {
        guard state == .connected else { return }
        tearDown()
        state = .failed(message)
        debugLogStore.append("Link: lost - \(message)")
    }

    private func tearDown() {
        if sessionManager.isRunning {
            sessionManager.stop()
        }
        UIApplication.shared.isIdleTimerDisabled = false
    }
}
