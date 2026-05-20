import Combine
import CoreLocation
import Foundation

@MainActor
final class LocationManager: NSObject, ObservableObject {
    @Published private(set) var authorizationStatus: CLAuthorizationStatus
    @Published private(set) var currentLocation: CLLocation?
    @Published private(set) var headingDegrees: Double?
    @Published private(set) var errorMessage: String?

    private let manager = CLLocationManager()

    override init() {
        authorizationStatus = manager.authorizationStatus
        super.init()

        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.distanceFilter = kCLDistanceFilterNone
        manager.headingFilter = 1
    }

    func requestPermissionsIfNeeded() {
        switch authorizationStatus {
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .authorizedAlways, .authorizedWhenInUse:
            startUpdates()
        case .restricted, .denied:
            errorMessage = "Location access is disabled. Enable While Using the App in Settings."
        @unknown default:
            errorMessage = "Location authorization is unavailable."
        }
    }

    func startUpdates() {
        guard CLLocationManager.locationServicesEnabled() else {
            errorMessage = "Location services are disabled on this device."
            return
        }

        manager.startUpdatingLocation()

        if CLLocationManager.headingAvailable() {
            manager.startUpdatingHeading()
        }
    }

    func stopUpdates() {
        manager.stopUpdatingLocation()
        manager.stopUpdatingHeading()
    }
}

extension LocationManager: CLLocationManagerDelegate {
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            authorizationStatus = manager.authorizationStatus

            switch authorizationStatus {
            case .authorizedAlways, .authorizedWhenInUse:
                errorMessage = nil
                startUpdates()
            case .denied, .restricted:
                errorMessage = "Location access is disabled. Enable While Using the App in Settings."
            case .notDetermined:
                break
            @unknown default:
                errorMessage = "Location authorization is unavailable."
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        Task { @MainActor in
            currentLocation = locations.last
            errorMessage = nil
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) {
        let heading = newHeading.trueHeading >= 0 ? newHeading.trueHeading : newHeading.magneticHeading

        Task { @MainActor in
            headingDegrees = heading >= 0 ? heading : nil
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
            errorMessage = error.localizedDescription
        }
    }
}
