# MCP Tools (current)

Each tool reads/writes a working `.fds` file (active path, or `fds_path`).

## Project / files
- `new_model(name, mesh_bounds, resolution, t_end, title)`
- `export_fds(path)`
- `validate_fds(path?)`
- `import_fds(path, copy=True)`
- `inspect_model()`
- `list_sample_library(query?)` / `open_sample(relative_path)`
- `open_in_pyrosim(path?)` / `run_simulation(n_cores)` / `open_smokeview()`

## Fire (presets and specified HRR)
- `list_fire_presets()` / `add_fire_preset(preset_name, position, placement=obst|vent, scale, flaming_after?)`
- `add_custom_fire(hrrpua, growth_rate, peak_hrr, fuel_area, position)`
- `list_fuels()` / `add_reaction(fuel, soot_yield?, co_yield?, hcn_yield?, hcl_yield?)`
- `fire_stoichiometry(hrr_kw, area_m2, fuel)`
- `add_hrr_fire(peak_hrr, area, position, fuel, growth_rate?, hrr_curve?, placement, radius?)`
- `add_hrrpua_fire(hrrpua, bounds, fuel, tmp_ign, burn_away, material)`
- `fire_modeling_guidance()` / `pyrosim_examples_index()`

Presets: `couch`, `cigarette`, `car`, `wastebasket`. Fuels: `PROPANE`, `N-HEPTANE`, `METHANE`, `POLYURETHANE`, `POLYURETHANE_GM27`, `WOOD`.

## Materials / surfaces
- `list_catalog()` / `list_materials(category)` — engineering + UMD FireBID (plastics, metals, hardwood, softwood, misc_wood, misc)
- `add_material(name, surf_id?, thickness?)`
- `add_layered_surface(surf_id, materials[], thicknesses[])`
- `add_surface(...)` — VEL, VOLUME_FLOW, HRRPUA, ADIABATIC, leak_path
- `add_obstruction` / `add_vent` / `add_hole` / `add_open_boundaries` / `add_mesh`

## Fire protection (NFPA 13 / 72)
- `list_sprinklers()` / `add_sprinkler(position, sprinkler_type, k_factor?, pressure_psi?, temperature_rating, orientation?)`
  Types: pendent, upright, sidewall, QR, residential, ESFR, CMSA, dry, concealed, flush, recessed, deluge, nozzle, in-rack, window, attic, …
- `add_smoke_detector` / `add_heat_detector` / `add_control(ctrl_id, detector_id, delay)`

## Flow / HVAC / tunnels
- `add_flow_vent(bounds, velocity)` — FDS VEL sign: negative = supply into domain
- `add_hvac_fan(inlet, outlet, volume_flow)`
- `add_velocity_patch(bounds, velocity, component)`
- `add_pressure_zone` / `set_wind` / `set_pressure_solver`
- `nfpa_502_critical_velocity(hrr_kw, height_m, area_m2, grade_percent?)`

## Output
- `create_2d_slice` / `create_volumetric_output` / `create_isosurface` / `show_smoke`
- `add_device` / `list_outputs` / `set_output_controls` / `set_ambient`

## Notes
- Do not invent namelists the tools already cover; call the tools.
- Every `&SLCF` needs `PBX`/`PBY`/`PBZ` or `XB` (PyroSim requires geometry).
- Sprinkler `FLOW_RATE` is L/min from NFPA 13 \(Q = K\sqrt{P}\).
- Material FYI strings must not contain `/` (FDS namelist terminator).
