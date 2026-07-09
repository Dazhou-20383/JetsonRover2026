#include <Arduino.h>
#include <Servo.h>
#include <stdlib.h>

namespace {

constexpr size_t kWheelCount = 6;
constexpr size_t kValuesPerWheel = 2;
constexpr size_t kExpectedValues = kWheelCount * kValuesPerWheel;
constexpr size_t kLineBufferSize = 128;

constexpr int kMotorPwmMin = 0;
constexpr int kMotorPwmMax = 255;

// Allows for only 90deg rotation, initial position is in the middle
// Setup procedure: ensure servo is facing front
// run init servo
// mount the wheels facing straight
// constexpr int kServoInitUs = 1500;
constexpr int kServoMinUs = 1000;
constexpr int kServoMaxUs = 2000;

struct WheelChannel {
	uint8_t motorPwmPin;
	int8_t motorDirectionPin;
	uint8_t steeringServoPin;
	bool enabled;
	int ServoInitUs;
	Servo servo;
};

// Edit these pins to match your Arduino wiring.
WheelChannel kWheels[kWheelCount] = {
		{20, -1, 10, true, 1700},   // front-left
		{21, -1, 11, true, 1800},   // front-right
		{6, -1, 24, false},  // middle-left: ignored
		{9, -1, 25, false},  // middle-right: ignored
		{22, -1, 12, true, 1500},  // rear-left
		{23, -1, 13, true, 1500},  // rear-right
};

char gLineBuffer[kLineBufferSize];
size_t gLineLength = 0;

float clampFloat(float value, float low, float high) {
	if (value < low) {
		return low;
	}
	if (value > high) {
		return high;
	}
	return value;
}

int clampInt(int value, int low, int high) {
	if (value < low) {
		return low;
	}
	if (value > high) {
		return high;
	}
	return value;
}

bool parseCsvFloats(char *line, float *values, size_t expectedCount) {
	size_t parsedCount = 0;
	char *token = strtok(line, ",");

	while (token != nullptr && parsedCount < expectedCount) {
		while (*token == ' ' || *token == '\t' || *token == '[' || *token == ']') {
			++token;
		}

		values[parsedCount] = atof(token);

		++parsedCount;
		token = strtok(nullptr, ",");
	}

	return parsedCount == expectedCount;
}

int speedToPwm(float speedCommand) {
	const float normalized = clampFloat(speedCommand, -1.0f, 1.0f);
	const float magnitude = fabsf(normalized);
	const int pwm = static_cast<int>(lroundf(
			kMotorPwmMin + (kMotorPwmMax - kMotorPwmMin) * magnitude));
	return clampInt(pwm, kMotorPwmMin, kMotorPwmMax);
}

int angleToServoUs(float angleCommand, int ServoInitUs = 1500) {
	const float normalized = clampFloat(angleCommand, -45.0f, 45.0f) / 90;

	int pulseWidthUs = ServoInitUs;
	if (normalized >= 0.0f) {
		pulseWidthUs += static_cast<int>(lroundf(ServoInitUs + normalized * 500));
	} else {
		pulseWidthUs += static_cast<int>(lroundf(ServoInitUs - normalized * 500));
	}

	return clampInt(pulseWidthUs, kServoMinUs, kServoMaxUs);
}

void applyWheelCommand(size_t wheelIndex, float speedCommand, float angleCommand) {
	WheelChannel &wheel = kWheels[wheelIndex];
	if (!wheel.enabled) {
		return;
	}

	if (wheel.motorDirectionPin >= 0) {
		digitalWrite(wheel.motorDirectionPin, speedCommand < 0.0f ? LOW : HIGH);
	}
  int speed_pwm = speedToPwm(speedCommand);
	analogWrite(wheel.motorPwmPin, speed_pwm);
  int servo_pwm = angleToServoUs(angleCommand, wheel.ServoInitUs);
	wheel.servo.writeMicroseconds(servo_pwm);
//   Serial.print("PWM: ");
//   Serial.print(speed_pwm);
//   Serial.print("; servo: ");
//   Serial.println(servo_pwm);
}

void applyCommand(const float *values) {
	for (size_t wheelIndex = 0; wheelIndex < kWheelCount; ++wheelIndex) {
		const size_t valueIndex = wheelIndex * kValuesPerWheel;
    // Serial.print("Wheel index: ");
    // Serial.println(wheelIndex);
		applyWheelCommand(wheelIndex, values[valueIndex], values[valueIndex + 1]);
	}
}

void processLine(char *line) {
	float values[kExpectedValues];
	if (!parseCsvFloats(line, values, kExpectedValues)) {
		Serial.println(F("ERR: expected 12 comma-separated values"));
		return;
	}

	applyCommand(values);
}

void setupPins() {
	for (size_t wheelIndex = 0; wheelIndex < kWheelCount; ++wheelIndex) {
		WheelChannel &wheel = kWheels[wheelIndex];
		if (!wheel.enabled) {
			continue;
		}

		pinMode(wheel.motorPwmPin, OUTPUT);
		analogWrite(wheel.motorPwmPin, kMotorPwmMin);

		if (wheel.motorDirectionPin >= 0) {
			pinMode(wheel.motorDirectionPin, OUTPUT);
			digitalWrite(wheel.motorDirectionPin, HIGH);
		}

		wheel.servo.attach(wheel.steeringServoPin, kServoMinUs, kServoMaxUs);
		wheel.servo.writeMicroseconds(wheel.ServoInitUs);
	}
}

void readSerial() {
	while (Serial.available() > 0) {
		const char incoming = static_cast<char>(Serial.read());

		if (incoming == '\n' || incoming == '\r') {
			if (gLineLength == 0) {
				continue;
			}

			gLineBuffer[gLineLength] = '\0';
			processLine(gLineBuffer);
			gLineLength = 0;
			continue;
		}

		if (gLineLength < kLineBufferSize - 1) {
			gLineBuffer[gLineLength++] = incoming;
		} else {
			gLineLength = 0;
			Serial.println(F("ERR: command too long"));
		}
	}
}

void test(){
  const float EXAMPLE_PAYLOAD[12] = {0.60, 30.00, 0.00, 0.00, 0.00, 0.00,0.00, 0.00, 0.00, 0.00, 0.00, 0.00};

  applyCommand(EXAMPLE_PAYLOAD);
}

}  // namespace

void setup() {
	Serial.begin(115200);
	setupPins();
	Serial.println(F("Arduino bridge ready"));
}

void loop() {
	readSerial();
}

// void loop() {
// 	test();
//   	Serial.println("================================");
// }
