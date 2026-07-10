
#include <Arduino.h>
#include <Servo.h>
#include <stdlib.h>
 
namespace {
 
constexpr size_t kWheelCount = 6;
constexpr size_t kValuesPerWheel = 2;
constexpr size_t kExpectedValues = kWheelCount * kValuesPerWheel;
constexpr size_t kLineBufferSize = 160;
 
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
		{20, -1, 10, true, 1500},   // front-left
		{21, -1, 11, true, 1500},   // front-right
		{6, -1, 24, false},  // middle-left: ignored
		{9, -1, 25, false},  // middle-right: ignored
		{22, -1, 12, true, 1700},  // rear-left
		{23, -1, 13, true, 1700},  // rear-right
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
	// normalized is in [-0.5, 0.5] for angleCommand in [-45, 45] degrees.
	const float normalized = clampFloat(angleCommand, -45.0f, 45.0f) / 90.0f;
 
	const int pulseWidthUs = ServoInitUs + static_cast<int>(lroundf(normalized * 500.0f));
 
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
 
void printAppliedValues(const float *values) {
	Serial.print(F("OK:"));
	for (size_t i = 0; i < kExpectedValues; ++i) {
		Serial.print(' ');
		Serial.print(values[i], 3);
		if (i + 1 < kExpectedValues) {
			Serial.print(',');
		}
	}
	Serial.println();
}
 
void processLine(char *line) {
	// parseCsvFloats mutates `line` in place via strtok, so keep an
	// unmodified copy around in case we need to report it on error.
	char rawLineCopy[kLineBufferSize];
	strncpy(rawLineCopy, line, kLineBufferSize - 1);
	rawLineCopy[kLineBufferSize - 1] = '\0';
 
	float values[kExpectedValues];
	if (!parseCsvFloats(line, values, kExpectedValues)) {
		Serial.print(F("ERR: expected "));
		Serial.print(kExpectedValues);
		Serial.print(F(" comma-separated values, got line: "));
		Serial.println(rawLineCopy);
		return;
	}
 
	applyCommand(values);
	printAppliedValues(values);
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

void test(const float payload[]){
  applyCommand(payload);
	delay(1000);
}

}  // namespace

void setup() {
	Serial.begin(115200);
	setupPins();
	Serial.println(F("Arduino bridge ready"));
	delay(3000);
}

void loop() {
	readSerial();
}

// void loop() {
// 	const float P1[12] = {0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 30.00, 0.00, 0.00};
// 	test(P1);
// 	const float P2[12] = {0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 30.00, 0.00, 0.00, 0.00, 30.00};
// 	test(P2);
// 	const float P3[12] = {0.0, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, -30.00, 0.00, 0.00};
// 	test(P3);
// 	const float P4[12] = {0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, -30.00, 0.00, 0.00, 0.00, -30.00};
// 	test(P4);
//   Serial.println("================================");
// }
