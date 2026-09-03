/**
 * Bread Modular — "drive" module (tscircuit port of modules/drive v1.0.0)
 * ------------------------------------------------------------------------
 * An overdrive/distortion stage with a dual op-amp (MCP6002) core:
 *
 *   AUDIO_IN -> R8 (100k) -> [U1A inverting stage] -> RV1 GAIN -> R3
 *            -> [U1B inverting stage, R4 51k feedback]
 *            -> diode soft-clip feedback networks:
 *                 - RV2 OD1 + D1/D2 (SS14) : one polarity
 *                 - RV3 OD2 + D3/D4 (SS14) : other polarity
 *            -> OUT_CLEAN via R5 (1k)
 *            -> OUT_DIRTY via D6 (SS210) ∥ D7 (SS14) hard-clip + R6 (1k)
 *
 * R1/R2 (1k) generate VMID; C1 0.1uF decouples the supply.
 * Netlist is a faithful 1:1 port of modules/drive/production/netlist.ipc.
 *
 * Layout mirrors the KiCad original: U1 + gain path up top, OD1/OD2 pots in
 * the middle row, GAIN pot bottom-center, SMA diodes along the bottom.
 *
 * (The KiCad sheet's unconnected, simulation-only V1 3.3V source is not
 * carried over so the JLCPCB BOM/PnP stay clean.)
 */
import {
  BreadModule,
  MCP6002,
  NET_GND,
  NET_VMID,
  NET_VSUPPLY,
  RV09Pot,
  SMADiode,
} from "../../lib";

export default () => (
  <BreadModule name="DRIVE" version="1.0.0">
    {/* ============ Power: VMID divider + decoupling (R1, R2, C1) ============ */}
    <resistor name="R1" resistance="1k" footprint="0402" schX={0} schY={3} schRotation={-90} pcbX={-12.6} pcbY={15.5} />
    <resistor name="R2" resistance="1k" footprint="0402" schX={0} schY={-1} schRotation={-90} pcbX={-10.3} pcbY={15.5} />
    <capacitor name="C1" capacitance="0.1uF" footprint="0402" schX={4} schY={3} schRotation={-90} pcbX={3.5} pcbY={21.5} />
    <trace name="R1-vsup" from=".R1 > .pin1" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="R1-vmid" from=".R1 > .pin2" to={NET_VMID} width="0.3mm" />
    <trace name="R2-vmid" from=".R2 > .pin1" to={NET_VMID} width="0.3mm" />
    <trace name="R2-gnd" from=".R2 > .pin2" to={NET_GND} width="0.3mm" />
    <trace name="C1-vsup" from=".C1 > .pin1" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="C1-gnd" from=".C1 > .pin2" to={NET_GND} width="0.3mm" />
    <netlabel net="VMID" schX={0} schY={1.5} anchorSide="left" />

    {/* ============ U1: MCP6002 dual op-amp ============ */}
    <MCP6002 schX={2} schY={1.5} pcbX={0} pcbY={17.15} />
    <trace name="U1-vdd" from=".U1 > .VDD" to={NET_VSUPPLY} width="0.3mm" />
    <trace name="U1-vss" from=".U1 > .VSS" to={NET_GND} width="0.3mm" />
    <trace name="U1-in1p-vmid" from=".U1 > .IN1P" to={NET_VMID} width="0.3mm" />
    <trace name="U1-in2p-vmid" from=".U1 > .IN2P" to={NET_VMID} width="0.3mm" />

    {/* ============ Input: INPUT1.1 -> R8 -> U1A inverting input ============ */}
    <trace name="INPUT1-audio-in" from=".INPUT1 > .pin1" to="net.AUDIO_IN" />
    <resistor name="R8" resistance="100k" footprint="0402" schX={-2.5} schY={4} pcbX={-5} pcbY={15.6} />
    <trace name="R8-audio-in" from=".R8 > .pin1" to="net.AUDIO_IN" />
    <trace name="R8-in1m" from=".R8 > .pin2" to=".U1 > .IN1M" />
    {/* Unused INPUT socket pins tied together (as in the KiCad original) */}
    <trace name="INPUT1-p2-3" from=".INPUT1 > .pin2" to=".INPUT1 > .pin3" />
    <trace name="INPUT1-p3-4" from=".INPUT1 > .pin3" to=".INPUT1 > .pin4" />
    <trace name="INPUT1-p4-5" from=".INPUT1 > .pin4" to=".INPUT1 > .pin5" />

    {/* ============ U1A feedback: OUT1 -> R7 -> IN1- ; OUT1 -> RV1 wiper ============ */}
    <resistor name="R7" resistance="100k" footprint="0402" schX={-2.5} schY={0.5} pcbX={-5} pcbY={18.5} />
    <trace name="U1-out1-r7" from=".U1 > .OUT1" to=".R7 > .pin2" />
    <trace name="R7-in1m" from=".R7 > .pin1" to=".U1 > .IN1M" />
    <trace name="U1-out1-rv1" from=".U1 > .OUT1" to=".RV1 > .pin2" />

    {/* ============ GAIN pot (RV1 50k): OUT1 -> RV1 -> R3 -> U1B- ============ */}
    <RV09Pot name="RV1" resistance="50k" label="GAIN" schX={-1} schY={6} pcbX={0} pcbY={-9.4} pinAttributes={{ pin1: { doNotConnect: true } }} />
    <resistor name="R3" resistance="1k" footprint="0402" schX={2} schY={6} pcbX={5.8} pcbY={15.4} />
    <trace name="RV1-wiper-r3" from=".RV1 > .pin3" to=".R3 > .pin1" />
    <trace name="R3-in2m" from=".R3 > .pin2" to=".U1 > .IN2M" />

    {/* ============ U1B feedback: R4 51k between IN2- (CLIP) and OUT2 ============ */}
    <resistor name="R4" resistance="51k" footprint="0402" schX={6.5} schY={1.5} pcbX={5.3} pcbY={17.3} pcbRotation={90} />
    <trace name="R4-in2m" from=".R4 > .pin1" to=".U1 > .IN2M" />
    <trace name="R4-out2" from=".R4 > .pin2" to=".U1 > .OUT2" />

    {/* ============ OD2 chain: OUT2 -> RV2 -> D2 -> D1 -> IN2- ============ */}
    <RV09Pot name="RV2" resistance="500k" label="OD1" schX={-4} schY={-3} pcbX={-6.58} pcbY={7.08} pinAttributes={{ pin1: { doNotConnect: true } }} />
    <SMADiode name="D1" partNumber="C2480" schX={-1} schY={-3} pcbX={-11.2} pcbY={-7} />
    <SMADiode name="D2" partNumber="C2480" schX={-1} schY={-5} pcbX={-11.2} pcbY={-12.6} />
    <trace name="U1-out2-rv2" from=".U1 > .OUT2" to=".RV2 > .pin3" />
    <trace name="RV2-wiper-d2" from=".RV2 > .pin2" to=".D2 > .anode" />
    <trace name="D2-cath-d1" from=".D2 > .cathode" to=".D1 > .anode" />
    <trace name="D1-cath-in2m" from=".D1 > .cathode" to=".U1 > .IN2M" />

    {/* ============ OD1 chain: IN2- -> D3 -> D4 -> RV3 -> OUT2 ============ */}
    <RV09Pot name="RV3" resistance="500k" label="OD2" schX={8} schY={-3} pcbX={7.11} pcbY={7.08} pinAttributes={{ pin1: { doNotConnect: true } }} />
    <SMADiode name="D3" partNumber="C2480" schX={5} schY={-3} pcbX={10.6} pcbY={-7} />
    <SMADiode name="D4" partNumber="C2480" schX={5} schY={-5} pcbX={10.5} pcbY={-12.6} />
    <trace name="U1-in2m-d3" from=".U1 > .IN2M" to=".D3 > .anode" />
    <trace name="D3-cath-d4" from=".D3 > .cathode" to=".D4 > .anode" />
    <trace name="D4-cath-rv3" from=".D4 > .cathode" to=".RV3 > .pin2" />
    <trace name="RV3-r1-out2" from=".RV3 > .pin3" to=".U1 > .OUT2" />

    {/* ============ Outputs: R5 -> OUT_CLEAN ; D6||D7 -> R6 -> OUT_DIRTY ============ */}
    <resistor name="R5" resistance="1k" footprint="0402" schX={8} schY={4} pcbX={5.8} pcbY={19.2} />
    <trace name="U1-out2-r5" from=".R5 > .pin1" to=".U1 > .OUT2" />
    <trace name="R5-out-clean" from=".R5 > .pin2" to="net.AUDIO_OUT_CLEAN" />

    <SMADiode name="D6" partNumber="C14996" schX={2} schY={-8} pcbX={-4.6} pcbY={-26.4} />
    <SMADiode name="D7" partNumber="C2480" schX={5.5} schY={-8} pcbX={4.8} pcbY={-26.5} />
    <resistor name="R6" resistance="1k" footprint="0402" schX={8} schY={-6.5} pcbX={7.6} pcbY={-23.6} />
    <trace name="U1-out2-d6" from=".U1 > .OUT2" to=".D6 > .cathode" />
    <trace name="D7-anode-out2" from=".D7 > .anode" to=".U1 > .OUT2" />
    <trace name="D6-anode-d7" from=".D6 > .anode" to=".D7 > .cathode" />
    <trace name="D6-anode-r6" from=".D6 > .anode" to=".R6 > .pin1" />
    <trace name="R6-out-dirty" from=".R6 > .pin2" to="net.AUDIO_OUT_DIRTY" />

    {/* ========= Bus: OUTPUT1 pins 1-3 = DIRTY, pins 4-5 = CLEAN ========= */}
    <trace name="OUTPUT-pin1-dirty" from=".OUTPUT1 > .pin1" to="net.AUDIO_OUT_DIRTY" />
    <trace name="OUTPUT-pin2-dirty" from=".OUTPUT1 > .pin2" to="net.AUDIO_OUT_DIRTY" />
    <trace name="OUTPUT-pin3-dirty" from=".OUTPUT1 > .pin3" to="net.AUDIO_OUT_DIRTY" />
    <trace name="OUTPUT-pin4-clean" from=".OUTPUT1 > .pin4" to="net.AUDIO_OUT_CLEAN" />
    <trace name="OUTPUT-pin5-clean" from=".OUTPUT1 > .pin5" to="net.AUDIO_OUT_CLEAN" />

    {/* ========= Bus pin-function labels (same spots as the KiCad original) ========= */}
    {/* INPUT side: pins 1-2 AUDIO, pins 3-5 MULT — rotated 90° like the KiCad board */}
    <silkscreentext
      text="AUDIO"
      pcbX={-7.186}
      pcbY={29.177}
      fontSize={1}
    />
    <silkscreentext
      text="MULT"
      pcbX={-8.984}
      pcbY={22.86}
      pcbRotation={90}
      fontSize={1}
    />
    {/* OUTPUT side: pins 1-3 DIRTY, pins 4-5 CLEAN ("CLEN" in the KiCad original) */}
    <silkscreentext
      text="DIRTY"
      pcbX={8.415}
      pcbY={26.67}
      pcbRotation={90}
      fontSize={1}
    />
    <silkscreentext
      text="CLEN"
      pcbX={8.415}
      pcbY={20.193}
      pcbRotation={90}
      fontSize={1}
    />
    {/* Decorative dashes flanking the vertical labels (KiCad F.SilkS gr_lines,
        0.1mm wide — converted from the KiCad board coordinates) */}
    <silkscreenline x1={-9.017} y1={18.288} x2={-9.017} y2={20.828} strokeWidth={0.1} />
    <silkscreenline x1={-9.017} y1={24.765} x2={-9.017} y2={27.432} strokeWidth={0.1} />
    <silkscreenline x1={8.382} y1={23.368} x2={8.382} y2={24.638} strokeWidth={0.1} />
    <silkscreenline x1={8.382} y1={28.702} x2={8.382} y2={29.972} strokeWidth={0.1} />
  </BreadModule>
);
