import Combine
import CoreLocation
import Foundation
import MapKit

@MainActor
final class MapViewModel: ObservableObject {
    struct RouteInstruction: Equatable, Identifiable {
        let id: Int
        let instruction: String
        let directionText: String
        let distanceText: String
    }

    struct BufferedStep: Equatable {
        let instruction: String
        let distanceText: String
        let landmarkText: String
    }

    struct RouteGuidance: Equatable {
        let distanceToNextLandmarkText: String
        let intersectionName: String
        let absoluteDirectionText: String
        let instructions: String
    }

    @Published var selectedCoordinate: CLLocationCoordinate2D?
    @Published var hasCenteredOnUser = false
    @Published private(set) var recenterRequestID = 0
    @Published private(set) var jsonPreview = ""
    @Published private(set) var statusMessage = "Long-press on the map to select a waypoint."
    @Published private(set) var nextStepBuffer: BufferedStep?
    @Published private(set) var routeInstructionBuffer: [RouteInstruction] = []
    @Published private(set) var routeGuidance: RouteGuidance?
    @Published private(set) var isPlanningRoute = false

    let locationManager: LocationManager

    private let networkManager: NetworkManager
    private let debugLogStore: DebugLogStore
    private let encoder: JSONEncoder
    private var cancellables = Set<AnyCancellable>()
    private var routeTask: Task<Void, Never>?

    init(networkManager: NetworkManager, debugLogStore: DebugLogStore) {
        self.networkManager = networkManager
        self.debugLogStore = debugLogStore
        self.locationManager = LocationManager()

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        self.encoder = encoder

        debugLogStore.append("Map: initialized")

        locationManager.$currentLocation
            .sink { [weak self] (_: CLLocation?) in
                self?.refreshPreview()
            }
            .store(in: &cancellables)
    }

    var currentCoordinate: CLLocationCoordinate2D? {
        locationManager.currentLocation?.coordinate
    }

    var selectedLatitudeText: String {
        guard let coordinate = selectedCoordinate else { return "Not selected" }
        return Self.coordinateFormatter.string(from: NSNumber(value: coordinate.latitude)) ?? "Not selected"
    }

    var selectedLongitudeText: String {
        guard let coordinate = selectedCoordinate else { return "Not selected" }
        return Self.coordinateFormatter.string(from: NSNumber(value: coordinate.longitude)) ?? "Not selected"
    }

    var headingText: String {
        guard let heading = locationManager.headingDegrees else { return "Unavailable" }
        return String(format: "%.1f°", heading)
    }

    var currentLatitudeText: String {
        guard let latitude = currentCoordinate?.latitude else { return "Unavailable" }
        return Self.coordinateFormatter.string(from: NSNumber(value: latitude)) ?? "Unavailable"
    }

    var currentLongitudeText: String {
        guard let longitude = currentCoordinate?.longitude else { return "Unavailable" }
        return Self.coordinateFormatter.string(from: NSNumber(value: longitude)) ?? "Unavailable"
    }

    var distanceText: String {
        guard let distanceMeters = distanceToSelectedWaypointMeters else { return "Unavailable" }

        if distanceMeters >= 1000 {
            return String(format: "%.2f km", distanceMeters / 1000)
        }

        return String(format: "%.1f m", distanceMeters)
    }

    var absoluteDirectionText: String {
        guard let bearing = bearingToSelectedWaypointDegrees else { return "Unavailable" }
        return String(format: "%.1f° %@", bearing, cardinalDirection(for: bearing))
    }

    var canSendGoal: Bool {
        selectedCoordinate != nil
    }

    var routeArrayText: String {
        guard !routeInstructionBuffer.isEmpty else { return "{}" }

        let entries = routeInstructionBuffer.map { step in
            "(Direction \(step.directionText), \(step.distanceText))"
        }

        return "{\(entries.joined(separator: ", "))}"
    }

    func onAppear() {
        debugLogStore.append("Map: onAppear")
        refreshPreview()
    }

    func onDisappear() {
        debugLogStore.append("Map: onDisappear")
        routeTask?.cancel()
    }

    func recenterOnUser() {
        hasCenteredOnUser = false
        recenterRequestID += 1
    }

    func selectWaypoint(at coordinate: CLLocationCoordinate2D) {
        routeTask?.cancel()
        selectedCoordinate = coordinate
        nextStepBuffer = nil
        routeInstructionBuffer = []
        routeGuidance = nil
        isPlanningRoute = false
        statusMessage = "Waypoint selected. Review the payload and send when ready."
        debugLogStore.append(String(format: "Map: waypoint selected lat=%.6f lon=%.6f", coordinate.latitude, coordinate.longitude))
        refreshPreview()
    }

    func sendGoal() async -> Bool {
        guard let coordinate = selectedCoordinate else {
            statusMessage = "Select a waypoint before sending."
            return false
        }

        let message = makeWaypointMessage(for: coordinate)

        do {
            let json = try networkManager.sendMessage(message)
            jsonPreview = prettyPrintedJSON(from: json) ?? json
            statusMessage = "Goal sent to Jetson. Planning route guidance..."
            debugLogStore.append("Map: goal sent")
            isPlanningRoute = true
            nextStepBuffer = nil
            routeInstructionBuffer = []
            routeGuidance = nil
            await updateRouteGuidance(to: coordinate, goalTimestamp: message.timestamp)
            return true
        } catch {
            statusMessage = error.localizedDescription
            debugLogStore.append("Map: goal send failed - \(error.localizedDescription)")
            return false
        }
    }

    private func refreshPreview() {
        guard let coordinate = selectedCoordinate else {
            jsonPreview = ""
            return
        }

        let message = makeWaypointMessage(for: coordinate)

        do {
            let data = try encoder.encode(message)
            jsonPreview = String(decoding: data, as: UTF8.self)
        } catch {
            jsonPreview = ""
            statusMessage = error.localizedDescription
        }
    }

    private func updateRouteGuidance(to destination: CLLocationCoordinate2D, goalTimestamp: Double) async {
        routeTask?.cancel()

        let task = Task { [weak self] in
            guard let self else { return }
            defer { isPlanningRoute = false }

            guard let currentCoordinate else {
                nextStepBuffer = nil
                routeInstructionBuffer = []
                routeGuidance = nil
                statusMessage = "Goal sent to Jetson. Current location is unavailable for route planning."
                return
            }

            let request = MKDirections.Request()
            request.source = MKMapItem(
                placemark: MKPlacemark(coordinate: currentCoordinate)
            )
            request.destination = MKMapItem(
                placemark: MKPlacemark(coordinate: destination)
            )
            request.transportType = .walking

            let directions = MKDirections(request: request)

            do {
                let response = try await directions.calculate()
                guard !Task.isCancelled else { return }

                guard let route = response.routes.first else {
                    nextStepBuffer = nil
                    routeInstructionBuffer = []
                    routeGuidance = nil
                    statusMessage = "Goal sent to Jetson. No route guidance is available for this waypoint."
                    return
                }

                let instructions = actionableInstructions(in: route)
                routeInstructionBuffer = instructions

                guard let nextStep = firstActionableStep(in: route)
                else {
                    nextStepBuffer = nil
                    routeGuidance = nil
                    statusMessage = "Goal sent to Jetson. No route guidance is available for this waypoint."
                    return
                }

                let nextInstruction = displayInstruction(for: nextStep)
                let intersectionName = inferredIntersectionName(from: nextStep)
                let stepBearing = bearingForStep(nextStep)
                let directionText = stepBearing.map {
                    String(format: "%.1f° %@", $0, self.cardinalDirection(for: $0))
                } ?? "Unavailable"

                nextStepBuffer = BufferedStep(
                    instruction: nextInstruction,
                    distanceText: formattedDistance(nextStep.distance),
                    landmarkText: intersectionName
                )
                routeGuidance = RouteGuidance(
                    distanceToNextLandmarkText: formattedDistance(nextStep.distance),
                    intersectionName: intersectionName,
                    absoluteDirectionText: directionText,
                    instructions: nextInstruction
                )

                do {
                    let routeGuideMessage = makeRouteGuideMessage(
                        route: route,
                        origin: currentCoordinate,
                        destination: destination,
                        goalTimestamp: goalTimestamp
                    )
                    _ = try networkManager.sendMessage(routeGuideMessage)
                    statusMessage = "Goal sent to Jetson. Tagged route guide emitted for VLM/ROS2."
                } catch {
                    statusMessage = "Goal sent and route shown, but route-guide payload failed: \(error.localizedDescription)"
                }
            } catch is CancellationError {
                return
            } catch {
                nextStepBuffer = nil
                routeInstructionBuffer = []
                routeGuidance = nil
                statusMessage = "Goal sent to Jetson, but route planning failed: \(error.localizedDescription)"
            }
        }

        routeTask = task
        await task.value
    }

    private var distanceToSelectedWaypointMeters: CLLocationDistance? {
        guard let selectedCoordinate,
              let currentLocation = locationManager.currentLocation
        else {
            return nil
        }

        let waypointLocation = CLLocation(
            latitude: selectedCoordinate.latitude,
            longitude: selectedCoordinate.longitude
        )
        return currentLocation.distance(from: waypointLocation)
    }

    private var bearingToSelectedWaypointDegrees: Double? {
        guard let selectedCoordinate,
              let currentCoordinate = currentCoordinate
        else {
            return nil
        }

        let startLatitude = currentCoordinate.latitude * .pi / 180
        let startLongitude = currentCoordinate.longitude * .pi / 180
        let endLatitude = selectedCoordinate.latitude * .pi / 180
        let endLongitude = selectedCoordinate.longitude * .pi / 180

        let deltaLongitude = endLongitude - startLongitude
        let y = sin(deltaLongitude) * cos(endLatitude)
        let x = cos(startLatitude) * sin(endLatitude)
            - sin(startLatitude) * cos(endLatitude) * cos(deltaLongitude)
        let bearingRadians = atan2(y, x)
        let bearingDegrees = bearingRadians * 180 / .pi

        return bearingDegrees >= 0 ? bearingDegrees : bearingDegrees + 360
    }

    private func makeWaypointMessage(for coordinate: CLLocationCoordinate2D) -> WaypointMessage {
        WaypointMessage(
            type: "manual_goal",
            latitude: coordinate.latitude,
            longitude: coordinate.longitude,
            altitude: locationManager.currentLocation?.altitude,
            heading_deg: locationManager.headingDegrees,
            timestamp: Date().timeIntervalSince1970,
            source: "mapkit",
            frame: "WGS84",
            user_prompt: nil,
            mode: "manual"
        )
    }

    private func makeRouteGuideMessage(
        route: MKRoute,
        origin: CLLocationCoordinate2D,
        destination: CLLocationCoordinate2D,
        goalTimestamp: Double
    ) -> RouteGuideMessage {
        let generatedAt = Date().timeIntervalSince1970

        return RouteGuideMessage(
            type: "route_guide",
            tag: "ROUTE_GUIDE_V1",
            source: "mapkit",
            frame: "WGS84",
            generated_at: generatedAt,
            goal_timestamp: goalTimestamp,
            origin: RouteCoordinate(latitude: origin.latitude, longitude: origin.longitude),
            destination: RouteCoordinate(latitude: destination.latitude, longitude: destination.longitude),
            route_array: routeArrayText,
            steps: actionableRouteSteps(in: route)
        )
    }

    private func prettyPrintedJSON(from json: String) -> String? {
        guard let data = json.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data),
              let normalized = try? JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])
        else {
            return nil
        }

        return String(decoding: normalized, as: UTF8.self)
    }

    private func firstActionableStep(in route: MKRoute) -> MKRoute.Step? {
        route.steps.first { step in
            step.distance > 0 && !step.instructions.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
    }

    private func actionableInstructions(in route: MKRoute) -> [RouteInstruction] {
        route.steps.enumerated().compactMap { index, step in
            let instruction = step.instructions.trimmingCharacters(in: .whitespacesAndNewlines)
            guard step.distance > 0, !instruction.isEmpty else {
                return nil
            }

            let directionText = bearingForStep(step).map { bearing in
                String(format: "%.0f %@", bearing, cardinalDirection(for: bearing))
            } ?? "Unavailable"

            return RouteInstruction(
                id: index,
                instruction: instruction,
                directionText: directionText,
                distanceText: formattedDistanceForArray(step.distance)
            )
        }
    }

    private func actionableRouteSteps(in route: MKRoute) -> [RouteStepMessage] {
        route.steps.enumerated().compactMap { index, step in
            let instruction = step.instructions.trimmingCharacters(in: .whitespacesAndNewlines)
            guard step.distance > 0, !instruction.isEmpty else {
                return nil
            }

            let bearing = bearingForStep(step)
            let cardinal = bearing.map { cardinalDirection(for: $0) }
            let endpoints = endpointsForStep(step)

            return RouteStepMessage(
                index: index,
                instruction: instruction,
                bearing_deg: bearing.map { ($0 * 10).rounded() / 10 },
                cardinal: cardinal,
                distance_m: (step.distance * 10).rounded() / 10,
                start: endpoints.map {
                    RouteCoordinate(latitude: $0.start.latitude, longitude: $0.start.longitude)
                },
                end: endpoints.map {
                    RouteCoordinate(latitude: $0.end.latitude, longitude: $0.end.longitude)
                }
            )
        }
    }

    private func displayInstruction(for step: MKRoute.Step) -> String {
        let instruction = step.instructions.trimmingCharacters(in: .whitespacesAndNewlines)
        return instruction.isEmpty ? "Continue to destination." : instruction
    }

    private func inferredIntersectionName(from step: MKRoute.Step) -> String {
        let instruction = step.instructions.trimmingCharacters(in: .whitespacesAndNewlines)

        let patterns = [
            " onto ",
            " on ",
            " at "
        ]

        for pattern in patterns {
            if let range = instruction.range(of: pattern, options: [.caseInsensitive]) {
                let trailing = instruction[range.upperBound...]
                    .trimmingCharacters(in: .whitespacesAndNewlines.union(.punctuationCharacters))
                if !trailing.isEmpty {
                    return trailing
                }
            }
        }

        if let notice = step.notice, !notice.isEmpty {
            return notice
        }

        return instruction.isEmpty ? "Next landmark unavailable" : instruction
    }

    private func bearingForStep(_ step: MKRoute.Step) -> Double? {
        guard let endpoints = endpointsForStep(step)
        else {
            return nil
        }

        return bearing(from: endpoints.start, to: endpoints.end)
    }

    private func endpointsForStep(
        _ step: MKRoute.Step
    ) -> (start: CLLocationCoordinate2D, end: CLLocationCoordinate2D)? {
        let pointCount = step.polyline.pointCount
        guard pointCount >= 2 else { return nil }

        var coordinates = Array(
            repeating: CLLocationCoordinate2D(latitude: 0, longitude: 0),
            count: pointCount
        )
        step.polyline.getCoordinates(&coordinates, range: NSRange(location: 0, length: pointCount))

        guard let start = coordinates.first,
              let end = coordinates.dropFirst().first(where: { coordinate in
                  coordinate.latitude != start.latitude || coordinate.longitude != start.longitude
              })
        else {
            return nil
        }

        return (start, end)
    }

    private func bearing(from start: CLLocationCoordinate2D, to end: CLLocationCoordinate2D) -> Double {
        let startLatitude = start.latitude * .pi / 180
        let startLongitude = start.longitude * .pi / 180
        let endLatitude = end.latitude * .pi / 180
        let endLongitude = end.longitude * .pi / 180

        let deltaLongitude = endLongitude - startLongitude
        let y = sin(deltaLongitude) * cos(endLatitude)
        let x = cos(startLatitude) * sin(endLatitude)
            - sin(startLatitude) * cos(endLatitude) * cos(deltaLongitude)
        let bearingRadians = atan2(y, x)
        let bearingDegrees = bearingRadians * 180 / .pi

        return bearingDegrees >= 0 ? bearingDegrees : bearingDegrees + 360
    }

    private func formattedDistance(_ distanceMeters: CLLocationDistance) -> String {
        if distanceMeters >= 1000 {
            return String(format: "%.2f km", distanceMeters / 1000)
        }

        return String(format: "%.1f m", distanceMeters)
    }

    private func formattedDistanceForArray(_ distanceMeters: CLLocationDistance) -> String {
        String(format: "%.0fm", distanceMeters)
    }

    private func cardinalDirection(for bearing: Double) -> String {
        switch bearing {
        case 22.5..<67.5:
            return "NE"
        case 67.5..<112.5:
            return "E"
        case 112.5..<157.5:
            return "SE"
        case 157.5..<202.5:
            return "S"
        case 202.5..<247.5:
            return "SW"
        case 247.5..<292.5:
            return "W"
        case 292.5..<337.5:
            return "NW"
        default:
            return "N"
        }
    }

    private static let coordinateFormatter: NumberFormatter = {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.minimumFractionDigits = 6
        formatter.maximumFractionDigits = 6
        return formatter
    }()
}
