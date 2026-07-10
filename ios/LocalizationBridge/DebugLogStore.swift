import Combine
import Foundation

@MainActor
final class DebugLogStore: ObservableObject {
    @Published private(set) var entries: [String] = []

    private let maximumEntries: Int

    init(maximumEntries: Int = 20) {
        self.maximumEntries = maximumEntries
    }

    func append(_ message: String) {
        entries.append(message)

        if entries.count > maximumEntries {
            entries.removeFirst(entries.count - maximumEntries)
        }
    }
}