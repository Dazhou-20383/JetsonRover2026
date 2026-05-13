import ARKit
import Combine
import Foundation
import SceneKit
import SwiftUI

@main
struct LocalizationBridgeApp: App {
    @StateObject private var sessionManager: ARSessionManager

    init() {
        // Replace with the Jetson's USB-tether network address.
        let manager = try! ARSessionManager(host: "192.168.2.2", port: 5005, targetHz: 15)
        _sessionManager = StateObject(wrappedValue: manager)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(sessionManager)
        }
    }
}

private struct ContentView: View {
    @EnvironmentObject private var sessionManager: ARSessionManager

    var body: some View {
        ZStack(alignment: .topLeading) {
            CameraView(session: sessionManager.session)
                .ignoresSafeArea()

            DebugOverlay(
                x: sessionManager.x,
                y: sessionManager.y,
                yaw: sessionManager.yaw,
                statusText: sessionManager.statusText
            )
            .padding()
        }
        .onAppear {
            sessionManager.start()
        }
        .onDisappear {
            sessionManager.stop()
        }
    }
}

private struct CameraView: UIViewRepresentable {
    let session: ARSession

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        view.session = session
        view.automaticallyUpdatesLighting = false
        view.scene = SCNScene()
        return view
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {
        uiView.session = session
    }
}

private struct DebugOverlay: View {
    let x: Float
    let y: Float
    let yaw: Float
    let statusText: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(statusText)
                .font(.headline)
            Text(String(format: "x: %.3f m", x))
            Text(String(format: "y: %.3f m", y))
            Text(String(format: "yaw: %.3f rad", yaw))
        }
        .font(.system(.body, design: .monospaced))
        .foregroundStyle(.white)
        .padding(14)
        .background(.black.opacity(0.65), in: RoundedRectangle(cornerRadius: 12))
    }
}
