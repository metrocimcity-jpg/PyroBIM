# Build / reconnect (PyroSim MCP)

The server already lives in `pyrosim-mcp/`. Use this when setting up a machine or after pulling changes.

## Layout
```
pyrosim-mcp/
  server.py          # FastMCP tools
  fds_writer.py
  presets.py
  materials.py       # FireBID + engineering MATL
  sprinklers.py      # NFPA 13 types
  fire_calcs.py      # HRR stoichiometry, NFPA 502, D*
  catalog.py
  test_fds.py
  requirements.txt
```

## Setup
```
cd pyrosim-mcp
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python -m unittest test_fds.py
```

Env vars (optional): `FDS_EXE`, `SMOKEVIEW_EXE`, `PYROSIM_EXE`, `PYROSIM_SAMPLES` (default `D:\@LIB\PyroSim\Samples`).

## Cursor MCP
Project `.cursor/mcp.json` should point at this venv’s Python and `server.py`. Restart Cursor MCP after tool changes.

## After reconnect
Sanity-check with prompts in `05-example-prompts.md` (beginner set first): list presets, new room, couch fire, temperature slice, validate.
