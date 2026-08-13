#include <Arduino.h>
#include <EEPROM.h>

#define PIN_CV1 PIN_PA7
#define PIN_CV2 PIN_PB0
#define PIN_TOGGLE PIN_PA3

#define LED_MODE_0 PIN_PB5
#define LED_MODE_1 PIN_PC0
#define LED_MODE_2 PIN_PC1
#define LED_MODE_3 PIN_PC2
#define LED_MODE_4 PIN_PC3

const byte totalModes = 5;
volatile byte mode = 0;
volatile unsigned long toggleTime = 0;

void enableLED(byte pin) {
  digitalWrite(LED_MODE_0, LOW);
  digitalWrite(LED_MODE_1, LOW);
  digitalWrite(LED_MODE_2, LOW);
  digitalWrite(LED_MODE_3, LOW);
  digitalWrite(LED_MODE_4, LOW);

  digitalWrite(pin, HIGH);
}

void handleTogglePinChange() {
  const int toggleValue = digitalRead(PIN_TOGGLE);
  if (toggleValue == LOW) {
    if (toggleTime > 0) {
      return;
    }

    toggleTime = millis();
    return;
  }

  // We are still in the HIGH state
  if (toggleTime == 0) {
    return;
  }

  // If this is HIGH
  const unsigned long timeDiff = millis() - toggleTime;
  if (timeDiff < 200) {
    toggleTime = 0;
    return;
  }
  
  // All set & change the mode
  mode += 1;
  if (mode >= totalModes) {
    mode = 0;
  }
  EEPROM.write(0, mode);
  Serial.printf("Mode changed to: %d\n", mode);
  toggleTime = 0;
} 

void mode_add() {
  float cv1 = analogRead(PIN_CV1) / 1023.0;
  float cv2 = analogRead(PIN_CV2) / 1023.0;
  DAC0.DATA = constrain((cv1 + cv2), 0.0, 1.0) * 255;
}

void mode_subtract() {
  float cv1 = analogRead(PIN_CV1) / 1023.0;
  float cv2 = analogRead(PIN_CV2) / 1023.0;
  DAC0.DATA = constrain((cv1 - cv2), 0.0, 1.0) * 255;
}

// Variables to track waveform stats
uint16_t sampleHighestValue = 0;        // Highest amplitude detected
uint16_t sampleLowestValue = 1023;      // Lowest amplitude detected
float outputLowestValue = 1023; // Smoothed lowest value (weighted average)
float outputHighestValue = 0;   // Smoothed highest value (weighted average)
float alpha = 0.9;
unsigned long lastCheckedAt = 0;

void mode_xpand() {
  int cv1 = analogRead(PIN_CV1);
  float normalizedCv2 = analogRead(PIN_CV2) / 1023.0;

  // Update the highest value
  if (cv1 > sampleHighestValue) {
    sampleHighestValue = cv1;
  }

  // Update the lowest value
  if (cv1 < sampleLowestValue) {
    sampleLowestValue = cv1;
  }

  if ((millis() - lastCheckedAt) > 1000) {
    outputLowestValue = alpha * sampleLowestValue + (1 - alpha) * outputLowestValue;
    outputHighestValue = alpha * sampleHighestValue + (1 - alpha) * outputHighestValue;

    // Reset values after the sample processed
    lastCheckedAt = millis();
    sampleHighestValue = 0;
    sampleLowestValue = 1023;
  }

  float normalizedCV1 = cv1 / 1023.0;
  float maxScale = 1023.0 / outputHighestValue;

  // We use this distance as a scale factor.
  // So the bottom of the waveform will stay as there
  // only the top values scales according to the distance
  int fullAmplitude = outputHighestValue - outputLowestValue;
  int distance = cv1 - outputLowestValue;
  float distanceNormalized = distance / (float)fullAmplitude;
  
  float xpandCV1 = normalizedCV1 * maxScale;
  float diff = xpandCV1 - normalizedCV1;

  DAC0.DATA = (normalizedCV1 + diff * normalizedCv2 * distanceNormalized) * 255;
}

void setup() {
  // DAC0 setup via the PA6 pin
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc; //this will force it to use VDD as the VREF
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0;

  analogReference(VDD);
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);

  pinMode(PIN_TOGGLE, INPUT_PULLUP);
  pinMode(LED_MODE_0, OUTPUT);
  pinMode(LED_MODE_1, OUTPUT);
  pinMode(LED_MODE_2, OUTPUT);
  pinMode(LED_MODE_3, OUTPUT);
  pinMode(LED_MODE_4, OUTPUT);
  mode = EEPROM.read(0);

  Serial.begin(9600);
  Serial.println("CV_MATH Started!");
}

void loop() {
  handleTogglePinChange();

  switch (mode)
  {
    case 0:
      enableLED(LED_MODE_0);
      mode_add();
      break;

    case 1:
      enableLED(LED_MODE_1);
      mode_subtract();
      break;
    
    case 2:
      enableLED(LED_MODE_2);
      mode_xpand();
      break;

    case 3:
      enableLED(LED_MODE_3);
      break;

    case 4:
      enableLED(LED_MODE_4);
      break;
    
    default:
      break;
  }
}
