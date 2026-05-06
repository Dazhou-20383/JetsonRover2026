import cv2
import socket
import struct
import pickle

# Configuration
JETSON_AP_IP = '10.42.0.1' # The Jetson's IP in AP mode
PORT = 9999

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((JETSON_AP_IP, PORT))
data = b""
payload_size = struct.calcsize("Q")

print(f"[*] Connected to Jetson at {JETSON_AP_IP}")

while True:
    # 1. Retrieve the message size
    while len(data) < payload_size:
        packet = client_socket.recv(4096)
        if not packet: break
        data += packet
    
    packed_msg_size = data[:payload_size]
    data = data[payload_size:]
    msg_size = struct.unpack("Q", packed_msg_size)[0]

    # 2. Retrieve the frame data based on size
    while len(data) < msg_size:
        data += client_socket.recv(4096)
    
    frame_data = data[:msg_size]
    data = data[msg_size:]

    # 3. Deserialize and Decode
    frame_encoded = pickle.loads(frame_data)
    frame = cv2.imdecode(frame_encoded, cv2.IMREAD_COLOR)

    # 4. Display in GUI
    cv2.imshow('Jetson Live Stream', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

client_socket.close()
cv2.destroyAllWindows()