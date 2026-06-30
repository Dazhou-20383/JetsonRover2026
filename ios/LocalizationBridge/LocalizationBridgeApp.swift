import SwiftUI

@main
struct LocalizationBridgeApp: App {
    @StateObject private var debugLogStore: DebugLogStore
    @StateObject private var sessionManager: ARSessionManager
    @StateObject private var mapViewModel: MapViewModel

    init() {
        // Replace with the Jetson's USB-tether network address.
        let debugLogStore = DebugLogStore()
        let networkManager = try! NetworkManager(
            host: "10.42.0.1",
            port: 5005,
            transport: .udp
        )
        _debugLogStore = StateObject(wrappedValue: debugLogStore)
        _sessionManager = StateObject(
            wrappedValue: ARSessionManager(
                networkManager: networkManager,
                debugLogStore: debugLogStore,
                targetHz: 5
            )
        )
        _mapViewModel = StateObject(
            wrappedValue: MapViewModel(
                networkManager: networkManager,
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
