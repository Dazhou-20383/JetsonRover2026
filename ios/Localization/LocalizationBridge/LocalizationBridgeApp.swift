import SwiftUI

@main
struct LocalizationBridgeApp: App {
    @StateObject private var debugLogStore: DebugLogStore
    @StateObject private var sessionManager: ARSessionManager
    @StateObject private var mapViewModel: MapViewModel
    @StateObject private var connectionManager: ConnectionManager

    init() {
        // The Jetson's Wi-Fi hotspot address (NetworkManager shared-mode default).
        let jetsonHost = "10.42.0.1"

        // Pose, waypoint/route, and camera traffic each use their own socket
        // and transport: AR pose is a lossy, latency-sensitive 5 Hz stream
        // where a dropped sample is immediately superseded by the next one,
        // so it stays on UDP. A manual goal or MapKit-derived route guide is
        // a rare, one-shot message where silent loss is a real problem, so
        // it goes over TCP, which also doubles as the "connected" signal for
        // the Connect button. The optional camera stream is one JPEG per UDP
        // datagram. None of these sockets touch the network at launch: the
        // TCP link only opens when the user taps Connect, so these inits only
        // fail on a malformed address literal.
        let debugLogStore = DebugLogStore()
        let poseNetwork = try! NetworkManager(host: jetsonHost, port: 5005, transport: .udp)
        let waypointNetwork = try! NetworkManager(host: jetsonHost, port: 5006, transport: .tcp)
        let cameraNetwork = try! NetworkManager(host: jetsonHost, port: 5007, transport: .udp)

        let sessionManager = ARSessionManager(
            networkManager: poseNetwork,
            cameraNetworkManager: cameraNetwork,
            debugLogStore: debugLogStore,
            targetHz: 5
        )

        _debugLogStore = StateObject(wrappedValue: debugLogStore)
        _sessionManager = StateObject(wrappedValue: sessionManager)
        _mapViewModel = StateObject(
            wrappedValue: MapViewModel(networkManager: waypointNetwork, debugLogStore: debugLogStore)
        )
        _connectionManager = StateObject(
            wrappedValue: ConnectionManager(
                waypointNetwork: waypointNetwork,
                sessionManager: sessionManager,
                debugLogStore: debugLogStore
            )
        )
    }

    var body: some Scene {
        WindowGroup {
            CombinedNavigationView()
                .environmentObject(sessionManager)
                .environmentObject(mapViewModel)
                .environmentObject(debugLogStore)
                .environmentObject(connectionManager)
                .onAppear {
                    // Only the map's location prompt at launch; the camera
                    // prompt comes later, when the user taps Connect.
                    mapViewModel.locationManager.requestAuthorization()
                }
        }
    }
}
