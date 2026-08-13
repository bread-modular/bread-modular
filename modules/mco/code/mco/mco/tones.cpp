#include <avr/io.h>
#include <avr/interrupt.h>

const long CLOCK_TIME = 20000000;
const int TIMER_DIV = 2;
const int MANUAL_DIV = 4;
float TICK_TIME_SEC = (1.0/(CLOCK_TIME / TIMER_DIV / MANUAL_DIV ));

void setupTone1() {
    // Set PB4 as output for Tone1
    PORTB.DIRSET = PIN4_bm;
    
    TCB0.CCMP = 65535; // Set the compare value
    TCB0.CTRLA |= TCB_ENABLE_bm; // counting value

    // Uses 20Mhz clock & divide it by for here
    TCB0.CTRLA |= TCB_CLKSEL_CLKDIV2_gc; // clock div by 2
  
    // Enabling inturrupts
    TCB0.CTRLB |= TCB_CNTMODE_INT_gc; // Timer interrupt mode (periodic interrupts)
    TCB0.INTCTRL = TCB_CAPT_bm; // Enable Capture interrupt
    sei();
}

// TCB0 Interrupt Service Routine
int tcb0SubScalerCnt = 0;
ISR(TCB0_INT_vect) {
  // Here with 20Mhz clock speed & 2div clockdiv 
  // we cannot acheive 20Hz
  // That's why we are manually subscaling here
  // NOTE: Do not use tcb0SubScalerCnt++ == 4 here. I will affect the timer
  if (tcb0SubScalerCnt == MANUAL_DIV) {
    tcb0SubScalerCnt = 0;
    PORTB.OUTTGL = PIN4_bm;
  }

  tcb0SubScalerCnt++;

  // Clear the interrupt flag
  TCB0.INTFLAGS = TCB_CAPT_bm;
}

void setTone1Frequency(int freq) {
  float period = 1.0 / freq ;
  float halfPeriod = period / 2;
  long periodTicks = halfPeriod / TICK_TIME_SEC;

  TCB0.CCMP = periodTicks;
  // Serial.printf("Set Freq: periodUs: %ld\n", periodTicks);
}


void setupTone2() {
    // Set PB5 as output for Tone2
    PORTB.DIRSET = PIN5_bm;
    
    TCB1.CCMP = 65535; // Set the compare value (we will change this later)
    TCB1.CTRLA |= TCB_ENABLE_bm; // enable the counter

    // Uses 20Mhz clock & divide it by 2
    TCB1.CTRLA |= TCB_CLKSEL_CLKDIV2_gc; // clock div by 2
  
    // Enabling inturrupts
    TCB1.CTRLB |= TCB_CNTMODE_INT_gc; // Timer interrupt mode (periodic interrupts)
    TCB1.INTCTRL = TCB_CAPT_bm; // Enable Capture interrupt
    sei();
}

// TCB1 Interrupt Service Routine
int tcb1SubScalerCnt = 0;
ISR(TCB1_INT_vect) {
  // Here with 20Mhz clock speed & 2div clockdiv 
  // we cannot acheive 20Hz
  // That's why we are manually subscaling here
  // NOTE: Do not use tcb0SubScalerCnt++ == 4 here. I will affect the timer
  if (tcb1SubScalerCnt == MANUAL_DIV) {
    tcb1SubScalerCnt = 0;
    PORTB.OUTTGL = PIN5_bm;
  }

  tcb1SubScalerCnt++;

  // Clear the interrupt flag
  TCB1.INTFLAGS = TCB_CAPT_bm;
}

void setTone2Frequency(int freq) {
  float period = 1.0 / freq ;
  float halfPeriod = period / 2;
  long periodTicks = halfPeriod / TICK_TIME_SEC;

  TCB1.CCMP = periodTicks;
  // Serial.printf("Set Freq: periodUs: %ld\n", periodTicks);
}