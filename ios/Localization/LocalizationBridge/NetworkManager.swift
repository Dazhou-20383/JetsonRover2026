import Darwin
import Foundation

/// Transport for messages sent from the iOS app to the Jetson. Each instance
/// owns one socket for one transport; the app creates one UDP instance for
/// the AR pose stream, one UDP instance for the optional camera stream, and
/// one TCP instance for MapKit waypoint/route messages (see
/// `LocalizationBridgeApp`).
///
/// TCP instances never connect on their own: `connect()` is driven by the
/// user's Connect button (via `ConnectionManager`). Connecting eagerly in
/// `init` and `try!`-ing it from the App initializer used to crash the app
/// at launch whenever the Jetson wasn't reachable.
///
/// Thread-safety: all socket state is only touched on `queue`, so the
/// instance can be used from any thread.
nonisolated final class NetworkManager: @unchecked Sendable {
    enum Transport: String {
        case udp
        case tcp
    }

    let host: String
    let port: UInt16
    let transport: Transport

    /// Called on an internal queue when an established TCP connection drops
    /// (peer closed it, keep-alive timed out, or a send failed). Not called
    /// for an explicit `disconnect()`. Set it before calling `connect()`.
    var onDisconnect: (@Sendable (Error) -> Void)?

    /// Compact (single-line, required by the TCP newline framing) with
    /// sorted keys, so every message has a stable field order on the Jetson.
    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }()
    private let queue = DispatchQueue(label: "LocalizationBridge.NetworkManager")
    private let destination: sockaddr_in
    private let connectTimeoutMs: Int32 = 3000

    private var socketFD: Int32 = -1
    private var readSource: DispatchSourceRead?

    init(host: String, port: UInt16, transport: Transport) throws {
        self.host = host
        self.port = port
        self.transport = transport

        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.stride)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = port.bigEndian

        let conversionResult = host.withCString { cString in
            inet_pton(AF_INET, cString, &addr.sin_addr)
        }
        guard conversionResult == 1 else {
            throw NetworkManagerError.invalidAddress(host)
        }
        destination = addr

        if transport == .udp {
            let fd = socket(AF_INET, Int32(SOCK_DGRAM), 0)
            guard fd >= 0 else {
                throw NetworkManagerError.socketCreationFailed(errno)
            }
            // iOS's default UDP send buffer (9216 bytes) is smaller than a
            // camera JPEG frame, which makes sendto fail with EMSGSIZE.
            Self.setOption(fd, SOL_SOCKET, SO_SNDBUF, 65_535)
            socketFD = fd
        }
    }

    deinit {
        if let readSource {
            readSource.cancel() // cancel handler closes the fd
        } else if socketFD >= 0 {
            close(socketFD)
        }
    }

    var isConnected: Bool {
        queue.sync { transport == .udp || socketFD >= 0 }
    }

    // MARK: - Connection (TCP only)

    /// Blocks for up to `connectTimeoutMs`. Call it off the main thread.
    /// No-op for UDP or when already connected.
    func connect() throws {
        try queue.sync {
            guard transport == .tcp, socketFD < 0 else { return }
            let fd = try openTCPSocket()
            socketFD = fd
            monitorForDisconnect(fd)
        }
    }

    /// Closes the TCP connection without firing `onDisconnect`.
    func disconnect() {
        queue.sync {
            guard transport == .tcp else { return }
            tearDownTCP()
        }
    }

    // MARK: - Sending

    /// Encodes (compact, single-line JSON) and sends a message.
    func sendMessage<T: Encodable>(_ message: T) throws {
        let data = try encoder.encode(message)
        try send(data: data)
    }

    /// Sends pre-encoded bytes. For TCP the payload must not contain a raw
    /// newline, because newline is the message delimiter: pretty-printed
    /// JSON would arrive at the Jetson as many malformed fragments.
    func send(data: Data) throws {
        guard !data.isEmpty else {
            throw NetworkManagerError.emptyPayload
        }
        if transport == .tcp && data.contains(0x0A) {
            throw NetworkManagerError.payloadContainsDelimiter
        }

        // TCP is a byte stream with no built-in message boundaries, so each
        // payload needs an explicit delimiter; UDP datagrams are already
        // whole messages and need none.
        let framedData = transport == .tcp ? data + Data([0x0A]) : data

        try queue.sync {
            guard socketFD >= 0 else {
                throw NetworkManagerError.notConnected
            }

            do {
                let bytesSent = try framedData.withUnsafeBytes { buffer -> Int in
                    guard let baseAddress = buffer.baseAddress else {
                        throw NetworkManagerError.emptyPayload
                    }

                    let result: Int
                    switch transport {
                    case .udp:
                        var addr = destination
                        result = withUnsafePointer(to: &addr) { pointer in
                            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                                sendto(socketFD, baseAddress, buffer.count, 0, $0,
                                       socklen_t(MemoryLayout<sockaddr_in>.stride))
                            }
                        }
                    case .tcp:
                        result = Darwin.send(socketFD, baseAddress, buffer.count, 0)
                    }

                    guard result >= 0 else {
                        throw NetworkManagerError.sendFailed(code: errno, transport: transport)
                    }
                    return result
                }

                guard bytesSent == framedData.count else {
                    throw NetworkManagerError.partialSend(expected: framedData.count, actual: bytesSent)
                }
            } catch {
                if transport == .tcp {
                    tearDownTCP()
                    onDisconnect?(error)
                }
                throw error
            }
        }
    }

    // MARK: - Private (all on `queue`)

    private func openTCPSocket() throws -> Int32 {
        let fd = socket(AF_INET, Int32(SOCK_STREAM), 0)
        guard fd >= 0 else {
            throw NetworkManagerError.socketCreationFailed(errno)
        }

        // Without this, writing to a socket the Jetson has closed raises
        // SIGPIPE, which terminates the app.
        Self.setOption(fd, SOL_SOCKET, SO_NOSIGPIPE, 1)
        // Detect a pulled cable / dead Jetson within ~11 s. Keep-alive probes
        // are handled by the kernel, so this costs no app wake-ups.
        Self.setOption(fd, SOL_SOCKET, SO_KEEPALIVE, 1)
        Self.setOption(fd, IPPROTO_TCP, TCP_KEEPALIVE, 5)
        Self.setOption(fd, IPPROTO_TCP, TCP_KEEPINTVL, 2)
        Self.setOption(fd, IPPROTO_TCP, TCP_KEEPCNT, 3)
        Self.setOption(fd, IPPROTO_TCP, TCP_NODELAY, 1)

        // Non-blocking connect + poll so an unreachable Jetson can't hang the caller.
        let flags = fcntl(fd, F_GETFL, 0)
        _ = fcntl(fd, F_SETFL, flags | O_NONBLOCK)

        var connectAddress = destination
        let result = withUnsafePointer(to: &connectAddress) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.stride))
            }
        }

        if result != 0 {
            guard errno == EINPROGRESS else {
                let code = errno
                close(fd)
                throw NetworkManagerError.connectionFailed(host: host, port: port, code: code)
            }

            var pfd = pollfd(fd: fd, events: Int16(POLLOUT), revents: 0)
            let ready = poll(&pfd, 1, connectTimeoutMs)
            guard ready > 0 else {
                let code = ready == 0 ? ETIMEDOUT : errno
                close(fd)
                throw NetworkManagerError.connectionFailed(host: host, port: port, code: code)
            }

            var soError: Int32 = 0
            var length = socklen_t(MemoryLayout<Int32>.size)
            getsockopt(fd, SOL_SOCKET, SO_ERROR, &soError, &length)
            guard soError == 0 else {
                close(fd)
                throw NetworkManagerError.connectionFailed(host: host, port: port, code: soError)
            }
        }

        _ = fcntl(fd, F_SETFL, flags)
        return fd
    }

    /// The Jetson never sends anything back, so the socket only becomes
    /// readable when the connection closes or errors. This is event-driven
    /// (no polling timer), so it is free while the link is healthy.
    private func monitorForDisconnect(_ fd: Int32) {
        let source = DispatchSource.makeReadSource(fileDescriptor: fd, queue: queue)
        source.setEventHandler { [weak self] in
            guard let self else { return }
            var scratch = [UInt8](repeating: 0, count: 512)
            let count = recv(fd, &scratch, scratch.count, Int32(MSG_DONTWAIT))
            if count > 0 { return } // unexpected data: discard
            if count < 0, errno == EAGAIN || errno == EINTR { return }

            let error: Error = count == 0
                ? NetworkManagerError.closedByPeer
                : NetworkManagerError.sendFailed(code: errno, transport: .tcp)
            self.tearDownTCP()
            self.onDisconnect?(error)
        }
        source.setCancelHandler {
            close(fd)
        }
        readSource = source
        source.resume()
    }

    private func tearDownTCP() {
        if let readSource {
            readSource.cancel() // cancel handler closes the fd
            self.readSource = nil
        } else if socketFD >= 0 {
            close(socketFD)
        }
        socketFD = -1
    }

    private static func setOption(_ fd: Int32, _ level: Int32, _ name: Int32, _ value: Int32) {
        var value = value
        setsockopt(fd, level, name, &value, socklen_t(MemoryLayout<Int32>.size))
    }
}

nonisolated enum NetworkManagerError: Error, LocalizedError {
    case socketCreationFailed(Int32)
    case invalidAddress(String)
    case connectionFailed(host: String, port: UInt16, code: Int32)
    case notConnected
    case payloadContainsDelimiter
    case closedByPeer
    case emptyPayload
    case partialSend(expected: Int, actual: Int)
    case sendFailed(code: Int32, transport: NetworkManager.Transport)

    var errorDescription: String? {
        switch self {
        case .socketCreationFailed(let code):
            return "Couldn't create a network socket (errno \(code))."
        case .invalidAddress(let host):
            return "Invalid IPv4 address: \(host)"
        case .connectionFailed(let host, let port, let code):
            switch code {
            case ETIMEDOUT:
                return "Jetson at \(host):\(port) didn't respond. Is the phone on the Jetson's Wi-Fi hotspot?"
            case ECONNREFUSED:
                return "Jetson at \(host) refused the connection. Is waypoint_bridge_node running?"
            case ENETUNREACH, EHOSTUNREACH:
                return "Can't reach \(host). Is the phone on the Jetson's Wi-Fi hotspot, with Local Network access allowed?"
            default:
                return "Couldn't connect to \(host):\(port) (errno \(code))."
            }
        case .payloadContainsDelimiter:
            return "TCP payload contains a newline; send compact JSON."
        case .notConnected:
            return "Not connected to the Jetson."
        case .closedByPeer:
            return "The Jetson closed the connection."
        case .emptyPayload:
            return "Refusing to send an empty payload."
        case .partialSend(let expected, let actual):
            return "Sent \(actual) of \(expected) bytes."
        case .sendFailed(let code, let transport):
            return "Send over \(transport.rawValue.uppercased()) failed (errno \(code))."
        }
    }
}
