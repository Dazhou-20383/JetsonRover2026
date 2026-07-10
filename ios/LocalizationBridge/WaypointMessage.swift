import Foundation

struct WaypointMessage: Codable {
    let type: String
    let latitude: Double
    let longitude: Double
    let altitude: Double?
    let heading_deg: Double?
    let timestamp: Double
    let source: String
    let frame: String
    let user_prompt: String?
    let mode: String
}

struct RouteGuideMessage: Codable {
    let type: String
    let tag: String
    let source: String
    let frame: String
    let generated_at: Double
    let goal_timestamp: Double
    let origin: RouteCoordinate
    let destination: RouteCoordinate
    let route_array: String
    let steps: [RouteStepMessage]
}

struct RouteCoordinate: Codable {
    let latitude: Double
    let longitude: Double
}

struct RouteStepMessage: Codable {
    let index: Int
    let instruction: String
    let bearing_deg: Double?
    let cardinal: String?
    let distance_m: Double
    let start: RouteCoordinate?
    let end: RouteCoordinate?
}
