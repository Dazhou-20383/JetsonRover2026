import CoreLocation
import MapKit
import SwiftUI
import UIKit

// MARK: - Root

/// Full-screen map with a floating status pill and a Maps-style bottom
/// sheet. Views that read the 5 Hz pose (`TrackingCard`, `StatusPill`)
/// observe `ARSessionManager` themselves, so pose updates only redraw
/// those small views — never the map or the whole sheet.
struct CombinedNavigationView: View {
    @EnvironmentObject private var viewModel: MapViewModel
    @State private var sheetDetent: PresentationDetent = Self.peekDetent

    private static let peekDetent = PresentationDetent.height(190)

    var body: some View {
        ZStack(alignment: .top) {
            WaypointMapView(
                selectedCoordinate: $viewModel.selectedCoordinate,
                userLocation: viewModel.currentCoordinate,
                hasCenteredOnUser: $viewModel.hasCenteredOnUser,
                locationStore: viewModel.locationManager,
                routePolyline: viewModel.plannedRoute?.polyline,
                onLongPress: viewModel.selectWaypoint(at:),
                recenterTrigger: viewModel.recenterRequestID
            )
            .ignoresSafeArea()

            HStack(alignment: .top) {
                StatusPill()
                Spacer(minLength: 12)
                MapButton(systemImage: "location.fill", label: "Recenter on my location") {
                    viewModel.recenterOnUser()
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
        }
        .onAppear(perform: viewModel.onAppear)
        .onDisappear(perform: viewModel.onDisappear)
        .onChange(of: viewModel.selectedCoordinate != nil) { _, hasGoal in
            if hasGoal && sheetDetent == Self.peekDetent {
                withAnimation { sheetDetent = .medium }
            }
        }
        .sheet(isPresented: .constant(true)) {
            ControlSheet()
                .presentationDetents([Self.peekDetent, .medium, .large], selection: $sheetDetent)
                .presentationBackgroundInteraction(.enabled(upThrough: .medium))
                .presentationDragIndicator(.visible)
                .presentationCornerRadius(28)
                .presentationBackground(Color(.systemGroupedBackground))
                .interactiveDismissDisabled()
        }
    }
}

// MARK: - Floating controls

private struct StatusPill: View {
    @EnvironmentObject private var connection: ConnectionManager
    @EnvironmentObject private var session: ARSessionManager

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "circle.fill")
                .font(.system(size: 9))
                .foregroundStyle(color)
                .symbolEffect(.pulse, isActive: connection.state == .connecting)
            Text(title)
                .font(.subheadline.weight(.semibold))
                .lineLimit(1)
        }
        .padding(.horizontal, 14)
        .frame(height: 44)
        .background(.regularMaterial, in: Capsule())
        .shadow(color: .black.opacity(0.12), radius: 8, y: 2)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Status: \(title)")
    }

    private var title: String {
        switch connection.state {
        case .disconnected: return "Not connected"
        case .connecting: return "Connecting…"
        case .failed: return "Connection failed"
        case .connected:
            switch session.trackingLevel {
            case .off: return "Connected"
            case .starting: return "Connected · Starting AR"
            case .limited: return "Connected · Tracking limited"
            case .normal: return "Connected · Tracking"
            case .failed: return "Connected · AR error"
            }
        }
    }

    private var color: Color {
        switch connection.state {
        case .disconnected: return .gray
        case .connecting: return .blue
        case .failed: return .red
        case .connected:
            switch session.trackingLevel {
            case .normal: return .green
            case .failed: return .red
            default: return .orange
            }
        }
    }
}

private struct MapButton: View {
    let systemImage: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(.tint)
                .frame(width: 44, height: 44)
                .background(.regularMaterial, in: Circle())
                .shadow(color: .black.opacity(0.12), radius: 8, y: 2)
        }
        .accessibilityLabel(label)
    }
}

// MARK: - Bottom sheet

private struct ControlSheet: View {
    @EnvironmentObject private var connection: ConnectionManager
    @EnvironmentObject private var viewModel: MapViewModel
    @State private var isShowingLog = false

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                ConnectionCard()

                if connection.isConnected {
                    TrackingCard()
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }

                LocationDeniedBanner(locationManager: viewModel.locationManager)

                GoalCard()

                if viewModel.selectedCoordinate != nil {
                    RouteCard()
                }

                DetailsCard(locationManager: viewModel.locationManager)

                Button {
                    isShowingLog = true
                } label: {
                    Label("Debug log", systemImage: "text.alignleft")
                        .font(.subheadline.weight(.medium))
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
                .tint(.secondary)
            }
            .padding(.horizontal, 16)
            .padding(.top, 22)
            .padding(.bottom, 24)
            .animation(.snappy, value: connection.isConnected)
        }
        .scrollBounceBehavior(.basedOnSize)
        .sheet(isPresented: $isShowingLog) {
            DebugLogView()
        }
    }
}

private struct ConnectionCard: View {
    @EnvironmentObject private var connection: ConnectionManager

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                Circle().fill(tint.opacity(0.15))
                Image(systemName: icon)
                    .font(.system(size: 19, weight: .semibold))
                    .foregroundStyle(tint)
                    .symbolEffect(.variableColor.iterative, isActive: connection.state == .connecting)
            }
            .frame(width: 46, height: 46)
            .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 2) {
                Text("Jetson rover")
                    .font(.headline)
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(isFailed ? AnyShapeStyle(.red) : AnyShapeStyle(.secondary))
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 8)

            connectButton
        }
        .card()
        .sensoryFeedback(trigger: connection.state) { _, newState in
            switch newState {
            case .connected: return .success
            case .failed: return .error
            default: return nil
            }
        }
    }

    @ViewBuilder
    private var connectButton: some View {
        switch connection.state {
        case .disconnected, .failed:
            Button(isFailed ? "Retry" : "Connect") {
                connection.connect()
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .fontWeight(.semibold)
        case .connecting:
            Button {} label: {
                HStack(spacing: 8) {
                    ProgressView()
                    Text("Connecting")
                }
            }
            .buttonStyle(.bordered)
            .controlSize(.large)
            .disabled(true)
            .accessibilityLabel("Connecting")
        case .connected:
            Button("Disconnect", role: .destructive) {
                connection.disconnect()
            }
            .buttonStyle(.bordered)
            .controlSize(.large)
        }
    }

    private var isFailed: Bool {
        if case .failed = connection.state { return true }
        return false
    }

    private var subtitle: String {
        switch connection.state {
        case .disconnected: return "Not connected · \(connection.host)"
        case .connecting: return "Reaching \(connection.host)…"
        case .connected: return "Streaming pose to \(connection.host)"
        case .failed(let message): return message
        }
    }

    private var icon: String {
        switch connection.state {
        case .disconnected: return "antenna.radiowaves.left.and.right.slash"
        case .connecting, .connected: return "antenna.radiowaves.left.and.right"
        case .failed: return "exclamationmark.triangle.fill"
        }
    }

    private var tint: Color {
        switch connection.state {
        case .disconnected: return .gray
        case .connecting: return .blue
        case .connected: return .green
        case .failed: return .red
        }
    }
}

private struct TrackingCard: View {
    @EnvironmentObject private var session: ARSessionManager

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Label {
                Text(session.statusText)
            } icon: {
                Image(systemName: trackingIcon)
                    .foregroundStyle(trackingColor)
            }
            .font(.subheadline.weight(.medium))

            HStack(spacing: 10) {
                StatTile(title: "X", value: String(format: "%.2f", session.x), unit: "m")
                StatTile(title: "Y", value: String(format: "%.2f", session.y), unit: "m")
                StatTile(title: "Yaw", value: String(format: "%.0f", session.yaw * 180 / .pi), unit: "°")
            }

            Divider()

            Toggle(isOn: $session.isCameraStreamEnabled) {
                VStack(alignment: .leading, spacing: 2) {
                    Label("Stream iPhone camera", systemImage: "video.fill")
                        .font(.subheadline.weight(.medium))
                    Text(cameraCaption)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .disabled(!session.isRunning || session.trackingLevel == .failed)
        }
        .card()
    }

    private var cameraCaption: String {
        guard session.isCameraStreamEnabled else {
            return "Off. Turn on only if the rover has no camera of its own — it uses extra battery."
        }
        if let kb = session.cameraFrameKB {
            return "Streaming 5 fps · \(kb) KB/frame"
        }
        return session.cameraStatusText
    }

    private var trackingIcon: String {
        switch session.trackingLevel {
        case .normal: return "checkmark.circle.fill"
        case .failed: return "xmark.octagon.fill"
        case .off: return "pause.circle.fill"
        case .starting, .limited: return "exclamationmark.circle.fill"
        }
    }

    private var trackingColor: Color {
        switch session.trackingLevel {
        case .normal: return .green
        case .failed: return .red
        case .off: return .gray
        case .starting, .limited: return .orange
        }
    }
}

private struct StatTile: View {
    let title: String
    let value: String
    let unit: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(value)
                    .font(.title3.weight(.semibold).monospacedDigit())
                Text(unit)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .lineLimit(1)
            .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(Color(.tertiarySystemFill), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .accessibilityElement(children: .combine)
    }
}

private struct LocationDeniedBanner: View {
    @ObservedObject var locationManager: LocationManager

    var body: some View {
        if locationManager.isAuthorizationDenied {
            HStack(spacing: 12) {
                Image(systemName: "location.slash.fill")
                    .foregroundStyle(.orange)
                Text("Location is off, so goals can't be routed.")
                    .font(.subheadline)
                Spacer(minLength: 8)
                Button("Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) {
                        UIApplication.shared.open(url)
                    }
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
            .card()
        }
    }
}

private struct GoalCard: View {
    @EnvironmentObject private var viewModel: MapViewModel
    @EnvironmentObject private var connection: ConnectionManager

    var body: some View {
        if viewModel.selectedCoordinate == nil {
            HStack(spacing: 14) {
                Image(systemName: "hand.tap.fill")
                    .font(.title2)
                    .foregroundStyle(.tint)
                    .frame(width: 46)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text("No goal set")
                        .font(.headline)
                    Text("Long-press anywhere on the map to drop a goal.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
            }
            .card()
        } else {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    Label("Goal", systemImage: "flag.fill")
                        .font(.headline)
                    Spacer()
                    Button {
                        viewModel.clearWaypoint()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title2)
                            .symbolRenderingMode(.hierarchical)
                            .foregroundStyle(.secondary)
                    }
                    .accessibilityLabel("Clear goal")
                }

                HStack(alignment: .top, spacing: 12) {
                    BigValue(title: "Distance", value: viewModel.distanceText)
                    BigValue(title: "Bearing", value: viewModel.absoluteDirectionText)
                }

                Text("\(viewModel.selectedLatitudeText), \(viewModel.selectedLongitudeText)")
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)

                Button {
                    viewModel.sendGoal()
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: connection.isConnected ? "paperplane.fill" : "antenna.radiowaves.left.and.right.slash")
                        Text(sendTitle)
                    }
                    .fontWeight(.semibold)
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(!connection.isConnected || viewModel.isPlanningRoute || !viewModel.canSendGoal)

                Text(viewModel.statusMessage)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .card()
        }
    }

    private var sendTitle: String {
        if !connection.isConnected { return "Connect to send" }
        if viewModel.isPlanningRoute { return "Waiting for route…" }
        return viewModel.plannedRoute == nil ? "Send goal only" : "Send goal + route"
    }
}

private struct BigValue: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title3.weight(.semibold).monospacedDigit())
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

private struct RouteCard: View {
    @EnvironmentObject private var viewModel: MapViewModel
    @State private var isShowingSteps = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label("Route", systemImage: "point.topleft.down.to.point.bottomright.curvepath.fill")
                    .font(.headline)
                Spacer()
                if !viewModel.isPlanningRoute {
                    Button {
                        viewModel.planRoute()
                    } label: {
                        Label(viewModel.plannedRoute == nil ? "Plan" : "Re-plan", systemImage: "arrow.clockwise")
                            .font(.subheadline.weight(.medium))
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
            }

            if viewModel.isPlanningRoute {
                HStack(spacing: 10) {
                    ProgressView()
                    Text("Planning walking route…")
                        .foregroundStyle(.secondary)
                }
            } else if let error = viewModel.routeError {
                Label {
                    Text(error)
                        .fixedSize(horizontal: false, vertical: true)
                } icon: {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                }
                .font(.subheadline)
            } else if let summary = viewModel.routeSummaryText {
                Text(summary)
                    .font(.title3.weight(.semibold).monospacedDigit())

                if let guidance = viewModel.routeGuidance {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "arrow.triangle.turn.up.right.diamond.fill")
                            .font(.title2)
                            .foregroundStyle(.blue)
                            .frame(width: 32)
                            .accessibilityHidden(true)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(guidance.instructions)
                                .font(.body.weight(.semibold))
                            Text("\(guidance.distanceToNextLandmarkText) · \(guidance.absoluteDirectionText)")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }

            if !viewModel.isPlanningRoute && !viewModel.routeInstructionBuffer.isEmpty {
                DisclosureGroup(isExpanded: $isShowingSteps) {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(viewModel.routeInstructionBuffer) { step in
                            HStack(alignment: .firstTextBaseline, spacing: 10) {
                                Text("\(step.id + 1)")
                                    .font(.caption.weight(.bold).monospacedDigit())
                                    .foregroundStyle(.secondary)
                                    .frame(width: 18, alignment: .trailing)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(step.instruction)
                                        .font(.subheadline)
                                    Text("\(step.distanceText) · \(step.directionText)")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    .padding(.top, 8)
                } label: {
                    Text("All steps (\(viewModel.routeInstructionBuffer.count))")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.primary)
                }
            }
        }
        .card()
    }
}

private struct DetailsCard: View {
    @EnvironmentObject private var viewModel: MapViewModel
    @ObservedObject var locationManager: LocationManager
    @State private var isExpanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            VStack(alignment: .leading, spacing: 10) {
                MetricRow(title: "Latitude", value: viewModel.currentLatitudeText)
                MetricRow(title: "Longitude", value: viewModel.currentLongitudeText)
                MetricRow(title: "Heading", value: viewModel.headingText)

                if !viewModel.jsonPreview.isEmpty {
                    CodeBlock(title: "Goal payload", text: viewModel.jsonPreview)
                }
                if !viewModel.routeInstructionBuffer.isEmpty {
                    CodeBlock(title: "Route array", text: viewModel.routeArrayText)
                }
            }
            .padding(.top, 10)
        } label: {
            Label("My position & payloads", systemImage: "info.circle")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.primary)
        }
        .card()
    }
}

private struct MetricRow: View {
    let title: String
    let value: String

    var body: some View {
        HStack {
            Text(title)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .font(.subheadline.monospacedDigit())
                .textSelection(.enabled)
        }
        .accessibilityElement(children: .combine)
    }
}

private struct CodeBlock: View {
    let title: String
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            ScrollView(.horizontal) {
                Text(text)
                    .font(.caption.monospaced())
                    .textSelection(.enabled)
                    .padding(10)
            }
            .frame(maxHeight: 160)
            .background(Color(.tertiarySystemFill), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
    }
}

private struct DebugLogView: View {
    @EnvironmentObject private var debugLogStore: DebugLogStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if debugLogStore.entries.isEmpty {
                    ContentUnavailableView("No events yet", systemImage: "text.alignleft")
                } else {
                    List {
                        // Newest first, so the latest event is always visible.
                        ForEach(Array(debugLogStore.entries.enumerated().reversed()), id: \.offset) { _, entry in
                            Text(entry)
                                .font(.caption.monospaced())
                                .textSelection(.enabled)
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Debug log")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        UIPasteboard.general.string = debugLogStore.entries.joined(separator: "\n")
                    } label: {
                        Image(systemName: "doc.on.doc")
                    }
                    .accessibilityLabel("Copy log")
                    .disabled(debugLogStore.entries.isEmpty)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

private extension View {
    func card() -> some View {
        padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                Color(.secondarySystemGroupedBackground),
                in: RoundedRectangle(cornerRadius: 20, style: .continuous)
            )
    }
}

// MARK: - Map

private struct WaypointMapView: UIViewRepresentable {
    @Binding var selectedCoordinate: CLLocationCoordinate2D?
    let userLocation: CLLocationCoordinate2D?
    @Binding var hasCenteredOnUser: Bool
    let locationStore: LocationManager
    let routePolyline: MKPolyline?
    let onLongPress: (CLLocationCoordinate2D) -> Void
    let recenterTrigger: Int

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView(frame: .zero)
        mapView.delegate = context.coordinator
        mapView.showsUserLocation = true
        mapView.showsCompass = false
        mapView.userTrackingMode = .follow
        mapView.pointOfInterestFilter = .excludingAll
        mapView.isRotateEnabled = false

        let longPress = UILongPressGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleLongPress(_:))
        )
        longPress.minimumPressDuration = 0.5
        mapView.addGestureRecognizer(longPress)

        return mapView
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        context.coordinator.parent = self
        context.coordinator.updateSelectedAnnotation(on: mapView)
        if context.coordinator.updateRouteOverlay(on: mapView, polyline: routePolyline) {
            // Just framed the new route; don't let the first-fix auto-center
            // snap the map back to the user.
            if !hasCenteredOnUser {
                DispatchQueue.main.async { hasCenteredOnUser = true }
            }
            return
        }

        if context.coordinator.lastRecenterTrigger != recenterTrigger {
            context.coordinator.lastRecenterTrigger = recenterTrigger
            centerMap(on: mapView, coordinate: userLocation, animated: true)
            return
        }

        guard let userLocation else { return }
        guard !hasCenteredOnUser else { return }

        centerMap(on: mapView, coordinate: userLocation, animated: true)
    }

    private func centerMap(
        on mapView: MKMapView,
        coordinate: CLLocationCoordinate2D?,
        animated: Bool
    ) {
        guard let coordinate else { return }

        let region = MKCoordinateRegion(
            center: coordinate,
            latitudinalMeters: 120,
            longitudinalMeters: 120
        )
        mapView.setRegion(region, animated: animated)

        DispatchQueue.main.async {
            hasCenteredOnUser = true
        }
    }

    final class Coordinator: NSObject, MKMapViewDelegate {
        var parent: WaypointMapView
        var lastRecenterTrigger: Int
        private let annotation = MKPointAnnotation()
        private var routeOverlay: MKPolyline?

        init(_ parent: WaypointMapView) {
            self.parent = parent
            lastRecenterTrigger = parent.recenterTrigger
        }

        func mapView(_ mapView: MKMapView, didUpdate userLocation: MKUserLocation) {
            parent.locationStore.update(location: userLocation.location)
        }

        @objc
        func handleLongPress(_ gesture: UILongPressGestureRecognizer) {
            guard gesture.state == .began,
                  let mapView = gesture.view as? MKMapView
            else {
                return
            }

            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            let point = gesture.location(in: mapView)
            let coordinate = mapView.convert(point, toCoordinateFrom: mapView)
            parent.onLongPress(coordinate)
        }

        func updateSelectedAnnotation(on mapView: MKMapView) {
            if let coordinate = parent.selectedCoordinate {
                annotation.coordinate = coordinate
                annotation.title = "Goal"

                if !mapView.annotations.contains(where: { $0 === annotation }) {
                    mapView.addAnnotation(annotation)
                }
            } else {
                mapView.removeAnnotation(annotation)
            }
        }

        /// Swaps the route overlay when the planned route changes. Returns
        /// true when a new route was added (and the map was zoomed to it).
        func updateRouteOverlay(on mapView: MKMapView, polyline: MKPolyline?) -> Bool {
            guard routeOverlay !== polyline else { return false }

            if let routeOverlay {
                mapView.removeOverlay(routeOverlay)
            }
            routeOverlay = polyline
            guard let polyline else { return false }

            mapView.addOverlay(polyline, level: .aboveRoads)
            // Leave room for the status pill on top and the bottom sheet,
            // which covers roughly the lower half at its medium detent.
            let padding = UIEdgeInsets(
                top: 90,
                left: 40,
                bottom: mapView.bounds.height * 0.5 + 24,
                right: 40
            )
            mapView.setVisibleMapRect(polyline.boundingMapRect, edgePadding: padding, animated: true)
            return true
        }

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            guard let polyline = overlay as? MKPolyline else {
                return MKOverlayRenderer(overlay: overlay)
            }
            let renderer = MKPolylineRenderer(polyline: polyline)
            renderer.strokeColor = .systemBlue
            renderer.lineWidth = 6
            renderer.lineCap = .round
            renderer.lineJoin = .round
            return renderer
        }

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            guard !(annotation is MKUserLocation) else {
                return nil
            }

            let identifier = "WaypointPin"
            let view = mapView.dequeueReusableAnnotationView(withIdentifier: identifier) as? MKMarkerAnnotationView
                ?? MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: identifier)

            view.annotation = annotation
            view.canShowCallout = false
            view.markerTintColor = .systemBlue
            view.glyphImage = UIImage(systemName: "flag.fill")
            view.animatesWhenAdded = true
            return view
        }
    }
}
