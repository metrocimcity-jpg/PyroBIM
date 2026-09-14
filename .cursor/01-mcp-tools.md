# MCP Tools (current)

Each tool reads/writes a working `.fds` file (active path, or `fds_path`).

## Project / files
- `new_model(name, mesh_bounds, resolution, t_end, title)`
- `export_fds(path)`
- `validate_fds(path?)`
- `import_fds(path, copy=True)`
- `inspect_model()`
- `list_sample_library(query?, include_validation?)` / `open_sample(relative_path)`
- `list_fds_validation(query?, category?)` / `open_fds_validation(series, case?)` / `fds_validation_guidance(topic?)`
- `open_in_pyrosim(path?)` / `run_simulation(n_cores)` / `open_smokeview()`

## Fire (presets and specified HRR)
- `list_fire_presets()` / `add_fire_preset(preset_name, position, placement=obst|vent, scale, flaming_after?)`
- `add_custom_fire(hrrpua, growth_rate, peak_hrr, fuel_area, position)`
- `list_fuels()` / `add_reaction(fuel, soot_yield?, co_yield?, hcn_yield?, hcl_yield?)`
- `fire_stoichiometry(hrr_kw, area_m2, fuel)`
- `add_hrr_fire(peak_hrr, area, position, fuel, growth_rate?, hrr_curve?, placement, radius?, tau_q?)`
- `add_hrrpua_fire(hrrpua, bounds, fuel, tmp_ign, burn_away, material)`
- `fire_modeling_guidance()` / `pyrosim_examples_index()` / `fds_validation_guidance()`

Presets: `couch`, `cigarette`, `car`, `wastebasket`. Fuels: `PROPANE`, `N-HEPTANE`, `METHANE`, `POLYURETHANE`, `POLYURETHANE_GM27`, `WOOD`, `CELLULOSE`, `NATURAL_GAS`, `METHANOL`.

## Materials / surfaces
- `list_catalog()` / `list_materials(category)` — engineering + UMD FireBID (plastics, metals, hardwood, softwood, misc_wood, misc)
- `add_material(name, surf_id?, thickness?)`
- `add_layered_surface(surf_id, materials[], thicknesses[])`
- `add_surface(...)` — VEL, VOLUME_FLOW, HRRPUA, TAU_Q, MLRPUA, MASS_FLUX, ADIABATIC, leak_path
- `add_obstruction` / `add_vent` / `add_hole` / `add_open_boundaries` / `add_mesh`

## Fire protection (NFPA 13 / 72 / 720)
- `list_sprinklers()` / `add_sprinkler(...)` — pendent, upright, sidewall, QR, residential, ESFR, CMSA, dry, concealed, flush, recessed, deluge, nozzle, …
- `list_detectors()` — smoke, heat, gas, beam, aspiration, flame, tenability
- `add_smoke_detector(position, detector_type)` — ionization, photoelectric, heskestad, Cleary I1/I2/P1/P2, NIST Dunes 2000
- `add_heat_detector(position, detector_type)` — NFPA 72 ordinary 57 °C, intermediate, high, extra_high, rate-compensation
- `add_gas_detector(position, gas)` — CO (70 ppm), CO₂, O₂, fuel LEL, methane, propane, HCN, HCl
- `add_beam_detector(start, end)` — PATH OBSCURATION
- `add_aspiration_detector(chamber, samples)` — VESDA-style ASPIRATION
- `add_flame_detector(position)` — RADIATIVE HEAT FLUX GAS
- `add_tenability_device(type, position, xb?)` — visibility, optical_density, thermocouple, layer_height
- `add_control(ctrl_id, detector_id, delay)`

## Flow / HVAC / tunnels
- `add_flow_vent(bounds, velocity)` — FDS VEL sign: negative = supply into domain
- `add_hvac_fan(inlet, outlet, volume_flow)`
- `add_velocity_patch(bounds, velocity, component)`
- `add_pressure_zone` / `set_wind(speed, direction, z_0, z_ref, monin_obukhov_length)` / `set_pressure_solver`
- `nfpa_502_critical_velocity(hrr_kw, height_m, area_m2, grade_percent?)`
- `add_vegetation_bed(bounds, packing_ratio, moisture_fraction)` — CSIRO grassland PART+INIT packing

## Output
- `create_2d_slice` / `create_volumetric_output` / `create_isosurface` / `show_smoke`
- `add_device` / `add_line_device` (McCaffrey XB+POINTS) / `list_outputs` / `set_output_controls` / `set_ambient`

## NIST FDS Validation
135 series from [firemodels/fds Validation](https://github.com/firemodels/fds/tree/master/Validation). Local copies: `PYROSIM_SAMPLES/fds-master/Validation` or `FDS_VALIDATION`.
- Plume: McCaffrey, Heskestad, Hamins, Sandia_Plumes
- Compartment / HGL: Steckler, NIST_NRC, PRISME, VTT, NBS_Multi-Room
- Tunnels: Memorial, Arup, Wu_Bakar, CSTB, SWJTU, FHWA
- Vegetation: CSIRO_Grassland_Fires, Crown_Fires, USFS_*
- Suppression: Vettori_*, Bittern, UL_NFPRF, USCG_HAI

## Notes
- Do not invent namelists the tools already cover; call the tools.
- Every `&SLCF` needs `PBX`/`PBY`/`PBZ` or `XB` (PyroSim requires geometry).
- Sprinkler `FLOW_RATE` is L/min from NFPA 13 \(Q = K\sqrt{P}\).
- Material FYI strings must not contain `/` (FDS namelist terminator).
