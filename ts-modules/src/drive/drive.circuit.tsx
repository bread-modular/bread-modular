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
    <trace from=".R1 > .pin1" to={NET_VSUPPLY} width="0.3mm" />
    <trace from=".R1 > .pin2" to={NET_VMID} width="0.3mm" />
    <trace from=".R2 > .pin1" to={NET_VMID} width="0.3mm" />
    <trace from=".R2 > .pin2" to={NET_GND} width="0.3mm" />
    <trace from=".C1 > .pin1" to={NET_VSUPPLY} width="0.3mm" />
    <trace from=".C1 > .pin2" to={NET_GND} width="0.3mm" />
    <netlabel net="VMID" schX={0} schY={1.5} anchorSide="left" />

    {/* ============ U1: MCP6002 dual op-amp ============ */}
    <MCP6002 schX={2} schY={1.5} pcbX={0} pcbY={17.15} />
    <trace from=".U1 > .VDD" to={NET_VSUPPLY} width="0.3mm" />
    <trace from=".U1 > .VSS" to={NET_GND} width="0.3mm" />
    <trace from=".U1 > .IN1P" to={NET_VMID} width="0.3mm" />
    <trace from=".U1 > .IN2P" to={NET_VMID} width="0.3mm" />

    {/* ============ Input: INPUT1.1 -> R8 -> U1A inverting input ============ */}
    <trace from=".INPUT1 > .pin1" to="net.AUDIO_IN" />
    <resistor name="R8" resistance="100k" footprint="0402" schX={-2.5} schY={4} pcbX={-5} pcbY={15.6} />
    <trace from=".R8 > .pin1" to="net.AUDIO_IN" />
    <trace from=".R8 > .pin2" to=".U1 > .IN1M" />
    {/* Unused INPUT socket pins tied together (as in the KiCad original) */}
    <trace from=".INPUT1 > .pin2" to=".INPUT1 > .pin3" />
    <trace from=".INPUT1 > .pin3" to=".INPUT1 > .pin4" />
    <trace from=".INPUT1 > .pin4" to=".INPUT1 > .pin5" />

    {/* ============ U1A feedback: OUT1 -> R7 -> IN1- ; OUT1 -> RV1 wiper ============ */}
    <resistor name="R7" resistance="100k" footprint="0402" schX={-2.5} schY={0.5} pcbX={-5} pcbY={18.5} />
    <trace from=".U1 > .OUT1" to=".R7 > .pin2" />
    <trace from=".R7 > .pin1" to=".U1 > .IN1M" />
    <trace from=".U1 > .OUT1" to=".RV1 > .pin2" />

    {/* ============ GAIN pot (RV1 50k): OUT1 -> RV1 -> R3 -> U1B- ============ */}
    <RV09Pot name="RV1" resistance="50k" label="GAIN" schX={-1} schY={6} pcbX={0} pcbY={-9.4} />
    <resistor name="R3" resistance="1k" footprint="0402" schX={2} schY={6} pcbX={5.8} pcbY={15.4} />
    <trace from=".RV1 > .pin3" to=".R3 > .pin1" />
    <trace from=".R3 > .pin2" to=".U1 > .IN2M" />

    {/* ============ U1B feedback: R4 51k between IN2- (CLIP) and OUT2 ============ */}
    <resistor name="R4" resistance="51k" footprint="0402" schX={6.5} schY={1.5} pcbX={5.3} pcbY={17.3} pcbRotation={90} />
    <trace from=".R4 > .pin1" to=".U1 > .IN2M" />
    <trace from=".R4 > .pin2" to=".U1 > .OUT2" />

    {/* ============ OD2 chain: OUT2 -> RV2 -> D2 -> D1 -> IN2- ============ */}
    <RV09Pot name="RV2" resistance="500k" label="OD1" schX={-4} schY={-3} pcbX={-6.58} pcbY={7.08} />
    <SMADiode name="D1" partNumber="C2480" schX={-1} schY={-3} pcbX={-11.2} pcbY={-7} />
    <SMADiode name="D2" partNumber="C2480" schX={-1} schY={-5} pcbX={-11.2} pcbY={-12.6} />
    <trace from=".U1 > .OUT2" to=".RV2 > .pin3" />
    <trace from=".RV2 > .pin2" to=".D2 > .anode" />
    <trace from=".D2 > .cathode" to=".D1 > .anode" />
    <trace from=".D1 > .cathode" to=".U1 > .IN2M" />

    {/* ============ OD1 chain: IN2- -> D3 -> D4 -> RV3 -> OUT2 ============ */}
    <RV09Pot name="RV3" resistance="500k" label="OD2" schX={8} schY={-3} pcbX={7.11} pcbY={7.08} />
    <SMADiode name="D3" partNumber="C2480" schX={5} schY={-3} pcbX={10.6} pcbY={-7} />
    <SMADiode name="D4" partNumber="C2480" schX={5} schY={-5} pcbX={10.5} pcbY={-12.6} />
    <trace from=".U1 > .IN2M" to=".D3 > .anode" />
    <trace from=".D3 > .cathode" to=".D4 > .anode" />
    <trace from=".D4 > .cathode" to=".RV3 > .pin2" />
    <trace from=".RV3 > .pin3" to=".U1 > .OUT2" />

    {/* ============ Outputs: R5 -> OUT_CLEAN ; D6||D7 -> R6 -> OUT_DIRTY ============ */}
    <resistor name="R5" resistance="1k" footprint="0402" schX={8} schY={4} pcbX={5.8} pcbY={19.2} />
    <trace from=".R5 > .pin1" to=".U1 > .OUT2" />
    <trace from=".R5 > .pin2" to="net.AUDIO_OUT_CLEAN" />

    <SMADiode name="D6" partNumber="C14996" schX={2} schY={-8} pcbX={-4.6} pcbY={-26.4} />
    <SMADiode name="D7" partNumber="C2480" schX={5.5} schY={-8} pcbX={4.8} pcbY={-26.5} />
    <resistor name="R6" resistance="1k" footprint="0402" schX={8} schY={-6.5} pcbX={7.6} pcbY={-23.6} />
    <trace from=".U1 > .OUT2" to=".D6 > .cathode" />
    <trace from=".D7 > .anode" to=".U1 > .OUT2" />
    <trace from=".D6 > .anode" to=".D7 > .cathode" />
    <trace from=".D6 > .anode" to=".R6 > .pin1" />
    <trace from=".R6 > .pin2" to="net.AUDIO_OUT_DIRTY" />

    {/* ========= Bus: OUTPUT1 pins 1-3 = DIRTY, pins 4-5 = CLEAN ========= */}
    <trace from=".OUTPUT1 > .pin1" to="net.AUDIO_OUT_DIRTY" />
    <trace from=".OUTPUT1 > .pin2" to="net.AUDIO_OUT_DIRTY" />
    <trace from=".OUTPUT1 > .pin3" to="net.AUDIO_OUT_DIRTY" />
    <trace from=".OUTPUT1 > .pin4" to="net.AUDIO_OUT_CLEAN" />
    <trace from=".OUTPUT1 > .pin5" to="net.AUDIO_OUT_CLEAN" />
  </BreadModule>
);
