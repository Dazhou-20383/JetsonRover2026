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

    /// Rounds a coordinate to ~1 meter of precision so nearby requests for
    /// the same origin/destination pair hit the same cache entry.
    private struct RouteCacheKey: Hashable {
        let originLatitude: Int
        let originLongitude: Int
        let destinationLatitude: Int
        let destinationLongitude: Int

        init(origin: CLLocationCoordinate2D, destination: CLLocationCoordinate2D) {
            func rounded(_ value: CLLocationDegrees) -> Int {
                Int((value * 100_000).rounded())
            }
            originLatitude = rounded(origin.latitude)
            originLongitude = rounded(origin.longitude)
            destinationLatitude = rounded(destination.latitude)
            destinationLongitude = rounded(destination.longitude)
        }
    }

    private struct CachedRoute {
        let route: MKRoute
        let cachedAt: Date
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
    /// The route planned (over cellular/Wi-Fi) for the selected goal. It is
    /// planned as soon as a goal is dropped, independent of the rover link,
    /// because the phone usually loses internet once it is tethered to the
    /// Jetson. Sending the goal later reuses this route with no network.
    @Published private(set) var plannedRoute: MKRoute?
    @Published private(set) var routeError: String?

    let locationManager: LocationManager

    private let networkManager: NetworkManager
    private let debugLogStore: DebugLogStore
    private let encoder: JSONEncoder
    private var cancellables = Set<AnyCancellable>()
    private var routeTask: Task<Void, Never>?
    private var routeCache: [RouteCacheKey: CachedRoute] = [:]
    private let routeCacheTTL: TimeInterval = 120
    private var plannedRouteOrigin: CLLocationCoordinate2D?
    private var planID = 0
    /// Set when a goal was dropped before the first GPS fix; planning starts
    /// as soon as a location arrives.
    private var isWaitingForLocationToPlan = false

    init(networkManager: NetworkManager, debugLogStore: DebugLogStore) {
        self.networkManager = networkManager
        self.debugLogStore = debugLogStore
        self.locationManager = LocationManager()

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        self.encoder = encoder

        debugLogStore.append("Map: initialized")

        locationManager.$currentLocation
            .sink { [weak self] (location: CLLocation?) in
                guard let self else { return }
                self.refreshPreview()
                if location != nil && self.isWaitingForLocationToPlan {
                    self.planRoute()
                }
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

    var routeSummaryText: String? {
        guard let plannedRoute else { return nil }
        let minutes = max(1, Int((plannedRoute.expectedTravelTime / 60).rounded()))
        return "\(formattedDistance(plannedRoute.distance)) · \(minutes) min walk"
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
        selectedCoordinate = coordinate
        debugLogStore.append(String(format: "Map: waypoint selected lat=%.6f lon=%.6f", coordinate.latitude, coordinate.longitude))
        refreshPreview()
        planRoute()
    }

    func clearWaypoint() {
        selectedCoordinate = nil
        resetRoute()
        statusMessage = "Long-press on the map to select a waypoint."
        refreshPreview()
    }

    /// Plans a walking route from the current location to the selected goal.
    /// Needs internet (MapKit), but not the rover link.
    func planRoute() {
        guard let destination = selectedCoordinate else { return }
        resetRoute()

        guard let origin = currentCoordinate else {
            isWaitingForLocationToPlan = true
            routeError = "Waiting for your location to plan a route…"
            statusMessage = "Goal selected. Waiting for your location to plan a route."
            return
        }

        isPlanningRoute = true
        statusMessage = "Planning route…"
        planID += 1
        let thisPlan = planID
        let cacheKey = RouteCacheKey(origin: origin, destination: destination)

        routeTask = Task { [weak self] in
            guard let self else { return }
            do {
                let route: MKRoute
                if let cached = self.cachedRoute(for: cacheKey) {
                    route = cached
                    self.debugLogStore.append("Map: reused cached route")
                } else {
                    let request = MKDirections.Request()
                    request.source = MKMapItem(placemark: MKPlacemark(coordinate: origin))
                    request.destination = MKMapItem(placemark: MKPlacemark(coordinate: destination))
                    request.transportType = .walking

                    let response = try await MKDirections(request: request).calculate()
                    guard let calculated = response.routes.first else {
                        throw RoutePlanningError.noRoute
                    }
                    route = calculated
                    self.cacheRoute(route, for: cacheKey)
                }

                guard !Task.isCancelled, thisPlan == self.planID else { return }
                self.apply(route: route, origin: origin)
            } catch {
                guard !Task.isCancelled, thisPlan == self.planID else { return }
                self.isPlanningRoute = false
                let message: String
                if let mkError = error as? MKError, mkError.code == .serverFailure || mkError.code == .loadingThrottled {
                    message = "Couldn't reach Apple Maps. Route planning needs internet, so plan before tethering to the rover."
                } else if error is RoutePlanningError {
                    message = "No walking route to this goal."
                } else {
                    message = "Route planning failed: \(error.localizedDescription)"
                }
                self.routeError = message
                self.statusMessage = "Goal selected without a route. You can still send the goal alone."
                self.debugLogStore.append("Map: route planning failed - \(error.localizedDescription)")
            }
        }
    }

    private func apply(route: MKRoute, origin: CLLocationCoordinate2D) {
        isPlanningRoute = false
        plannedRoute = route
        plannedRouteOrigin = origin
        routeInstructionBuffer = actionableInstructions(in: route)

        if let nextStep = firstActionableStep(in: route) {
            let nextInstruction = displayInstruction(for: nextStep)
            let intersectionName = inferredIntersectionName(from: nextStep)
            let directionText = bearingForStep(nextStep).map {
                String(format: "%.1f° %@", $0, cardinalDirection(for: $0))
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
        }

        statusMessage = "Route ready. Connect to the rover and send it."
        debugLogStore.append("Map: route planned (\(routeInstructionBuffer.count) steps)")
    }

    private func resetRoute() {
        routeTask?.cancel()
        planID += 1
        isWaitingForLocationToPlan = false
        isPlanningRoute = false
        plannedRoute = nil
        plannedRouteOrigin = nil
        routeError = nil
        nextStepBuffer = nil
        routeInstructionBuffer = []
        routeGuidance = nil
    }

    /// Sends the goal and, if one was planned, its route guide. Uses only the
    /// rover link: no MapKit/internet access happens here.
    func sendGoal() {
        guard let coordinate = selectedCoordinate else {
            statusMessage = "Select a waypoint before sending."
            return
        }

        let message = makeWaypointMessage(for: coordinate)

        do {
            // The pretty-printed encoding is for the on-screen preview only.
            // The wire format must be compact: the TCP channel is
            // newline-delimited JSON, so a pretty-printed message would be
            // split into one malformed line per field on the Jetson.
            let data = try encoder.encode(message)
            jsonPreview = String(decoding: data, as: UTF8.self)
            try networkManager.sendMessage(message)
            debugLogStore.append("Map: goal sent")
        } catch {
            statusMessage = "Couldn't send goal: \(error.localizedDescription)"
            debugLogStore.append("Map: goal send failed - \(error.localizedDescription)")
            return
        }

        guard let route = plannedRoute, let origin = plannedRouteOrigin else {
            statusMessage = "Goal sent to the rover (no route attached)."
            return
        }

        do {
            try networkManager.sendMessage(
                makeRouteGuideMessage(
                    route: route,
                    origin: origin,
                    destination: coordinate,
                    goalTimestamp: message.timestamp
                )
            )
            statusMessage = "Goal and route sent to the rover."
            debugLogStore.append("Map: route guide sent")
        } catch {
            statusMessage = "Goal sent, but the route failed to send: \(error.localizedDescription)"
            debugLogStore.append("Map: route guide send failed - \(error.localizedDescription)")
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

    private func cachedRoute(for key: RouteCacheKey) -> MKRoute? {
        guard let cached = routeCache[key],
              Date().timeIntervalSince(cached.cachedAt) < routeCacheTTL
        else {
            return nil
        }
        return cached.route
    }

    private func cacheRoute(_ route: MKRoute, for key: RouteCacheKey) {
        // Small, opportunistic prune so the cache doesn't grow without bound
        // over a long session; this app only ever has a handful of entries
        // at once, so a full scan on insert is more than cheap enough.
        let now = Date()
        routeCache = routeCache.filter { now.timeIntervalSince($0.value.cachedAt) < routeCacheTTL }
        routeCache[key] = CachedRoute(route: route, cachedAt: now)
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

private enum RoutePlanningError: Error {
    case noRoute
}
