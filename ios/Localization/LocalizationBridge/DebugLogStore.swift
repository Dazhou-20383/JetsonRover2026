import Combine
import Foundation

@MainActor
final class DebugLogStore: ObservableObject {
    @Published private(set) var entries: [String] = []

    private let maximumEntries: Int

    init(maximumEntries: Int = 200) {
        self.maximumEntries = maximumEntries
    }

    func append(_ message: String) {
        let timestamp = Self.timeFormatter.string(from: Date())
        entries.append("\(timestamp)  \(message)")

        if entries.count > maximumEntries {
            entries.removeFirst(entries.count - maximumEntries)
        }
    }

    private static let timeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter
    }()
}
