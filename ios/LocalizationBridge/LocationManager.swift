import Combine
import CoreLocation
import Foundation

@MainActor
final class LocationManager: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published private(set) var currentLocation: CLLocation?
    @Published private(set) var headingDegrees: Double?
    @Published private(set) var errorMessage: String?

    private let manager = CLLocationManager()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        errorMessage = "Waiting for map location updates..."
    }

    /// Explicitly triggers the system location permission prompt. Call this once,
    /// from a single known place (e.g. app/root view onAppear), rather than relying
    /// on MKMapView's implicit prompting, which only fires once per install and can
    /// race with other permission prompts (e.g. the camera prompt) on the same frame.
    func requestAuthorization() {
        let status = manager.authorizationStatus
        switch status {
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .authorized, .authorizedAlways, .authorizedWhenInUse:
            manager.startUpdatingHeading()
        case .denied, .restricted:
            errorMessage = "Location permission denied. Enable Location in Settings."
        @unknown default:
            break
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            switch manager.authorizationStatus {
            case .authorized, .authorizedAlways, .authorizedWhenInUse:
                self.errorMessage = nil
                manager.startUpdatingHeading()
            case .denied, .restricted:
                self.errorMessage = "Location permission denied. Enable Location in Settings."
            case .notDetermined:
                break
            @unknown default:
                break
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) {
        guard newHeading.headingAccuracy >= 0 else { return }
        let value = newHeading.trueHeading >= 0 ? newHeading.trueHeading : newHeading.magneticHeading
        Task { @MainActor in
            self.update(headingDegrees: value)
        }
    }

    func update(location: CLLocation?) {
        currentLocation = location
        if location == nil, errorMessage == nil {
            errorMessage = "Waiting for map location updates..."
        } else if location != nil {
            errorMessage = nil
        }
    }

    func update(headingDegrees: Double?) {
        self.headingDegrees = headingDegrees
    }

    func clear() {
        currentLocation = nil
        headingDegrees = nil
        errorMessage = "Waiting for map location updates..."
    }
}
