
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

constexpr int8_t motorDirectionPinRight1 = 4;
constexpr int8_t motorDirectionPinRight2 = 2;
constexpr int8_t motorDirectionPinLeft1 = 7;
constexpr int8_t motorDirectionPinLeft2 = 8;
 
// Allows for only 90deg rotation, initial position is in the middle
// Setup procedure: ensure servo is facing front
// run init servo
// mount the wheels facing straight
// constexpr int kServoInitUs = 1500;
constexpr int kServoMinUs = 1000;
constexpr int kServoMaxUs = 2000;
 
struct WheelChannel {
	uint8_t motorPwmPin;
	bool isRight;
	bool reversed;
	uint8_t steeringServoPin;
	bool enabled;
	int ServoInitUs;
	Servo servo;
};
 
// Edit these pins to match your Arduino wiring.
WheelChannel kWheels[kWheelCount] = {
		{11, false, true, 13, true, 1550},   // front-left
		{5, true, true, 12, true, 1600},   // front-right
		{-1, false, false, 0, false},  // middle-left: ignored
		{-1, true, false, 0, false},  // middle-right: ignored
		{6, false, true, 10, true, 1500},  // rear-left
		{3, true, true, 9, true, 1550},  // rear-right
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
	const float normalized = clampFloat(angleCommand, -45.0f, 45.0f) / 45.0f;
 
	const int pulseWidthUs = ServoInitUs + static_cast<int>(lroundf(normalized * 400.0f));
 
	return clampInt(pulseWidthUs, kServoMinUs, kServoMaxUs);
}

void setMotorDirection(WheelChannel &wheel, int mode){

	int8_t motorDirectionPin1 = wheel.isRight ? motorDirectionPinRight1 : motorDirectionPinLeft1;
	int8_t motorDirectionPin2 = wheel.isRight ? motorDirectionPinRight2 : motorDirectionPinLeft2;
	int _mode = mode * (wheel.reversed ? -1 : 1);

	if (_mode == 1){
			digitalWrite(motorDirectionPin1, HIGH);
			digitalWrite(motorDirectionPin2, LOW);
	} else if (_mode == -1){
			digitalWrite(motorDirectionPin1, LOW);
			digitalWrite(motorDirectionPin2, HIGH);
	}
}
 
void applyWheelCommand(size_t wheelIndex, float speedCommand, float angleCommand) {
	WheelChannel &wheel = kWheels[wheelIndex];
	if (!wheel.enabled) {
		return;
	}

	int forward = (speedCommand >= 0) ? 1 : -1;
	setMotorDirection(wheel, forward);

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

		pinMode(motorDirectionPinRight1, OUTPUT);
		digitalWrite(motorDirectionPinRight1, LOW);
		pinMode(motorDirectionPinRight2, OUTPUT);
		digitalWrite(motorDirectionPinRight2, LOW);
		pinMode(motorDirectionPinLeft1, OUTPUT);
		digitalWrite(motorDirectionPinLeft1, LOW);
		pinMode(motorDirectionPinLeft2, OUTPUT);
		digitalWrite(motorDirectionPinLeft2, LOW);
 
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
	delay(5000);
}

void loop() {
	readSerial();
}

// void loop() {
// 	const float P1[12] = {0.30, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.30, 00.00, 0.00, 0.00};
// 	test(P1);
// 	const float P2[12] = {0.00, 0.00, -0.30, 0.00, 0.00, 0.00, 0.00, 00.00, 0.00, 0.00, -0.30, 00.00};
// 	test(P2);
// 	const float P3[12] = {-0.30, 0.00, 0.00, 0.00, 00.00, 0.00, 0.00, 0.00, -0.30, 0.00, 0.00, 0.00};
// 	test(P3);
// 	const float P4[12] = {0.00, 0.00, 0.30, 0.00, 0.00, 0.00, 0.00, 00.00, 0.00, 0.00, 0.30, 00.00};
// 	test(P4);
//   Serial.println("================================");
// }
