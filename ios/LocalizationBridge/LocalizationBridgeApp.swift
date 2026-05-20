import SwiftUI

@main
struct LocalizationBridgeApp: App {
    @StateObject private var sessionManager: ARSessionManager
    @StateObject private var mapViewModel: MapViewModel

    init() {
        // Replace with the Jetson's USB-tether network address.
        let networkManager = try! NetworkManager(
            host: "10.42.0.1",
            port: 5005,
            transport: .udp
        )
        _sessionManager = StateObject(
            wrappedValue: ARSessionManager(networkManager: networkManager, targetHz: 5)
        )
        _mapViewModel = StateObject(wrappedValue: MapViewModel(networkManager: networkManager))
    }

    var body: some Scene {
        WindowGroup {
            NavigationStack {
                CombinedNavigationView()
                    .environmentObject(sessionManager)
                    .environmentObject(mapViewModel)
            }
            .onAppear(perform: sessionManager.start)
        }
    }
}
