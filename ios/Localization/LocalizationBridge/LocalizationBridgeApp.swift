import SwiftUI

@main
struct LocalizationBridgeApp: App {
    @StateObject private var debugLogStore: DebugLogStore
    @StateObject private var sessionManager: ARSessionManager
    @StateObject private var mapViewModel: MapViewModel

    init() {
        // Replace with the Jetson's USB-tether network address.
        //
        // Pose and waypoint/route traffic use separate sockets and separate
        // transports: AR pose is a lossy, latency-sensitive 5 Hz stream where
        // a dropped sample is immediately superseded by the next one, so it
        // stays on UDP. A manual goal or MapKit-derived route guide is a
        // rare, one-shot message where silent loss is a real problem, so it
        // goes over TCP instead. Keeping them on separate sockets also means
        // a slow/blocked waypoint send can no longer delay the pose stream.
        let debugLogStore = DebugLogStore()
        let poseNetworkManager = try! NetworkManager(
            host: "10.42.0.1",
            port: 5005,
            transport: .udp
        )
        let waypointNetworkManager = try! NetworkManager(
            host: "10.42.0.1",
            port: 5006,
            transport: .tcp
        )
        _debugLogStore = StateObject(wrappedValue: debugLogStore)
        _sessionManager = StateObject(
            wrappedValue: ARSessionManager(
                networkManager: poseNetworkManager,
                debugLogStore: debugLogStore,
                targetHz: 5
            )
        )
        _mapViewModel = StateObject(
            wrappedValue: MapViewModel(
                networkManager: waypointNetworkManager,
                debugLogStore: debugLogStore
            )
        )
    }

    var body: some Scene {
        WindowGroup {
            NavigationStack {
                CombinedNavigationView()
                    .environmentObject(sessionManager)
                    .environmentObject(mapViewModel)
                    .environmentObject(debugLogStore)
            }
            .onAppear {
                sessionManager.start {
                    mapViewModel.locationManager.requestAuthorization()
                }
            }
        }
    }
}
