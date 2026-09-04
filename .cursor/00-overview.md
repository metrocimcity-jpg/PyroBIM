# PyroSim MCP Server — Overview

## Goal
Build an MCP server that lets an AI assistant control **Thunderhead PyroSim/FDS** fire modeling workflows:
- Insert fire presets (couch, cigarette, car, etc.) into a model
- Add result outputs: 2D slices, volumetric data, smoke visualization
- Run simulations and open Smokeview

## Why text-based, not GUI automation
PyroSim's native format is a `.fds` file — plain text, namelist-style (Fortran group syntax like `&SURF ... /`).
The most reliable integration is **generating/editing `.fds` files directly**, then optionally shelling out to:
- `fds.exe` (or `fds` on Linux) — runs the simulation
- `smokeview.exe` — opens 3D visualization of results

This avoids fragile UI scripting and works headless (good for MCP/CLI use).

## Stack
- Language: Python (MCP official SDK: `mcp` package)
- Core lib: a small `fds_writer.py` module that appends/edits namelist blocks
- Transport: stdio (for Cursor)

## File map (this folder)
| File | Purpose |
|---|---|
| `00-overview.md` | this file |
| `01-mcp-tools.md` | tool definitions/schemas to implement |
| `02-fire-presets.md` | preset fire data (HRR curves, growth rates) |
| `03-fds-syntax-reference.md` | FDS namelist snippets used by the tools |
| `04-cursor-build-instructions.md` | step-by-step build/setup guide |
| `05-example-prompts.md` | sample prompts to test once built |

Give Cursor all 6 files as project context, then start with `04-cursor-build-instructions.md`.
