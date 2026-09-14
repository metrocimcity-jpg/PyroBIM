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

    def test_firebid_oak_and_layered_wall(self):
        listing = server.list_materials("hardwood")
        self.assertIn("Oak", listing)
        server.new_model("mats", [0, 4, 0, 4, 0, 3], 0.2)
        oak = server.add_material("Oak")
        self.assertIn("&MATL ID='OAK'", oak)
        self.assertIn("CONDUCTIVITY=0.17", oak)
        wall = server.add_layered_surface(
            "Default_Wall",
            ["GYPSUM", "INSULATION", "GYPSUM"],
            [0.01, 0.09, 0.01],
        )
        self.assertIn("MATL_ID='GYPSUM','INSULATION','GYPSUM'", wall)
        self.assertIn("THICKNESS=0.01,0.09,0.01", wall)
        valid = server.validate_fds()
        self.assertTrue(valid.startswith("VALID"), valid)

    def test_simple_chemistry_and_hrr_fire(self):
        fuels = server.list_fuels()
        self.assertIn("PROPANE", fuels)
        stoich = server.fire_stoichiometry(1858.0, 1.44, "N-HEPTANE")
        self.assertIn("HRRPUA=1290", stoich)
        server.new_model("vtt", [0, 10, 0, 10, 0, 5], 0.2)
        reac = server.add_reaction("PROPANE")
        self.assertIn("FUEL='PROPANE'", reac)
        self.assertIn("RADIATIVE_FRACTION=0.3", reac)
        fire = server.add_hrr_fire(
            1858.0,
            1.44,
            [1, 1, 0],
            fuel="N-HEPTANE",
            hrr_curve=[[0, 0], [13, 1245], [288, 1858], [438, 0]],
        )
        self.assertIn("HRRPUA=1290", fire)
        self.assertIn("&RAMP", fire)
        burn = server.add_hrrpua_fire(
            500.0,
            [3, 4, 3, 4, 0, 0.1],
            fuel="WOOD",
            tmp_ign=300.0,
            burn_away=True,
        )
        self.assertIn("TMP_IGN=300", burn)
        self.assertIn("BURN_AWAY=.TRUE.", burn)
        valid = server.validate_fds()
        self.assertTrue(valid.startswith("VALID"), valid)

    def test_nfpa13_sprinkler_types(self):
        listing = server.list_sprinklers()
        for name in (
            "pendent",
            "upright",
            "sidewall",
            "esfr_pendent",
            "deluge",
            "residential_sidewall",
        ):
            self.assertIn(name, listing)
        server.new_model("spr", [0, 10, 0, 10, 0, 3], 0.2)
        pendent = server.add_sprinkler([5, 5, 2.9], "pendent")
        self.assertIn("SMOKEVIEW_ID='sprinkler_pendent'", pendent)
        self.assertIn("ORIENTATION=0,0,-1", pendent)
        sidewall = server.add_sprinkler([1, 5, 2.4], "sidewall")
        self.assertIn("ORIENTATION=1,0,0", sidewall)
        open_head = server.add_sprinkler([8, 5, 2.9], "deluge")
        self.assertIn("SMOKEVIEW_ID='nozzle'", open_head)
        self.assertIn("QUANTITY='TIME'", open_head)
        self.assertIn("SETPOINT=0", open_head)
        vc = server.nfpa_502_critical_velocity(20000.0, 5.0, 60.0)
        self.assertIn("V_c=", vc)
        patch = server.add_velocity_patch([1, 2, 1, 1.25, 1, 1.25], -18.0, "x")
        self.assertIn("VELOCITY PATCH", patch)
        self.assertIn("VELOCITY_COMPONENT=1", patch)
        valid = server.validate_fds()
        self.assertTrue(valid.startswith("VALID"), valid)

    def test_detector_catalog(self):
        listing = server.list_detectors()
        for name in (
            "ionization",
            "photoelectric",
            "heskestad",
            "ordinary",
            "co",
            "beam",
            "aspiration",
            "flame",
        ):
            self.assertIn(name, listing)
        server.new_model("det", [0, 8, 0, 8, 0, 3], 0.2)
        ion = server.add_smoke_detector([4, 4, 2.9], "ionization")
        self.assertIn("CHAMBER OBSCURATION", ion)
        self.assertIn("SMOKEVIEW_ID='smoke_detector'", ion)
        self.assertIn("ALPHA_E=2.5", ion)
        photo = server.add_smoke_detector([4, 5, 2.9], "photoelectric")
        self.assertIn("ALPHA_E=1.8", photo)
        hes = server.add_smoke_detector([5, 4, 2.9], "heskestad")
        self.assertIn("LENGTH=1.8", hes)
        self.assertIn("ACTIVATION_OBSCURATION=3.24", hes)
        heat = server.add_heat_detector([4, 4, 2.9], "ordinary")
        self.assertIn("LINK TEMPERATURE", heat)
        self.assertIn("ACTIVATION_TEMPERATURE=57.2", heat)
        self.assertIn("SMOKEVIEW_ID='heat_detector'", heat)
        co = server.add_gas_detector([4, 4, 1.5], "co")
        self.assertIn("SPEC_ID='CARBON MONOXIDE'", co)
        self.assertIn("SETPOINT=7e-05", co)  # may format as 0.00007
        beam = server.add_beam_detector([1, 1, 2.5], [7, 1, 2.5], setpoint=15.0)
        self.assertIn("PATH OBSCURATION", beam)
        asp = server.add_aspiration_detector(
            [0.5, 0.5, 0.5],
            [[2, 2, 2.8], [6, 2, 2.8]],
            flowrate=0.3,
        )
        self.assertIn("QUANTITY='ASPIRATION'", asp)
        self.assertIn("FLOWRATE=0.3", asp)
        flame = server.add_flame_detector([1, 4, 2.5], setpoint=5.0)
        self.assertIn("RADIATIVE HEAT FLUX GAS", flame)
        vis = server.add_tenability_device("visibility", position=[4, 4, 1.8], setpoint=10.0)
        self.assertIn("VISIBILITY", vis)
        valid = server.validate_fds()
        self.assertTrue(valid.startswith("VALID"), valid)

    def test_fds_validation_catalog_covers_github(self):
        import validation

        self.assertEqual(len(validation.SERIES), 135)
        listing = server.list_fds_validation("McCaffrey")
        self.assertIn("McCaffrey_Plume", listing)
        self.assertIn("add_line_device", listing)
        tunnels = server.list_fds_validation(category="tunnel")
        self.assertIn("Memorial_Tunnel", tunnels)
        self.assertIn("Wu_Bakar_Tunnels", tunnels)
        guide = server.fds_validation_guidance("sprinkler")
        self.assertIn("Vettori_Flat_Ceiling", guide)

    def test_validation_patterns(self):
        server.new_model("val", [0, 10, 0, 10, 0, 3], 0.2)
        line = server.add_line_device("THERMOCOUPLE", [5, 5, 5, 5, 0, 3], points=30)
        self.assertIn("POINTS=30", line)
        self.assertIn("Z_ID='Height'", line)
        tau = server.add_hrr_fire(45.0, 0.09, [4.85, 4.85, 0], fuel="NATURAL_GAS", tau_q=-1.0)
        self.assertIn("TAU_Q=-1", tau)
        self.assertIn("HRRPUA=", tau)
        wind = server.set_wind(4.6, direction=270.0, z_0=0.03, monin_obukhov_length=-500.0)
        self.assertIn("Z_0=0.03", wind)
        self.assertIn("L=-500", wind)
        veg = server.add_vegetation_bed([0, 10, 0, 10, 0, 0.21], packing_ratio=0.0026)
        self.assertIn("PACKING_RATIO=0.0026", veg)
        self.assertIn("N_PARTICLES_PER_CELL=1", veg)
        self.assertIn("STATIC=.TRUE.", veg)
        valid = server.validate_fds()
        self.assertTrue(valid.startswith("VALID"), valid)

    def test_t_squared_peak_matches_alpha(self):
        alpha = presets.GROWTH_ALPHA["ultra-fast"]
        peak = 2500.0
        t_peak = math.sqrt(peak / alpha)
        points = presets.build_ramp("ultra-fast", peak, hold_s=t_peak)
        reached = next(t for t, f in points if f == 1.0)
        self.assertAlmostEqual(reached, t_peak, delta=0.2)


if __name__ == "__main__":
    unittest.main()
