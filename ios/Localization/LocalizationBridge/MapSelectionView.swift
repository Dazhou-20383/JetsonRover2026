import CoreLocation
import ARKit
import AVFoundation
import MapKit
import RealityKit
import SwiftUI

struct CombinedNavigationView: View {
    @EnvironmentObject private var sessionManager: ARSessionManager
    @EnvironmentObject private var viewModel: MapViewModel
    @EnvironmentObject private var debugLogStore: DebugLogStore

    var body: some View {
        ZStack {
            ARSessionView(session: sessionManager.session)
                .allowsHitTesting(false)
                .ignoresSafeArea()

            WaypointMapView(
                selectedCoordinate: $viewModel.selectedCoordinate,
                userLocation: viewModel.currentCoordinate,
                hasCenteredOnUser: $viewModel.hasCenteredOnUser,
                locationStore: viewModel.locationManager,
                onLongPress: viewModel.selectWaypoint(at:),
                recenterTrigger: viewModel.recenterRequestID
            )

            VStack {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 12) {
                        PoseOverlayCard(
                            poseText: sessionManager.latestPoseText,
                            statusText: sessionManager.statusText
                        )
                        PermissionBanner(message: viewModel.statusMessage)
                        DebugLogCard(entries: debugLogStore.entries)
                    }
                    .padding()

                    Spacer()

                    RecenterButton(action: viewModel.recenterOnUser)
                        .padding()
                }
                Spacer()
            }
        }
        .navigationTitle("Localization Bridge")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear(perform: viewModel.onAppear)
        .onDisappear(perform: viewModel.onDisappear)
        .safeAreaInset(edge: .bottom) {
            ScrollView {
                BottomControlPanel(
                    currentLatitudeText: viewModel.currentLatitudeText,
                    currentLongitudeText: viewModel.currentLongitudeText,
                    headingText: viewModel.headingText,
                    selectedLatitudeText: viewModel.selectedLatitudeText,
                    selectedLongitudeText: viewModel.selectedLongitudeText,
                    distanceText: viewModel.distanceText,
                    absoluteDirectionText: viewModel.absoluteDirectionText,
                    jsonPreview: viewModel.jsonPreview,
                    nextStepBuffer: viewModel.nextStepBuffer,
                    routeArrayText: viewModel.routeArrayText,
                    routeInstructionBuffer: viewModel.routeInstructionBuffer,
                    routeGuidance: viewModel.routeGuidance,
                    isPlanningRoute: viewModel.isPlanningRoute,
                    canSendGoal: viewModel.canSendGoal,
                    sendGoal: {
                        Task {
                            _ = await viewModel.sendGoal()
                        }
                    }
                )
            }
            .scrollIndicators(.visible)
            .frame(maxHeight: 340)
        }
    }
}

private struct ARSessionView: UIViewRepresentable {
    let session: ARSession

    func makeUIView(context: Context) -> ARView {
        let view = ARView(frame: .zero)
        view.automaticallyConfigureSession = false
        view.session = session
        view.environment.background = .color(.clear)
        view.isUserInteractionEnabled = false
        return view
    }

    func updateUIView(_ uiView: ARView, context: Context) {
        if uiView.session !== session {
            uiView.session = session
        }
    }
}

private struct MetricRow: View {
    let title: String
    let value: String

    var body: some View {
        HStack {
            Text(title)
                .font(.headline)
            Spacer()
            Text(value)
                .font(.system(.body, design: .monospaced))
                .foregroundStyle(.secondary)
        }
    }
}

private struct PermissionBanner: View {
    let message: String

    var body: some View {
        Text(message)
            .font(.subheadline.weight(.medium))
            .foregroundStyle(.primary)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }
}

private struct DebugLogCard: View {
    let entries: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Debug Log")
                .font(.headline)

            if entries.isEmpty {
                Text("Waiting for events...")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(Array(entries.enumerated()), id: \.offset) { index, entry in
                                Text(entry)
                                    .font(.caption.monospaced())
                                    .foregroundStyle(.secondary)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .id(index)
                            }
                        }
                        .onChange(of: entries.count) { _, _ in
                            guard let lastIndex = entries.indices.last else { return }
                            withAnimation {
                                proxy.scrollTo(lastIndex, anchor: .bottom)
                            }
                        }
                    }
                }
                .frame(maxHeight: 120)
            }
        }
        .padding(12)
        .frame(maxWidth: 260)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }
}

private struct PoseOverlayCard: View {
    let poseText: String
    let statusText: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Pose Stream")
                .font(.headline)
            Text(poseText)
                .font(.system(.subheadline, design: .monospaced))
            Text(statusText)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(14)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }
}

private struct RecenterButton: View {
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: "location.fill")
                .font(.headline)
                .foregroundStyle(.primary)
                .frame(width: 44, height: 44)
                .background(.ultraThinMaterial, in: Circle())
        }
        .accessibilityLabel("Recenter on current location")
    }
}

private struct BottomControlPanel: View {
    let currentLatitudeText: String
    let currentLongitudeText: String
    let headingText: String
    let selectedLatitudeText: String
    let selectedLongitudeText: String
    let distanceText: String
    let absoluteDirectionText: String
    let jsonPreview: String
    let nextStepBuffer: MapViewModel.BufferedStep?
    let routeArrayText: String
    let routeInstructionBuffer: [MapViewModel.RouteInstruction]
    let routeGuidance: MapViewModel.RouteGuidance?
    let isPlanningRoute: Bool
    let canSendGoal: Bool
    let sendGoal: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 10) {
                Text("Current Position")
                    .font(.headline)
                MetricRow(title: "Latitude", value: currentLatitudeText)
                MetricRow(title: "Longitude", value: currentLongitudeText)
                MetricRow(title: "Heading", value: headingText)
            }

            Divider()

            VStack(alignment: .leading, spacing: 10) {
                Text("Selected Waypoint")
                    .font(.headline)
                MetricRow(title: "Latitude", value: selectedLatitudeText)
                MetricRow(title: "Longitude", value: selectedLongitudeText)
                MetricRow(title: "Distance", value: distanceText)
                MetricRow(title: "Direction", value: absoluteDirectionText)
            }

            if !jsonPreview.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Waypoint JSON")
                        .font(.headline)
                    ScrollView(.horizontal, showsIndicators: true) {
                        Text(jsonPreview)
                            .font(.system(.footnote, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: 120)
                    .padding(12)
                    .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
                }
            }

            if let nextStepBuffer {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Next Step Buffer")
                        .font(.headline)
                    MetricRow(title: "Landmark", value: nextStepBuffer.landmarkText)
                    MetricRow(title: "Distance", value: nextStepBuffer.distanceText)

                    Text(nextStepBuffer.instruction)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            if !routeInstructionBuffer.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Route Array")
                        .font(.headline)
                    ScrollView(.horizontal, showsIndicators: true) {
                        Text(routeArrayText)
                            .font(.system(.footnote, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: 80)
                    .padding(12)
                    .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))

                    Text("Route Instruction Buffer")
                        .font(.headline)

                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(routeInstructionBuffer) { step in
                            HStack(alignment: .top, spacing: 10) {
                                Text("\(step.id + 1).")
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(.secondary)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(step.instruction)
                                        .font(.subheadline)
                                    Text(step.distanceText)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    .padding(12)
                    .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
                }
            }

            if isPlanningRoute || routeGuidance != nil {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Route Guidance")
                        .font(.headline)

                    if isPlanningRoute {
                        HStack(spacing: 10) {
                            ProgressView()
                            Text("Planning route to the waypoint...")
                                .foregroundStyle(.secondary)
                        }
                    } else if let routeGuidance {
                        MetricRow(title: "Next Landmark", value: routeGuidance.intersectionName)
                        MetricRow(title: "Distance", value: routeGuidance.distanceToNextLandmarkText)
                        MetricRow(title: "Turn", value: routeGuidance.absoluteDirectionText)

                        Text(routeGuidance.instructions)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Button(action: sendGoal) {
                Label("Send Goal", systemImage: "paperplane.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!canSendGoal)
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 12)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 20))
        .overlay {
            RoundedRectangle(cornerRadius: 20)
                .strokeBorder(Color.primary.opacity(0.08))
        }
        .padding(.horizontal)
        .padding(.bottom, 8)
    }
}

private struct WaypointMapView: UIViewRepresentable {
    @Binding var selectedCoordinate: CLLocationCoordinate2D?
    let userLocation: CLLocationCoordinate2D?
    @Binding var hasCenteredOnUser: Bool
    let locationStore: LocationManager
    let onLongPress: (CLLocationCoordinate2D) -> Void
    let recenterTrigger: Int

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView(frame: .zero)
        mapView.delegate = context.coordinator
        mapView.showsUserLocation = true
        mapView.showsCompass = true
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
        locationStore.update(location: mapView.userLocation.location)

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

            let point = gesture.location(in: mapView)
            let coordinate = mapView.convert(point, toCoordinateFrom: mapView)
            parent.onLongPress(coordinate)
        }

        func updateSelectedAnnotation(on mapView: MKMapView) {
            if let coordinate = parent.selectedCoordinate {
                annotation.coordinate = coordinate
                annotation.title = "Selected Goal"

                if !mapView.annotations.contains(where: { $0 === annotation }) {
                    mapView.addAnnotation(annotation)
                }
            } else {
                mapView.removeAnnotation(annotation)
            }
        }

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            guard !(annotation is MKUserLocation) else {
                return nil
            }

            let identifier = "WaypointPin"
            let view = mapView.dequeueReusableAnnotationView(withIdentifier: identifier) as? MKMarkerAnnotationView
                ?? MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: identifier)

            view.annotation = annotation
            view.canShowCallout = true
            view.markerTintColor = .systemBlue
            view.glyphImage = UIImage(systemName: "flag.fill")
            return view
        }
    }
}
