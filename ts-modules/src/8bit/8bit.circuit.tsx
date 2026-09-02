/**
 * Bread Modular — "8bit" module (tscircuit port of modules/8bit, board 1.1.0)
 * ---------------------------------------------------------------------------
 * A tinyAVR digital sound module. ATtiny1616 (U2) generates the audio
 * (PWM via PA6) + gate (PA7), reads CV1/CV2 and MIDI, and cycles firmware
 * presets with the MODE push button:
 *
 *   AUDIO:  U2 PA6 -> RV1 50k (LOWPASS / level) -> [RC w/ C2 to VMID]
 *           -> U1A unity buffer -> R2 1k -> AUDIO_OUT (bus pins 2-3)
 *   GATE:   U2 PA7 -> U1B unity buffer -> R3 1k -> GATE_OUT (bus pins 4-5)
 *   CV1:    INPUT1.2 -> [R7 100k pull-up] -> U3A unity buffer -> RV2 1M
 *           (attenuator) -> BUFF_CV1 -> U2 PA1
 *   CV2:    INPUT1.3 -> [R8 100k pull-up] -> U3B unity buffer -> RV3 1M
 *           (attenuator) -> BUFF_CV2 -> U2 PA2
 *   MIDI:   INPUT1.1 / OUTPUT1.1 (MIDI in on PB3/RX, THRU out on PB2/TX)
 *   UPDI:   INPUT1.5 -> R1 4.7k -> U2 PA0 (programming)
 *   MODE:   SW1 (K2-1808SN tact) pulls PA4 to GND
 *   LED:    U2 PA5 -> D1 0603 LED -> R6 330 -> GND
 *
 * R4/R5 (1k) generate VMID; C1 100uF bulk + C3/C4 0.1uF decoupling.
 * Netlist is a faithful 1:1 port of modules/8bit/production/netlist.ipc
 * (U1/U3 = MCP6002 dual op-amps, SOIC-8; U2 = ATtiny1616-M, VQFN-20 3x3mm).
 *
 * Layout mirrors the KiCad original: op-amp row + CV pots in the upper half,
 * U2/SW1/LED in the middle, RV1 LOWPASS + power divider at the bottom.
 */
import {
  BreadModule,
  MCP6002,
  NET_GND,
  NET_VMID,
  NET_VSUPPLY,
  RV09Pot,
} from "../../lib";

/* ------------------------------------------------------------------ */
/* U2 — ATtiny1616-M, VQFN-20 3x3mm P0.4mm EP 1.7x1.7mm                */
/* (KiCad Package_DFN_QFN:VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm;        */
/*  Microchip VQFN pad numbering: 1=PA2 ... 20=PA1, 21=EP=GND)         */
/* ------------------------------------------------------------------ */
const VQFN20_ATtiny1616 = () => (
  <footprint>
    {/* Left side, pins 1-5 (0.4mm pitch, 0.8 x 0.2mm pads) */}
    <smtpad shape="rect" portHints={["pin1"]} pcbX={-1.45} pcbY={0.8} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin2"]} pcbX={-1.45} pcbY={0.4} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin3"]} pcbX={-1.45} pcbY={0} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin4"]} pcbX={-1.45} pcbY={-0.4} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin5"]} pcbX={-1.45} pcbY={-0.8} width={0.8} height={0.2} />
    {/* Bottom side, pins 6-10 */}
    <smtpad shape="rect" portHints={["pin6"]} pcbX={-0.8} pcbY={-1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin7"]} pcbX={-0.4} pcbY={-1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin8"]} pcbX={0} pcbY={-1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin9"]} pcbX={0.4} pcbY={-1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin10"]} pcbX={0.8} pcbY={-1.45} width={0.2} height={0.8} />
    {/* Right side, pins 11-15 */}
    <smtpad shape="rect" portHints={["pin11"]} pcbX={1.45} pcbY={-0.8} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin12"]} pcbX={1.45} pcbY={-0.4} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin13"]} pcbX={1.45} pcbY={0} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin14"]} pcbX={1.45} pcbY={0.4} width={0.8} height={0.2} />
    <smtpad shape="rect" portHints={["pin15"]} pcbX={1.45} pcbY={0.8} width={0.8} height={0.2} />
    {/* Top side, pins 16-20 */}
    <smtpad shape="rect" portHints={["pin16"]} pcbX={0.8} pcbY={1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin17"]} pcbX={0.4} pcbY={1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin18"]} pcbX={0} pcbY={1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin19"]} pcbX={-0.4} pcbY={1.45} width={0.2} height={0.8} />
    <smtpad shape="rect" portHints={["pin20"]} pcbX={-0.8} pcbY={1.45} width={0.2} height={0.8} />
    {/* Exposed pad (pin 21) + via-in-pad. The EP is fenced in by the QFN
        pads (0.2mm gaps — even a 0.15mm trace can't legally escape: a
        mid-gap run leaves only ~0.09mm clearance), so — like a classic
        QFN layout — GND drops through this via onto the bottom pour.
        No PCB trace is declared to the EP. */}
    <smtpad shape="rect" portHints={["pin21"]} pcbX={0} pcbY={0} width={1.7} height={1.7} />
    <platedhole portHints={["pin21"]} pcbX={0} pcbY={0} holeDiameter="0.3mm" outerDiameter="0.5mm" />
    {/* Corner silkscreen brackets + pin-1 mark (KiCad F.SilkS, 0.12mm) */}
    <silkscreenline x1={1.61} y1={1.61} x2={1.61} y2={1.16} strokeWidth={0.12} />
    <silkscreenline x1={1.16} y1={1.61} x2={1.61} y2={1.61} strokeWidth={0.12} />
    {/* pin-1 corner (shorter brackets) */}
    <silkscreenline x1={-1.16} y1={1.61} x2={-1.31} y2={1.61} strokeWidth={0.12} />
    <silkscreenline x1={-1.61} y1={1.16} x2={-1.61} y2={1.37} strokeWidth={0.12} />
    <silkscreenline x1={1.61} y1={-1.61} x2={1.61} y2={-1.16} strokeWidth={0.12} />
    <silkscreenline x1={1.16} y1={-1.61} x2={1.61} y2={-1.61} strokeWidth={0.12} />
    <silkscreenline x1={-1.16} y1={-1.61} x2={-1.61} y2={-1.61} strokeWidth={0.12} />
    <silkscreenline x1={-1.61} y1={-1.61} x2={-1.61} y2={-1.16} strokeWidth={0.12} />
    <courtyardrect pcbX={0} pcbY={0} width={4.2} height={4.2} />
  </footprint>
);

const ATTINY1616 = (props: { schX?: number; schY?: number; pcbX: number; pcbY: number; pcbRotation?: number }) => (
  <chip
    name="U2"
    footprint={<VQFN20_ATtiny1616 />}
    /* 20MHz, 16kB Flash, 2kB SRAM (no LCSC part # in the original BOM) */
    pinLabels={{
      pin1: "PA2", // BUFF_CV2 in
      pin2: "PA3", // unused
      pin3: "GND",
      pin4: "VCC",
      pin5: "PA4", // MODE button in
      pin6: "PA5", // LED out
      pin7: "PA6", // audio PWM out
      pin8: "PA7", // gate out
      pin9: "PB5", // unused
      pin10: "PB4", // unused
      pin11: "PB3", // MIDI RX
      pin12: "PB2", // MIDI TX
      pin13: "PB1", // unused
      pin14: "PB0", // unused
      pin15: "PC0", // unused
      pin16: "PC1", // unused
      pin17: "PC2", // unused
      pin18: "PC3", // unused
      pin19: "PA0", // ~{RESET}/UPDI via R1
      pin20: "PA1", // BUFF_CV1 in
      pin21: "EP", // exposed pad -> GND
    }}
    pinAttributes={{
      VCC: { requiresPower: true, providesPower: true },
      GND: { requiresGround: true, providesGround: true },
      PA3: { doNotConnect: true },
      PB5: { doNotConnect: true },
      PB4: { doNotConnect: true },
      PB1: { doNotConnect: true },
      PB0: { doNotConnect: true },
      PC0: { doNotConnect: true },
      PC1: { doNotConnect: true },
      PC2: { doNotConnect: true },
      PC3: { doNotConnect: true },
    }}
    schPinArrangement={{
      leftSide: { direction: "top-to-bottom", pins: ["VCC", "GND", "EP", "PA0", "PA4", "PA5"] },
      rightSide: {
        direction: "top-to-bottom",
        pins: ["PA2", "PA1", "PA6", "PA7", "PB3", "PB2", "PA3", "PB5", "PB4", "PB1", "PB0", "PC0", "PC1", "PC2", "PC3"],
      },
    }}
    schX={props.schX}
    schY={props.schY}
    pcbX={props.pcbX}
    pcbY={props.pcbY}
    pcbRotation={props.pcbRotation}
  />
);

/* ------------------------------------------------------------------ */
/* SW1 — K2-1808SN-A4SW-01 SMD tact switch (BreadModular_MISC          */
/* footprint: 2 + 2 pads, 1.05 x 0.65mm each)                          */
/* ------------------------------------------------------------------ */
const TactSwitchFootprint = () => (
  <footprint>
    {/* pin 1 (both pads internally joined) */}
    <smtpad shape="rect" portHints={["pin1"]} pcbX={-2.06} pcbY={1.1} width={1.05} height={0.65} />
    <smtpad shape="rect" portHints={["pin1"]} pcbX={2.14} pcbY={1.1} width={1.05} height={0.65} />
    {/* pin 2 (both pads internally joined) */}
    <smtpad shape="rect" portHints={["pin2"]} pcbX={-2.05} pcbY={-1.125} width={1.05} height={0.65} />
    <smtpad shape="rect" portHints={["pin2"]} pcbX={2.15} pcbY={-1.125} width={1.05} height={0.65} />
    {/* Body outline (KiCad F.SilkS 0.1mm) */}
    <silkscreenline x1={2.175} y1={0.725} x2={2.175} y2={-0.775} strokeWidth={0.1} />
    <silkscreenline x1={-1.49} y1={-1.025} x2={1.61} y2={-1.025} strokeWidth={0.1} />
    <silkscreenline x1={-1.5} y1={1.2} x2={1.6} y2={1.2} strokeWidth={0.1} />
    <silkscreenline x1={-2.05} y1={0.725} x2={-2.05} y2={-0.775} strokeWidth={0.1} />
  </footprint>
);

export default () => (
  <BreadModule name="8BIT" version="1.1.0" autorouterEffortLevel="100x">
    {/* ============ U2: ATtiny1616 MCU (VQFN-20, rotated 90° like KiCad) ============ */}
    <ATTINY1616 schX={0} schY={0.5} pcbX={-3.5} pcbY={-7.83} pcbRotation={90} />

    {/* ============ U1 / U3: MCP6002 dual op-amps ============ */}
    {/* U1 (right): A = audio out buffer, B = gate buffer */}
    <MCP6002 name="U1" schX={5.5} schY={2} pcbX={5.145} pcbY={17.145} />
    {/* U3 (left): A = CV1 buffer, B = CV2 buffer */}
    <MCP6002 name="U3" schX={-5.5} schY={2} pcbX={-4.11} pcbY={17.145} />

    {/* ============ Power: VMID divider (R4/R5) + decoupling ============ */}
    <resistor name="R4" resistance="1k" footprint="0402" schX={-3} schY={-6.5} pcbX={-5.709} pcbY={-17.526} />
    <resistor name="R5" resistance="1k" footprint="0402" schX={-1.5} schY={-6.5} pcbX={-3.3} pcbY={-17.526} />
    <trace name="R4-vsup" from=".R4 > .pin1" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="R4-vmid" from=".R4 > .pin2" to={NET_VMID} width="0.3mm" />
    <trace name="R5-vmid" from=".R5 > .pin1" to={NET_VMID} width="0.3mm" />
    <trace name="R5-gnd" from=".R5 > .pin2" to={NET_GND} width="0.3mm" />
    <netlabel net="VMID" schX={-2.25} schY={-5.5} anchorSide="left" />

    {/* C1 100uF bulk decoupling (1206) */}
    <capacitor name="C1" capacitance="100uF" footprint="1206" schX={-8.5} schY={-6.5} pcbX={-4.85} pcbY={-13.6} />
    <trace name="C1-vsup" from=".C1 > .pin2" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="C1-gnd" from=".C1 > .pin1" to={NET_GND} width="0.3mm" />
    {/* C3: U1 supply decoupling, C4: U3 supply decoupling */}
    <capacitor name="C3" capacitance="0.1uF" footprint="0402" schX={7} schY={0.5} pcbX={4.318} pcbY={13.462} />
    <trace name="C3-vsup" from=".C3 > .pin1" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="C3-gnd" from=".C3 > .pin2" to={NET_GND} width="0.3mm" />
    <capacitor name="C4" capacitance="0.1uF" footprint="0402" schX={-8} schY={0.5} pcbX={-1.35} pcbY={20.701} />
    <trace name="C4-vsup" from=".C4 > .pin1" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="C4-gnd" from=".C4 > .pin2" to={NET_GND} width="0.3mm" />

    {/* ============ Audio out: PA6 -> RV1 -> C2 -> U1A follower -> R2 ============ */}
    <RV09Pot name="RV1" resistance="50k" schX={3} schY={-4} pcbX={6.858} pcbY={-12.407} pinAttributes={{ pin2: { doNotConnect: true } }} />
    <trace name="U2-pa6-rv1" from=".U2 > .PA6" to=".RV1 > .pin1" />
    <trace name="RV1-wiper-u1a-in" from=".RV1 > .pin3" to="net.U1A_IN" />
    <capacitor name="C2" capacitance="100nF" footprint="0402" schX={4.5} schY={-5.5} pcbX={-0.9} pcbY={-15.748} />
    <trace name="C2-vmid" from=".C2 > .pin1" to={NET_VMID} width="0.3mm" />
    <trace name="C2-u1a-in" from=".C2 > .pin2" to="net.U1A_IN" />
    <trace name="U1-in1p" from=".U1 > .IN1P" to="net.U1A_IN" />
    {/* U1A unity buffer: OUT1 tied to IN1- */}
    <trace name="U1-out1" from=".U1 > .OUT1" to="net.U1A_BUF" />
    <trace name="U1-in1m" from=".U1 > .IN1M" to="net.U1A_BUF" />
    <resistor name="R2" resistance="1k" footprint="0402" schX={8} schY={4.5} pcbX={2.54} pcbY={20.828} />
    <trace name="R2-u1a-buf" from=".R2 > .pin1" to="net.U1A_BUF" />
    <trace name="R2-audio-out" from=".R2 > .pin2" to="net.AUDIO_OUT" />

    {/* ============ Gate out: PA7 -> U1B follower -> R3 ============ */}
    <trace name="U2-pa7-u1b-in" from=".U2 > .PA7" to="net.U1B_IN" />
    <trace name="U1-in2p" from=".U1 > .IN2P" to="net.U1B_IN" />
    <trace name="U1-out2" from=".U1 > .OUT2" to="net.U1B_BUF" />
    <trace name="U1-in2m" from=".U1 > .IN2M" to="net.U1B_BUF" />
    <resistor name="R3" resistance="1k" footprint="0402" schX={9.5} schY={0} pcbX={11.682} pcbY={14.478} />
    <trace name="R3-u1b-buf" from=".R3 > .pin1" to="net.U1B_BUF" />
    <trace name="R3-gate-out" from=".R3 > .pin2" to="net.GATE_OUT" />

    {/* ============ CV1 chain: INPUT1.2 -> U3A follower -> RV2 -> PA1 ============ */}
    <trace name="INPUT1-cv1" from=".INPUT1 > .pin2" to="net.CV1" />
    <trace name="U3-in1p" from=".U3 > .IN1P" to="net.CV1" />
    <resistor name="R7" resistance="100k" footprint="0402" schX={-8} schY={4.5} pcbX={-8.13} pcbY={13.335} />
    <trace name="R7-vsup" from=".R7 > .pin1" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="R7-cv1" from=".R7 > .pin2" to="net.CV1" />
    <trace name="U3-out1" from=".U3 > .OUT1" to="net.U3A_OUT" />
    <trace name="U3-in1m" from=".U3 > .IN1M" to="net.U3A_OUT" />
    <RV09Pot name="RV2" resistance="1M" schX={-6} schY={-4} pcbX={-6.985} pcbY={4.1} />
    <trace name="RV2-u3a-out" from=".RV2 > .pin2" to="net.U3A_OUT" />
    <trace name="RV2-wiper-buffcv1" from=".RV2 > .pin3" to="net.BUFF_CV1" />
    <trace name="U2-pa1-buffcv1" from=".U2 > .PA1" to="net.BUFF_CV1" />

    {/* ============ CV2 chain: INPUT1.3 -> U3B follower -> RV3 -> PA2 ============ */}
    <trace name="INPUT1-cv2" from=".INPUT1 > .pin3" to="net.CV2" />
    <trace name="U3-in2p" from=".U3 > .IN2P" to="net.CV2" />
    <resistor name="R8" resistance="100k" footprint="0402" schX={-6.5} schY={4.5} pcbX={-0.76} pcbY={13.335} />
    <trace name="R8-vsup" from=".R8 > .pin1" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="R8-cv2" from=".R8 > .pin2" to="net.CV2" />
    <trace name="U3-out2" from=".U3 > .OUT2" to="net.U3B_OUT" />
    <trace name="U3-in2m" from=".U3 > .IN2M" to="net.U3B_OUT" />
    <RV09Pot name="RV3" resistance="1M" schX={-1.5} schY={-4} pcbX={6.985} pcbY={4.1} />
    <trace name="RV3-u3b-out" from=".RV3 > .pin2" to="net.U3B_OUT" />
    <trace name="RV3-wiper-buffcv2" from=".RV3 > .pin3" to="net.BUFF_CV2" />
    <trace name="U2-pa2-buffcv2" from=".U2 > .PA2" to="net.BUFF_CV2" />

    {/* ============ MIDI in / THRU: bus pins 1, U2 PB3 (RX) / PB2 (TX) ============ */}
    <trace name="INPUT1-midi" from=".INPUT1 > .pin1" to="net.MIDI" />
    <trace name="OUTPUT1-midi" from=".OUTPUT1 > .pin1" to="net.MIDI" />
    <trace name="U2-pb3-midi" from=".U2 > .PB3" to="net.MIDI" />
    <trace name="INPUT1-tx" from=".INPUT1 > .pin4" to="net.TX" />
    <trace name="U2-pb2-tx" from=".U2 > .PB2" to="net.TX" />

    {/* ============ UPDI programming: INPUT1.5 -> R1 4.7k -> PA0 ============ */}
    <trace name="INPUT1-udpi" from=".INPUT1 > .pin5" to="net.UDPI" />
    <resistor name="R1" resistance="4.7k" footprint="0402" schX={-4.5} schY={5.5} pcbX={-12.2} pcbY={10.5} />
    <trace name="R1-udpi" from=".R1 > .pin2" to="net.UDPI" />
    <trace name="R1-pa0" from=".R1 > .pin1" to=".U2 > .PA0" />

    {/* ============ MODE button: SW1 pulls PA4 to GND ============ */}
    <chip name="SW1" footprint={<TactSwitchFootprint />} schX={-2.5} schY={6.5} pcbX={-9.525} pcbY={-10.795} />
    <trace name="SW1-gnd" from=".SW1 > .pin1" to={NET_GND} width="0.3mm" />
    <trace name="SW1-mode" from=".SW1 > .pin2" to="net.SW_MODE" />
    <trace name="U2-pa4-mode" from=".U2 > .PA4" to="net.SW_MODE" />

    {/* ============ LED: PA5 -> D1 -> R6 330 -> GND ============ */}
    <trace name="U2-pa5-led" from=".U2 > .PA5" to="net.LED_A" />
    <led name="D1" footprint="0603" schX={-1} schY={5.5} pcbX={-10.9475} pcbY={-5.08} />
    <trace name="D1-anode" from=".D1 > .anode" to="net.LED_A" />
    <trace name="D1-cathode" from=".D1 > .cathode" to=".R6 > .pin1" />
    <resistor name="R6" resistance="330" footprint="0402" schX={0.5} schY={5.5} pcbX={-8.13} pcbY={-5.08} />
    <trace name="R6-gnd" from=".R6 > .pin2" to={NET_GND} width="0.3mm" />

    {/* ============ Power to the op-amps + MCU ============ */}
    <trace name="U1-vdd" from=".U1 > .VDD" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="U1-vss" from=".U1 > .VSS" to={NET_GND} width="0.3mm" />
    <trace name="U3-vdd" from=".U3 > .VDD" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="U3-vss" from=".U3 > .VSS" to={NET_GND} width="0.3mm" />
    <trace name="U2-vcc" from=".U2 > .VCC" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="U2-gnd" from=".U2 > .GND" to={NET_GND} width="0.3mm" />

    {/* ============ Bus: audio out on pins 2-3, gate out on pins 4-5 ============ */}
    <trace name="OUTPUT1-audio-2" from=".OUTPUT1 > .pin2" to="net.AUDIO_OUT" />
    <trace name="OUTPUT1-audio-3" from=".OUTPUT1 > .pin3" to="net.AUDIO_OUT" />
    <trace name="OUTPUT1-gate-4" from=".OUTPUT1 > .pin4" to="net.GATE_OUT" />
    <trace name="OUTPUT1-gate-5" from=".OUTPUT1 > .pin5" to="net.GATE_OUT" />

    {/* ============ Bottom-side GND pour (like a KiCad B.Cu GND zone) ============ */}
    <copperpour name="GND-pour" connectsTo={NET_GND} layer="bottom" />


    {/* ========= Bus pin-function labels (same spots as the KiCad board) ========= */}
    {/* INPUT side: MIDI / CV1 / CV2 / TX / U (UPDI) — horizontal, 1mm font */}
    <silkscreentext text="MIDI" pcbX={-9.779} pcbY={28.575} fontSize={1} />
    <silkscreentext text="CV1" pcbX={-9.779} pcbY={26.035} fontSize={1} />
    <silkscreentext text="CV2" pcbX={-9.779} pcbY={23.368} fontSize={1} />
    <silkscreentext text="TX" pcbX={-9.779} pcbY={20.828} fontSize={1} />
    <silkscreentext text="U" pcbX={-9.779} pcbY={18.288} fontSize={1} />
    {/* OUTPUT side: MIDI horizontal; AUDIO / GATE vertical (rot 90 like KiCad) */}
    <silkscreentext text="MIDI" pcbX={9.779} pcbY={28.448} fontSize={1} />
    <silkscreentext text="AUDIO" pcbX={9.525} pcbY={25.4} pcbRotation={90} fontSize={1} />
    <silkscreentext text="GATE" pcbX={9.652} pcbY={20.193} pcbRotation={90} fontSize={1} />
    {/* Decorative dashes flanking the vertical labels (KiCad F.SilkS gr_lines) */}
    <silkscreenline x1={8.382} y1={27.94} x2={12.065} y2={27.94} strokeWidth={0.1} />
    <silkscreenline x1={8.382} y1={22.86} x2={12.065} y2={22.86} strokeWidth={0.1} />
    <silkscreenline x1={12.065} y1={22.86} x2={12.827} y2={22.86} strokeWidth={0.1} />
    {/* Knob + button labels (KiCad gr_text positions) */}
    <silkscreentext text="CV1" pcbX={-6.985} pcbY={-3.175} fontSize={1} />
    <silkscreentext text="CV2" pcbX={6.985} pcbY={-3.175} fontSize={1} />
    <silkscreentext text="LOWPASS" pcbX={6.985} pcbY={-19.685} fontSize={1} />
    <silkscreentext text="MODE" pcbX={-11.684} pcbY={-8.255} fontSize={1} />
  </BreadModule>
);
