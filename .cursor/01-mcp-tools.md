# MCP Tools to Implement

Each tool reads/writes a working `.fds` file (path tracked in server state or passed as arg).

## Project / file tools
- **new_model(name, mesh_bounds, resolution)** — create new `.fds` file with a `&MESH` block
- **export_fds(path)** — save current model to disk
- **validate_fds(path)** — basic syntax check (balanced `/`, required groups present)
- **open_in_pyrosim(path)** — launch PyroSim GUI with this file (optional, OS-dependent)

## Fire tools
- **list_fire_presets()** — return names/descriptions from `02-fire-presets.md` data
- **add_fire_preset(preset_name, position[x,y,z], surface_id?, scale?)**
  - inserts `&SURF` with HRRPUA + `&RAMP` (t-squared growth) + `&OBST`/`&VENT` at position
- **add_custom_fire(hrrpua, growth_rate, peak_hrr, fuel_area, position)** — manual fire, no preset

## Mesh / geometry tools
- **add_mesh(bounds, cell_size)**
- **add_obstruction(bounds, material, is_fuel=False)**
- **add_vent(bounds, surface_id)** (e.g. open boundary, supply/exhaust)

## Result / visualization tools
- **create_2d_slice(quantity, axis["x"|"y"|"z"], position, mesh_id?)**
  → writes `&SLCF PBX=`/`PBY=`/`PBZ=` for the given plane
- **create_volumetric_output(quantity, cell_centered=True)**
  → writes `&SLCF` with `CELL_CENTERED=.TRUE.` covering full mesh, or `&BNDF` for boundary data
- **create_isosurface(quantity, value)**
  → writes `&ISOF QUANTITY= VALUE=`
- **show_smoke(visibility_factor=3.0, soot_yield=0.1)**
  → sets `SOOT_YIELD` on `&REAC`, adds `&SLCF QUANTITY='extinction coefficient'` for smoke rendering
- **add_device(quantity, position, id)** — thermocouple/heat-flux/gas sensor `&DEVC`
- **list_outputs()** — summarize all output blocks currently in the model

## Simulation tools
- **run_simulation(fds_path, n_cores=1)** — shells out to `fds`
- **open_smokeview(fds_path)** — shells out to `smokeview`

## Notes for implementation
- Every tool should be idempotent-ish: append blocks, don't duplicate IDs.
- Keep a simple in-memory or file-based registry of used `ID=` strings to avoid collisions.
- Return the exact FDS text block written, so the AI/user can see what changed.
