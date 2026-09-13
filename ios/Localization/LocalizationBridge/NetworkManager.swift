import Darwin
import Foundation

/// Transport for messages sent from the iOS app to the Jetson. Each instance
/// owns one socket for one transport; the app creates one UDP instance for
/// the AR pose stream and one TCP instance for MapKit waypoint/route
/// messages (see `LocalizationBridgeApp`), rather than sharing a single
/// socket across both.
final class NetworkManager {
    enum Transport: String {
        case udp
        case tcp
    }

    private let host: String
    private let port: UInt16
    private let transport: Transport
    private let socketFD: Int32
    private let encoder: JSONEncoder
    private let sendQueue = DispatchQueue(label: "LocalizationBridge.NetworkManager")
    private var destination = sockaddr_in()

    init(host: String, port: UInt16 = 5005, transport: Transport = .udp) throws {
        self.host = host
        self.port = port
        self.transport = transport
        self.encoder = JSONEncoder()

        let socketType = transport == .udp ? Int32(SOCK_DGRAM) : Int32(SOCK_STREAM)
        socketFD = socket(AF_INET, socketType, 0)
        guard socketFD >= 0 else {
            throw NetworkManagerError.socketCreationFailed(errno)
        }

        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.stride)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = port.bigEndian

        let conversionResult = host.withCString { cString in
            inet_pton(AF_INET, cString, &addr.sin_addr)
        }

        guard conversionResult == 1 else {
            close(socketFD)
            throw NetworkManagerError.invalidAddress(host)
        }

        destination = addr

        if transport == .tcp {
            var connectAddress = destination
            let result = withUnsafePointer(to: &connectAddress) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                    connect(
                        socketFD,
                        sockaddrPointer,
                        socklen_t(MemoryLayout<sockaddr_in>.stride)
                    )
                }
            }

            guard result == 0 else {
                let errorCode = errno
                close(socketFD)
                throw NetworkManagerError.connectionFailed(host: host, port: port, code: errorCode)
            }
        }
    }

    deinit {
        close(socketFD)
    }

    /// Encodes and sends a message. Callers that already have their own encoded
    /// `Data` (e.g. because they also need it for an on-screen preview) should
    /// call `send(data:)` directly instead, to avoid encoding the same message twice.
    func sendMessage<T: Encodable>(_ message: T) throws {
        let data = try encoder.encode(message)
        try send(data: data)
    }

    /// Sends pre-encoded bytes as-is. Exposed so callers that already hold an
    /// encoded payload (for a preview, a cache, etc.) can send it without
    /// re-encoding through this type's own `encoder`.
    func send(data: Data) throws {
        // TCP is a byte stream with no built-in message boundaries, so each
        // payload needs an explicit delimiter; UDP datagrams are already
        // whole messages and need none.
        let framedData: Data
        switch transport {
        case .udp:
            framedData = data
        case .tcp:
            framedData = data + Data([0x0A]) // "\n"
        }

        try sendQueue.sync {
            guard !framedData.isEmpty else {
                throw NetworkManagerError.emptyPayload
            }

            let bytesSent = try framedData.withUnsafeBytes { buffer -> Int in
                guard let baseAddress = buffer.baseAddress else {
                    throw NetworkManagerError.emptyPayload
                }

                switch transport {
                case .udp:
                    var addr = destination
                    return try withUnsafePointer(to: &addr) { pointer in
                        try pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                            let result = sendto(
                                socketFD,
                                baseAddress,
                                buffer.count,
                                0,
                                sockaddrPointer,
                                socklen_t(MemoryLayout<sockaddr_in>.stride)
                            )

                            guard result >= 0 else {
                                throw NetworkManagerError.sendFailed(code: errno, transport: transport)
                            }

                            return result
                        }
                    }
                case .tcp:
                    let result = Darwin.send(socketFD, baseAddress, buffer.count, 0)
                    guard result >= 0 else {
                        throw NetworkManagerError.sendFailed(code: errno, transport: transport)
                    }
                    return result
                }
            }

            guard bytesSent == framedData.count else {
                throw NetworkManagerError.partialSend(expected: framedData.count, actual: bytesSent)
            }
        }
    }
}

enum NetworkManagerError: Error, LocalizedError {
    case socketCreationFailed(Int32)
    case invalidAddress(String)
    case connectionFailed(host: String, port: UInt16, code: Int32)
    case emptyPayload
    case partialSend(expected: Int, actual: Int)
    case sendFailed(code: Int32, transport: NetworkManager.Transport)

    var errorDescription: String? {
        switch self {
        case .socketCreationFailed(let code):
            return "Failed to create \(transportDescription) socket (errno \(code))."
        case .invalidAddress(let host):
            return "Invalid IPv4 address: \(host)"
        case .connectionFailed(let host, let port, let code):
            return "Failed to connect to \(host):\(port) over TCP (errno \(code))."
        case .emptyPayload:
            return "Refusing to send an empty payload."
        case .partialSend(let expected, let actual):
            return "Sent \(actual) of \(expected) bytes."
        case .sendFailed(let code, let transport):
            return "Failed to send over \(transport.rawValue.uppercased()) (errno \(code))."
        }
    }

    private var transportDescription: String {
        switch self {
        case .sendFailed(_, let transport):
            return transport.rawValue.uppercased()
        default:
            return "network"
        }
    }
}
