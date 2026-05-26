#include <Arduino.h>
#include <Servo.h>
#include <errno.h>
#include <stdlib.h>

namespace {

constexpr unsigned long kBaudRate = 115200;
constexpr size_t kWheelCount = 6;
constexpr size_t kServoCount = 4;
constexpr size_t kValuesPerWheel = 2;
constexpr size_t kExpectedValueCount = kWheelCount * kValuesPerWheel;
constexpr size_t kMaxPacketLength = 128;
constexpr float kVelocityScale = 1000.0f;
constexpr float kAngleScale = 1000.0f;

enum WheelIndex : size_t {
  FRONT_LEFT = 0,
  FRONT_RIGHT = 1,
  MIDDLE_LEFT = 2,
  MIDDLE_RIGHT = 3,
  REAR_LEFT = 4,
  REAR_RIGHT = 5,
};

enum DriveSide : size_t {
  LEFT_SIDE = 0,
  RIGHT_SIDE = 1,
};

struct WheelCommand {
  int32_t velocity_raw = 0;
  int32_t angle_raw = 0;
};

struct RoverCommand {
  WheelCommand wheels[kWheelCount];
};

struct ServoCalibration {
  Servo servo;
  uint8_t pin;
  int center_us;
  float radians_to_us;
  int min_us;
  int max_us;
};

char serial_buffer[kMaxPacketLength];
size_t serial_index = 0;
bool packet_overflow = false;
RoverCommand latest_command;

// Update these pins and calibration values for your hardware.
ServoCalibration steering_servos[kServoCount] = {
    {Servo(), 3, 1500, 318.0f, 1000, 2000},   // Front left
    {Servo(), 5, 1500, -318.0f, 1000, 2000},  // Front right
    {Servo(), 6, 1500, 318.0f, 1000, 2000},   // Rear left
    {Servo(), 9, 1500, -318.0f, 1000, 2000},  // Rear right
};

long parseLongToken(const char* token, bool& ok) {
  if (token == nullptr || *token == '\0') {
    ok = false;
    return 0;
  }

  errno = 0;
  char* end_ptr = nullptr;
  long value = strtol(token, &end_ptr, 10);
  if (errno != 0 || end_ptr == token || *end_ptr != '\0') {
    ok = false;
    return 0;
  }

  ok = true;
  return value;
}

bool parseMotorPacket(char* packet, RoverCommand& command) {
  char* token = strtok(packet, ",");
  if (token == nullptr || strcmp(token, "M") != 0) {
    return false;
  }

  long values[kExpectedValueCount];
  for (size_t i = 0; i < kExpectedValueCount; ++i) {
    bool ok = false;
    token = strtok(nullptr, ",");
    values[i] = parseLongToken(token, ok);
    if (!ok) {
      return false;
    }
  }

  // Reject packets with trailing unexpected fields.
  if (strtok(nullptr, ",") != nullptr) {
    return false;
  }

  for (size_t wheel = 0; wheel < kWheelCount; ++wheel) {
    command.wheels[wheel].velocity_raw = static_cast<int32_t>(values[wheel * 2]);
    command.wheels[wheel].angle_raw = static_cast<int32_t>(values[wheel * 2 + 1]);
  }

  return true;
}

float velocityFromRaw(int32_t raw_value) {
  return static_cast<float>(raw_value) / kVelocityScale;
}

float angleFromRaw(int32_t raw_value) {
  return static_cast<float>(raw_value) / kAngleScale;
}

float averageVelocityForSide(const RoverCommand& command, DriveSide side) {
  if (side == LEFT_SIDE) {
    return (
        velocityFromRaw(command.wheels[FRONT_LEFT].velocity_raw) +
        velocityFromRaw(command.wheels[MIDDLE_LEFT].velocity_raw) +
        velocityFromRaw(command.wheels[REAR_LEFT].velocity_raw)) / 3.0f;
  }

  return (
      velocityFromRaw(command.wheels[FRONT_RIGHT].velocity_raw) +
      velocityFromRaw(command.wheels[MIDDLE_RIGHT].velocity_raw) +
      velocityFromRaw(command.wheels[REAR_RIGHT].velocity_raw)) / 3.0f;
}

int servoPulseFromAngle(float angle_radians, const ServoCalibration& calibration) {
  long pulse = lroundf(
      static_cast<float>(calibration.center_us) +
      angle_radians * calibration.radians_to_us);
  if (pulse < calibration.min_us) {
    pulse = calibration.min_us;
  }
  if (pulse > calibration.max_us) {
    pulse = calibration.max_us;
  }
  return static_cast<int>(pulse);
}

void applySteering(const RoverCommand& command) {
  const size_t wheel_map[kServoCount] = {
      FRONT_LEFT,
      FRONT_RIGHT,
      REAR_LEFT,
      REAR_RIGHT,
  };

  for (size_t i = 0; i < kServoCount; ++i) {
    const float angle = angleFromRaw(command.wheels[wheel_map[i]].angle_raw);
    const int pulse = servoPulseFromAngle(angle, steering_servos[i]);
    steering_servos[i].servo.writeMicroseconds(pulse);
  }
}

void setDriveMotor(size_t wheel, float velocity_mps) {
  // Replace this stub with your motor driver implementation.
  // Example responsibilities:
  // - choose motor direction from the sign of velocity_mps
  // - convert magnitude to PWM or RPM setpoint
  // - send the value to a driver, ESC, or CAN/UART bridge
  (void)wheel;
  (void)velocity_mps;
}

void applyDrive(const RoverCommand& command) {
  const float left_velocity = averageVelocityForSide(command, LEFT_SIDE);
  const float right_velocity = averageVelocityForSide(command, RIGHT_SIDE);

  setDriveMotor(FRONT_LEFT, left_velocity);
  setDriveMotor(MIDDLE_LEFT, left_velocity);
  setDriveMotor(REAR_LEFT, left_velocity);

  setDriveMotor(FRONT_RIGHT, right_velocity);
  setDriveMotor(MIDDLE_RIGHT, right_velocity);
  setDriveMotor(REAR_RIGHT, right_velocity);
}

void printParsedCommand(const RoverCommand& command) {
  Serial.print("RX");
  for (size_t wheel = 0; wheel < kWheelCount; ++wheel) {
    Serial.print(',');
    Serial.print(command.wheels[wheel].velocity_raw);
    Serial.print(',');
    Serial.print(command.wheels[wheel].angle_raw);
  }
  Serial.print(",L,");
  Serial.print(averageVelocityForSide(command, LEFT_SIDE), 3);
  Serial.print(",R,");
  Serial.println(averageVelocityForSide(command, RIGHT_SIDE), 3);
}

void processPacket(char* packet) {
  RoverCommand parsed_command;
  if (!parseMotorPacket(packet, parsed_command)) {
    Serial.println("ERR,PARSE");
    return;
  }

  latest_command = parsed_command;
  printParsedCommand(latest_command);
  applySteering(latest_command);
  applyDrive(latest_command);
  Serial.println("OK");
}

void readSerialPackets() {
  while (Serial.available() > 0) {
    const char byte_read = static_cast<char>(Serial.read());

    if (byte_read == '\r') {
      continue;
    }

    if (byte_read == '\n') {
      if (!packet_overflow && serial_index > 0) {
        serial_buffer[serial_index] = '\0';
        processPacket(serial_buffer);
      } else if (packet_overflow) {
        Serial.println("ERR,OVERFLOW");
      }

      serial_index = 0;
      packet_overflow = false;
      continue;
    }

    if (packet_overflow) {
      continue;
    }

    if (serial_index >= kMaxPacketLength - 1) {
      packet_overflow = true;
      continue;
    }

    serial_buffer[serial_index++] = byte_read;
  }
}

}  // namespace

void setup() {
  Serial.begin(kBaudRate);

  for (size_t i = 0; i < kServoCount; ++i) {
    steering_servos[i].servo.attach(steering_servos[i].pin);
    steering_servos[i].servo.writeMicroseconds(steering_servos[i].center_us);
  }

  Serial.println("READY");
}

void loop() {
  readSerialPackets();
}
