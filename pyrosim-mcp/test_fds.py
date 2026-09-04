"""Unit tests for FDS writer, presets, and MCP tool functions."""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import fds_writer
import presets
import server


class RampTests(unittest.TestCase):
    def test_nfpa_time_to_1055kw(self):
        expected = {"slow": 600, "medium": 300, "fast": 150, "ultra-fast": 75}
        for growth, seconds in expected.items():
            points = presets.build_ramp(growth, 1055.0, hold_s=seconds)
            peak = next(t for t, f in points if f == 1.0)
            # NFPA table lists ~600/~300/~150/~75 s; α gives 603.2 s for slow.
            self.assertAlmostEqual(peak, seconds, delta=5.0)

    def test_ramp_starts_at_zero(self):
        points = presets.build_ramp("fast", 2500.0)
        self.assertEqual(points[0], (0.0, 0.0))
        self.assertEqual(points[-1][1], 1.0)

    def test_cigarette_flaming_transition(self):
        points = presets.build_cigarette_ramp(flaming_after=600.0)
        times = [t for t, _ in points]
        self.assertIn(600.0, times)
        self.assertEqual(points[-1][1], 1.0)


class FdsWriterTests(unittest.TestCase):
    def test_duplicate_id_raises(self):
        model = fds_writer.FdsModel("dup")
        model.add_mesh([0, 5, 0, 5, 0, 5], 0.2, mesh_id="MESH1")
        with self.assertRaises(ValueError):
            model.add_mesh([5, 10, 0, 5, 0, 5], 0.2, mesh_id="MESH1")

    def test_save_load_roundtrip(self):
        model = fds_writer.FdsModel("roundtrip", title="Couch fire test", t_end=600)
        model.add_mesh([0, 5, 0, 5, 0, 5], 0.1)
        model.add_reac(soot_yield=0.10)
        model.add_surf_with_ramp(
            "couch_fire",
            1800.0,
            "fire_ramp",
            [(0.0, 0.0), (75.0, 0.25), (150.0, 1.0), (600.0, 1.0)],
        )
        model.add_obst([1, 2.5, 1, 1.8, 0, 0.5], obst_id="couch_1", surf_ids=("couch_fire", "INERT", "INERT"))
        model.add_slcf("TEMPERATURE", axis="z", position=1.5)
        model.add_devc("THERMOCOUPLE", [2.5, 2.5, 2.0], "TC_1")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.fds"
            model.save(path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("&HEAD", text)
            self.assertIn("&TAIL", text)
            self.assertFalse(fds_writer.validate_fds_text(text))

            loaded = fds_writer.FdsModel.load(path)
            self.assertEqual(loaded.chid, "roundtrip")
            self.assertEqual(loaded.t_end, 600)
            self.assertIn("couch_fire", loaded.used_ids)
            self.assertIn("MESH1", loaded.used_ids)

    def test_ijk_from_bounds(self):
        ijk = fds_writer.ijk_from_bounds([0, 5, 0, 5, 0, 5], 0.1)
        self.assertEqual(ijk, (50, 50, 50))

    def test_slcf_requires_geometry(self):
        model = fds_writer.FdsModel("geom")
        model.add_mesh([0, 5, 0, 5, 0, 5], 0.2)
        with self.assertRaises(ValueError):
            model.add_slcf("TEMPERATURE")
        volume = model.add_slcf("TEMPERATURE", xb=model.domain_xb(), cell_centered=True)
        self.assertIn("XB=", volume)
        self.assertFalse(fds_writer.validate_fds_text(model.to_fds()))
        bad = (
            "&HEAD CHID='x', TITLE='x' /\n"
            "&TIME T_END=1 /\n"
            "&MESH IJK=1,1,1, XB=0,1,0,1,0,1, ID='MESH1' /\n"
            "&SLCF QUANTITY='TEMPERATURE', CELL_CENTERED=.TRUE. /\n"
            "&TAIL /\n"
        )
        errors = fds_writer.validate_fds_text(bad)
        self.assertTrue(any("SLCF must specify geometry" in item for item in errors))


class ToolWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        server.MODELS_DIR = Path(self.tmp.name)
        server.CURRENT_PATH = None

    def test_build_instruction_workflow(self):
        created = server.new_model("demo", [0, 5, 0, 5, 0, 5], resolution=0.2)
        self.assertIn("Created model", created)

        fire = server.add_fire_preset("couch", [1, 1, 0])
        self.assertIn("&SURF", fire)
        self.assertIn("&RAMP", fire)
        self.assertIn("&OBST", fire)

        slice_text = server.create_2d_slice("TEMPERATURE", "z", 1.5)
        self.assertIn("PBZ=1.5", slice_text)

        dest = str(Path(self.tmp.name) / "test.fds")
        exported = server.export_fds(dest)
        self.assertIn("Exported", exported)

        valid = server.validate_fds(dest)
        self.assertTrue(valid.startswith("VALID"), valid)

        text = Path(dest).read_text(encoding="utf-8")
        self.assertIn("QUANTITY='TEMPERATURE'", text)
        self.assertIn("SURF_IDS='couch_fire'", text)

    def test_list_presets_and_outputs(self):
        listing = server.list_fire_presets()
        for name in ("couch", "cigarette", "car", "wastebasket"):
            self.assertIn(name, listing)

        server.new_model("out", [0, 4, 0, 4, 0, 3], resolution=0.2)
        server.create_isosurface("TEMPERATURE", 60.0)
        server.add_device("THERMOCOUPLE", [2, 2, 2], "TC_1")
        summary = server.list_outputs()
        self.assertIn("&ISOF", summary)
        self.assertIn("TC_1", summary)

    def test_unknown_preset(self):
        server.new_model("x", [0, 2, 0, 2, 0, 2], 0.2)
        with self.assertRaises(ValueError):
            server.add_fire_preset("plasma_cannon", [0, 0, 0])

    def test_show_smoke_slcf_has_geometry(self):
        server.new_model("smoke", [0, 5, 0, 5, 0, 5], 0.2)
        text = server.show_smoke()
        self.assertIn("PBZ=", text)
        self.assertIn("XB=", text)
        self.assertIn("VISIBILITY", text)
        self.assertNotIn(
            "&SLCF QUANTITY='EXTINCTION COEFFICIENT', CELL_CENTERED=.TRUE. /",
            text,
        )
        valid = server.validate_fds()
        self.assertTrue(valid.startswith("VALID"), valid)

    def test_pyrosim_sample_patterns(self):
        server.new_model("room", [0, 10, 0, 8, 0, 3], 0.2)
        dump = server.set_output_controls(nframes=600, smoke3d=True, dt_restart=300)
        self.assertIn("RENDER_FILE=", dump)
        holes = server.add_hole([4, 6, 0, 0.2, 0, 2.1])
        self.assertIn("&HOLE", holes)
        opens = server.add_open_boundaries()
        self.assertIn("SURF_ID='OPEN'", opens)
        self.assertIn("open_xmin", opens)
        self.assertNotIn("open_zmin", opens)
        mats = server.add_material("CONCRETE")
        self.assertIn("&MATL ID='CONCRETE'", mats)
        flow = server.add_flow_vent([0, 0, 3, 4, 1, 2], -5.0)
        self.assertIn("VEL=-5", flow)
        hvac = server.add_hvac_fan(
            [1, 1.5, 1, 1.5, 2.5, 2.5],
            [8, 8.5, 1, 1.5, 2.5, 2.5],
            1.0,
        )
        self.assertIn("TYPE_ID='FAN'", hvac)
        det = server.add_smoke_detector([5, 4, 2.8])
        self.assertIn("&PROP", det)
        slc = server.create_2d_slice("VELOCITY", "x", 5.0)
        self.assertIn("VECTOR=.TRUE.", slc)
        iso = server.create_isosurface("VELOCITY", 1.0, extra_values=[2.0, 5.0])
        self.assertIn("VALUE=1,2,5", iso)
        valid = server.validate_fds()
        self.assertTrue(valid.startswith("VALID"), valid)

    def test_open_pyrosim_sample(self):
        sample = Path(r"D:\@LIB\PyroSim\Samples\leakage_input_files\door_crack.fds")
        if not sample.exists():
            self.skipTest("PyroSim Samples not installed")
        info = server.import_fds(str(sample), copy=True)
        self.assertIn("CHID='door_crack'", info)
        self.assertIn("HVAC=", info)
        census = server.inspect_model()
        self.assertIn("door_crack", census)

    def test_t_squared_peak_matches_alpha(self):
        alpha = presets.GROWTH_ALPHA["ultra-fast"]
        peak = 2500.0
        t_peak = math.sqrt(peak / alpha)
        points = presets.build_ramp("ultra-fast", peak, hold_s=t_peak)
        reached = next(t for t, f in points if f == 1.0)
        self.assertAlmostEqual(reached, t_peak, delta=0.2)


if __name__ == "__main__":
    unittest.main()
