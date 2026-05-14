import Foundation
import Darwin

final class PoseSender {
    private let host: String
    private let port: UInt16
    private let socketFD: Int32
    private var destination = sockaddr_in()

    init(host: String, port: UInt16 = 5005) throws {
        self.host = host
        self.port = port

        socketFD = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        guard socketFD >= 0 else {
            throw PoseSenderError.socketCreationFailed(errno)
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
            throw PoseSenderError.invalidAddress(host)
        }

        destination = addr
    }

    deinit {
        close(socketFD)
    }

    func send(x: Float, y: Float, yaw: Float) {
        let payload = PosePayload(x: x, y: y, yaw: yaw)

        guard let data = try? JSONEncoder().encode(payload) else {
            return
        }

        data.withUnsafeBytes { buffer in
            guard let baseAddress = buffer.baseAddress else {
                return
            }

            var addr = destination
            withUnsafePointer(to: &addr) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                    _ = sendto(
                        socketFD,
                        baseAddress,
                        buffer.count,
                        0,
                        sockaddrPointer,
                        socklen_t(MemoryLayout<sockaddr_in>.stride)
                    )
                }
            }
        }
    }
}

private struct PosePayload: Codable {
    let x: Float
    let y: Float
    let yaw: Float
}

enum PoseSenderError: Error, LocalizedError {
    case socketCreationFailed(Int32)
    case invalidAddress(String)

    var errorDescription: String? {
        switch self {
        case .socketCreationFailed(let code):
            return "Failed to create UDP socket (errno \(code))."
        case .invalidAddress(let host):
            return "Invalid IPv4 address: \(host)"
        }
    }
}
