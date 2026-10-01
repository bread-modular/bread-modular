"""Mutation tests for independent HRO/body-datum release acceptance, read-only."""
import unittest
from pathlib import Path
import pcbnew as p
from assembly_datum import expected_position

class AssemblyDatumTests(unittest.TestCase):
    def setUp(self):
        self.board=p.LoadBoard(str(Path(__file__).resolve().parents[1]/'base.kicad_pcb'))
        self.j5=next(f for f in self.board.GetFootprints() if f.GetReference()=='J5')
        self.origin=self.board.GetDesignSettings().GetAuxOrigin()

    def test_documented_body_not_raw_anchor(self):
        x,y=expected_position(self.j5,self.origin)
        self.assertAlmostEqual(x,4.035);self.assertAlmostEqual(y,130.810)
        self.assertNotAlmostEqual(x,p.ToMM(self.j5.GetPosition().x-self.origin.x))

    def test_zero_native_offset_cannot_be_used_as_circular_proof(self):
        self.j5.SetField('JLCPCB Position Offset X','0')
        with self.assertRaisesRegex(AssertionError,'disagrees with HRO'):
            expected_position(self.j5,self.origin)

    def test_nonfinite_native_offset_rejected(self):
        self.j5.SetField('JLCPCB Position Offset Y','nan')
        with self.assertRaisesRegex(AssertionError,'non-finite'):
            expected_position(self.j5,self.origin)

    def test_moved_anchor_rejected(self):
        self.j5.Move(p.VECTOR2I(p.FromMM(.1),0))
        with self.assertRaisesRegex(AssertionError,'anchor moved'):
            expected_position(self.j5,self.origin)

    def test_rotated_or_library_corrected_part_rejected(self):
        self.j5.SetOrientationDegrees(180)
        with self.assertRaisesRegex(AssertionError,'rotated/flipped'):
            expected_position(self.j5,self.origin)

    def test_body_art_change_rejected(self):
        q=next(q for q in self.j5.GraphicalItems() if q.GetClass()=='PCB_SHAPE' and q.GetLayer()==p.F_Fab)
        q.SetStart(q.GetStart()+p.VECTOR2I(p.FromMM(.01),0))
        with self.assertRaisesRegex(AssertionError,'F.Fab'):
            expected_position(self.j5,self.origin)

if __name__=='__main__':unittest.main()
