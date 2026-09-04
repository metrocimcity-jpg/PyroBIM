# Build Instructions (for Cursor AI)

Follow in order. Keep each tool small and testable.

## 1. Scaffold project
```
mkdir pyrosim-mcp && cd pyrosim-mcp
python -m venv .venv && source .venv/bin/activate
pip install mcp
```
Create structure:
```
pyrosim-mcp/
  server.py
  fds_writer.py
  presets.py
  requirements.txt
```

## 2. `fds_writer.py`
- Class `FdsModel` holding a list of text blocks + a `used_ids` set
- Methods: `add_mesh`, `add_reac`, `add_surf_with_ramp`, `add_obst`, `add_vent`,
  `add_slcf`, `add_isof`, `add_devc`, `save(path)`
- Each method appends a formatted namelist string (see `03-fds-syntax-reference.md`)
- Raise an error if an `ID=` is reused

## 3. `presets.py`
- Dict of presets from `02-fire-presets.md` (name → growth class, peak_hrr, area, hrrpua, soot_yield)
- Function `build_ramp(growth_class, peak_hrr)` → returns list of (t, f) pairs

## 4. `server.py`
- Use `mcp.server.fastmcp.FastMCP`
- Register each tool from `01-mcp-tools.md` as a `@mcp.tool()` function
- Tools call into `FdsModel` / `presets.py`
- Keep one active `FdsModel` in server state (or accept `path` per call and load/save each time — simpler, prefer this for statelessness)
- `run_simulation` / `open_smokeview`: use `subprocess.run([...])`, let user configure exe paths via env vars `FDS_EXE`, `SMOKEVIEW_EXE`, `PYROSIM_EXE`

## 5. Test locally
```
mcp dev server.py
```
Try: `new_model`, `add_fire_preset("couch", [1,1,0])`, `create_2d_slice("TEMPERATURE","z",1.5)`, `export_fds("test.fds")`

## 6. Connect to Cursor
Add to Cursor's MCP config (`~/.cursor/mcp.json` or project `.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "pyrosim": {
      "command": "python",
      "args": ["/absolute/path/to/pyrosim-mcp/server.py"]
    }
  }
}
```
Restart Cursor, confirm the server shows connected, then test with a prompt from `05-example-prompts.md`.

## 7. Nice-to-haves (later)
- `list_outputs()` to summarize current model
- Auto-open Smokeview after `run_simulation` completes
- Preset variants (e.g. "couch_fire_smoldering_start")
- Unit tests on `fds_writer.py` output syntax
