# PyroSim MCP Server — Overview

## Goal
An MCP server so Cursor can generate and edit **Thunderhead PyroSim / NIST FDS** fire models as `.fds` text (not GUI automation).

Current capabilities:
- New/import/validate models; open PyroSim, FDS, Smokeview
- Fire presets (couch, cigarette, car, wastebasket) and specified-HRR / HRRPUA / burn-away fires
- Simple chemistry (`&REAC`), UMD FireBID materials, layered surfaces
- NFPA 13/13D/13R/15 sprinklers, heat detectors, smoke detectors, activation controls
- HVAC fans, flow vents, leakage zones, wind, velocity patches
- NFPA 502 critical velocity and D\*/10 mesh guidance
- Slices, isosurfaces, devices, smoke visualization
- PyroSim sample library under `PYROSIM_SAMPLES`

## Why text-based
PyroSim’s native format is a `.fds` file (Fortran namelists). Editing namelists is reliable and headless.

## Stack
- Python MCP SDK (`mcp` package; FastMCP / MCPServer)
- `pyrosim-mcp/server.py` plus `fds_writer.py`, `presets.py`, `materials.py`, `sprinklers.py`, `fire_calcs.py`, `catalog.py`

## File map (this folder)
| File | Purpose |
|---|---|
| `00-overview.md` | this file |
| `01-mcp-tools.md` | live tool catalog |
| `02-fire-presets.md` | fire / chemistry / NFPA data notes |
| `03-fds-syntax-reference.md` | namelist snippets |
| `04-cursor-build-instructions.md` | setup and MCP config |
| `05-example-prompts.md` | 100 sample prompts by difficulty |

Use `05-example-prompts.md` when exercising the connected `pyrosim` MCP server.
