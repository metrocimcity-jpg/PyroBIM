"""PyroSim / FDS MCP server — generate and edit .fds fire models."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # mcp 2.x renamed FastMCP → MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP

from fds_writer import FdsModel, validate_fds_text
from catalog import (
    DEVICE_QUANTITIES,
    FLOW_NOTE,
    MATERIALS,
    SLICE_QUANTITIES,
)
from presets import (
    build_cigarette_ramp,
    build_ramp,
    preset_summaries,
    resolve_preset,
)

mcp = FastMCP("pyrosim")

MODELS_DIR = ROOT / "models"

CURRENT_PATH: str | None = None
SAMPLES_ROOT = Path(os.environ.get("PYROSIM_SAMPLES", r"D:\@LIB\PyroSim\Samples"))


def _active_path(fds_path: str | None) -> str:
    path = fds_path or CURRENT_PATH
    if not path:
        raise ValueError("No active model. Call new_model first, or pass fds_path.")
    return path


def _load(fds_path: str | None) -> tuple[FdsModel, str]:
    path = _active_path(fds_path)
    if not Path(path).exists():
        raise FileNotFoundError(f"FDS file not found: {path}")
    return FdsModel.load(path), path


def _save(model: FdsModel, path: str) -> str:
    global CURRENT_PATH
    model.save(path)
    CURRENT_PATH = path
    return path


def _fire_footprint(preset: dict, position: list[float], scale: float) -> list[float]:
    if len(position) != 3:
        raise ValueError("position must be [x, y, z]")
    lx = float(preset.get("lx") or preset["area"] ** 0.5) * (scale ** 0.5)
    ly = float(preset.get("ly") or preset["area"] ** 0.5) * (scale ** 0.5)
    height = float(preset.get("height", 0.2))
    x, y, z = position
    return [x, x + lx, y, y + ly, z, z + height]


def _ensure_reac(model: FdsModel, preset: dict) -> str | None:
    if any(b.strip().upper().startswith("&REAC") for b in model.blocks):
        return None
    return model.add_reac(
        fuel=preset.get("fuel", "POLYURETHANE"),
        soot_yield=float(preset.get("soot_yield", 0.10)),
        co_yield=float(preset.get("co_yield", 0.05)),
    )


@mcp.tool()
def new_model(
    name: str,
    mesh_bounds: list[float],
    resolution: float = 0.2,
    t_end: float = 600.0,
    title: str = "",
) -> str:
    """Create a new FDS model with a mesh and save it.

    Args:
        name: Model name used as CHID and default filename stem.
        mesh_bounds: Domain [x0, x1, y0, y1, z0, z1] in meters.
        resolution: Cell size in meters.
        t_end: Simulation end time in seconds.
        title: Optional TITLE in &HEAD.
    """
    global CURRENT_PATH
    stem = name[:-4] if name.lower().endswith(".fds") else name
    model = FdsModel(chid=stem, title=title or stem, t_end=t_end)
    dump_block = model.set_dump(
        render_file=f"{stem}.ge1",
        nframes=max(1, int(t_end)),
        dt_restart=min(300.0, float(t_end)),
        column_dump_limit=True,
    )
    mesh_block = model.add_mesh(mesh_bounds, resolution)
    path = str(MODELS_DIR / f"{stem}.fds")
    _save(model, path)
    return (
        f"Created model '{stem}' at {path}\n"
        f"Cell size {resolution} m.\n{dump_block}\n{mesh_block}"
    )


@mcp.tool()
def export_fds(path: str, fds_path: str | None = None) -> str:
    """Save the current model to a new path.

    Args:
        path: Destination .fds file path.
        fds_path: Source model path. Defaults to the active model.
    """
    model, source = _load(fds_path)
    dest = str(Path(path))
    _save(model, dest)
    return f"Exported {source} -> {dest}"


@mcp.tool()
def validate_fds(path: str | None = None) -> str:
    """Basic syntax check: balanced namelists, required groups, unique IDs.

    Args:
        path: .fds file to check. Defaults to the active model.
    """
    target = _active_path(path)
    text = Path(target).read_text(encoding="utf-8")
    errors = validate_fds_text(text)
    if errors:
        return "INVALID\n" + "\n".join(f"- {item}" for item in errors)
    namelist_count = text.count("&")
    return f"VALID {target}\n{namelist_count} namelist groups, no issues found."


@mcp.tool()
def open_in_pyrosim(path: str | None = None) -> str:
    """Launch the PyroSim GUI with this FDS file.

    Args:
        path: .fds file to open. Defaults to the active model.
    """
    target = _active_path(path)
    exe = os.environ.get("PYROSIM_EXE", "pyrosim")
    try:
        subprocess.Popen([exe, target])
    except FileNotFoundError:
        return (
            f"PyroSim executable not found ({exe}). "
            "Set PYROSIM_EXE to the full path of pyrosim.exe."
        )
    return f"Launched PyroSim: {exe} {target}"


@mcp.tool()
def list_fire_presets() -> str:
    """Return available fire presets with growth class, peak HRR, area, and soot yield."""
    lines = ["Fire presets (engineering approximations, not certified test data):"]
    for row in preset_summaries():
        lines.append(
            f"- {row['name']}: {row['description']}. "
            f"growth={row['growth_class']}, peak_HRR={row['peak_hrr_kW']} kW, "
            f"area={row['area_m2']} m², HRRPUA={row['hrrpua_kW_m2']} kW/m², "
            f"SOOT_YIELD={row['soot_yield']}"
        )
    return "\n".join(lines)


@mcp.tool()
def add_fire_preset(
    preset_name: str,
    position: list[float],
    surface_id: str | None = None,
    scale: float = 1.0,
    flaming_after: float | None = None,
    placement: str = "obst",
    fds_path: str | None = None,
) -> str:
    """Insert a preset fire: &SURF + t-squared &RAMP + burner &OBST or floor &VENT.

    Args:
        preset_name: One of couch, cigarette, car, wastebasket.
        position: Min-corner [x, y, z] of the burner in meters.
        surface_id: Optional &SURF ID. Auto-generated if omitted.
        scale: Multiplier on HRRPUA and peak HRR (area stays the same unless cigarette flaming).
        flaming_after: For cigarette only: seconds until flaming transition. Omit to stay smoldering.
        placement: 'obst' (burner blockage) or 'vent' (PyroSim floor vent, as in door_crack.fds).
        fds_path: Model path. Defaults to the active model.
    """
    if scale <= 0:
        raise ValueError("scale must be positive")
    preset = resolve_preset(preset_name)
    model, path = _load(fds_path)

    surf_id = surface_id or model.unique_id(f"{preset['name']}_fire")
    ramp_id = model.unique_id(f"{surf_id}_ramp")
    obst_id = model.unique_id(f"{preset['name']}_1")

    written: list[str] = []

    reac = _ensure_reac(model, preset)
    if reac:
        written.append(reac)

    lx = float(preset.get("lx") or preset["area"] ** 0.5)
    ly = float(preset.get("ly") or preset["area"] ** 0.5)
    area = lx * ly

    if preset.get("smoldering"):
        flaming_hrr = float(preset.get("flaming_hrr", 35.0)) * scale
        smolder_hrr = float(preset["peak_hrr"]) * scale
        if flaming_after is not None:
            area = float(preset.get("flaming_area", area))
            hrrpua = flaming_hrr / area
            ramp = build_cigarette_ramp(
                flaming_after=flaming_after,
                smolder_hrr=smolder_hrr,
                flaming_hrr=flaming_hrr,
            )
        else:
            hrrpua = smolder_hrr / area
            ramp = build_cigarette_ramp(flaming_after=None, smolder_hrr=smolder_hrr)
    else:
        peak_hrr = float(preset["peak_hrr"]) * scale
        hrrpua = peak_hrr / area
        ramp = build_ramp(preset["growth_class"], peak_hrr)

    written.append(
        model.add_surf_with_ramp(
            surf_id=surf_id,
            hrrpua=hrrpua,
            ramp_id=ramp_id,
            ramp_points=ramp,
            color=preset.get("color", "RED"),
        )
    )
    if placement not in {"obst", "vent"}:
        raise ValueError("placement must be 'obst' or 'vent'")
    bounds = _fire_footprint(preset, position, scale=1.0)
    if placement == "vent":
        # PyroSim samples (door_crack.fds, atrium_with_fans.fds) put burners on a floor VENT.
        z = position[2]
        vent_bounds = [bounds[0], bounds[1], bounds[2], bounds[3], z, z]
        written.append(model.add_vent(vent_bounds, surf_id, vent_id=obst_id))
    else:
        written.append(
            model.add_obst(
                bounds=bounds,
                obst_id=obst_id,
                surf_ids=(surf_id, "INERT", "INERT"),
            )
        )
    _save(model, path)
    return f"Added '{preset['name']}' fire in {path}\n" + "\n".join(written)


@mcp.tool()
def add_custom_fire(
    hrrpua: float,
    growth_rate: str,
    peak_hrr: float,
    fuel_area: float,
    position: list[float],
    surface_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Insert a manual t-squared fire (no preset).

    Args:
        hrrpua: Heat release rate per unit area in kW/m².
        growth_rate: NFPA class: slow, medium, fast, or ultra-fast.
        peak_hrr: Peak heat release rate in kW.
        fuel_area: Burner area in m² (square footprint).
        position: Min-corner [x, y, z] of the burner in meters.
        surface_id: Optional &SURF ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    surf_id = surface_id or model.unique_id("custom_fire")
    ramp_id = model.unique_id(f"{surf_id}_ramp")
    obst_id = model.unique_id("custom_fire_1")
    side = fuel_area ** 0.5
    x, y, z = position
    bounds = [x, x + side, y, y + side, z, z + 0.2]
    written: list[str] = []
    if not any(b.strip().upper().startswith("&REAC") for b in model.blocks):
        written.append(model.add_reac())
    written.append(
        model.add_surf_with_ramp(
            surf_id=surf_id,
            hrrpua=hrrpua,
            ramp_id=ramp_id,
            ramp_points=build_ramp(growth_rate, peak_hrr),
        )
    )
    written.append(
        model.add_obst(bounds=bounds, obst_id=obst_id, surf_ids=(surf_id, "INERT", "INERT"))
    )
    _save(model, path)
    return f"Added custom fire in {path}\n" + "\n".join(written)


@mcp.tool()
def add_mesh(
    bounds: list[float],
    cell_size: float,
    mesh_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Append a &MESH block.

    Args:
        bounds: [x0, x1, y0, y1, z0, z1] in meters.
        cell_size: Cell size in meters.
        mesh_id: Optional mesh ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_mesh(bounds, cell_size, mesh_id=mesh_id)
    _save(model, path)
    return f"Added mesh in {path}\n{block}"


@mcp.tool()
def add_obstruction(
    bounds: list[float],
    material: str = "INERT",
    is_fuel: bool = False,
    obst_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Append an &OBST block.

    Args:
        bounds: [x0, x1, y0, y1, z0, z1] in meters.
        material: SURF_ID applied to the obstruction (or fuel surface if is_fuel).
        is_fuel: If true, top face uses material as a burner (SURF_IDS top/sides/bottom).
        obst_id: Optional obstruction ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    if is_fuel:
        block = model.add_obst(
            bounds, obst_id=obst_id, surf_ids=(material, "INERT", "INERT")
        )
    else:
        block = model.add_obst(bounds, obst_id=obst_id, surf_id=material)
    _save(model, path)
    return f"Added obstruction in {path}\n{block}"


@mcp.tool()
def add_vent(
    bounds: list[float],
    surface_id: str = "OPEN",
    fds_path: str | None = None,
) -> str:
    """Append a &VENT (open boundary, supply, or exhaust).

    Args:
        bounds: [x0, x1, y0, y1, z0, z1] in meters.
        surface_id: SURF_ID, e.g. OPEN, or a supply/exhaust surface.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_vent(bounds, surface_id)
    _save(model, path)
    return f"Added vent in {path}\n{block}"


@mcp.tool()
def import_fds(path: str, copy: bool = True) -> str:
    """Load an existing .fds file as the active model.

    Args:
        path: Source FDS file.
        copy: If true (default), copy into pyrosim-mcp/models so the original is not overwritten.
    """
    global CURRENT_PATH
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"FDS file not found: {path}")
    dest = source
    if copy:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        dest = MODELS_DIR / source.name
        dest.write_text(source.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    model = FdsModel.load(dest)
    CURRENT_PATH = str(dest)
    counts = model.group_counts()
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()) if k not in {"HEAD", "TAIL", "TIME"})
    return f"Active model {dest}  CHID='{model.chid}'  T_END={model.t_end}s\n{summary}"


@mcp.tool()
def list_sample_library(query: str = "") -> str:
    """List PyroSim sample .fds files (skips fds-master verification suite).

    Args:
        query: Optional substring filter on file path.
    """
    root = SAMPLES_ROOT
    if not root.exists():
        return (
            f"Sample library not found at {root}. "
            "Set PYROSIM_SAMPLES to your Thunderhead Samples folder."
        )
    needle = query.lower().strip()
    lines = [f"Samples under {root} (fds-master skipped):"]
    count = 0
    for path in sorted(root.rglob("*.fds")):
        if "fds-master" in path.parts:
            continue
        rel = path.relative_to(root)
        if needle and needle not in str(rel).lower():
            continue
        count += 1
        if count <= 80:
            lines.append(f"  {rel}")
    if count > 80:
        lines.append(f"  ... {count - 80} more. Narrow with query.")
    lines.append(f"Total: {count}. Open one with open_sample(relative_path).")
    return "\n".join(lines)


@mcp.tool()
def open_sample(relative_path: str) -> str:
    """Copy a PyroSim sample into models/ and make it the active FDS file.

    Args:
        relative_path: Path under the Samples folder, e.g. leakage_input_files/door_crack.fds
    """
    source = SAMPLES_ROOT / relative_path
    if not source.exists():
        raise FileNotFoundError(f"Sample not found: {source}")
    return import_fds(str(source), copy=True)


@mcp.tool()
def add_hole(
    bounds: list[float],
    hole_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Cut an opening through obstructions (&HOLE). Used for doors/windows in PyroSim samples.

    Args:
        bounds: [x0, x1, y0, y1, z0, z1] in meters. A thin slab through a wall is typical.
        hole_id: Optional hole ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_hole(bounds, hole_id=hole_id)
    _save(model, path)
    return f"Added hole in {path}\n{block}"


@mcp.tool()
def add_material(
    name: str = "CONCRETE",
    surf_id: str | None = None,
    thickness: float | None = None,
    fds_path: str | None = None,
) -> str:
    """Add a &MATL plus matching solid &SURF from the PyroSim material catalog.

    Args:
        name: CONCRETE, CONCRETE_LIGHT, STEEL, GYPSUM, or GLASS.
        surf_id: Optional SURF ID (defaults to the material name).
        thickness: Override default thickness in meters.
        fds_path: Model path. Defaults to the active model.
    """
    key = name.strip().upper()
    if key not in MATERIALS:
        raise ValueError(f"Unknown material '{name}'. Available: {', '.join(MATERIALS)}")
    spec = MATERIALS[key]
    model, path = _load(fds_path)
    written = [
        model.add_matl(
            key,
            conductivity=float(spec["conductivity"]),
            specific_heat=float(spec["specific_heat"]),
            density=float(spec["density"]),
            emissivity=spec.get("emissivity"),
        )
    ]
    surf_name = surf_id or f"{key}_SURF"
    written.append(
        model.add_surf(
            surf_name,
            color=spec.get("color"),
            matl_id=key,
            thickness=float(thickness if thickness is not None else spec["thickness"]),
            backing="VOID",
        )
    )
    _save(model, path)
    return f"Added material {key} in {path}\n" + "\n".join(written)


@mcp.tool()
def add_surface(
    surf_id: str,
    color: str | None = None,
    vel: float | None = None,
    volume_flow: float | None = None,
    tmp_front: float | None = None,
    hrrpua: float | None = None,
    adiabatic: bool = False,
    leak_path: list[int] | None = None,
    fds_path: str | None = None,
) -> str:
    """Add a generic &SURF (flow, hot patch, adiabatic, leak path, or burner).

    Args:
        surf_id: Surface ID.
        color: Named FDS color.
        vel: Signed velocity (m/s). Negative = supply into domain; positive = exhaust.
        volume_flow: Volume flow (m³/s), FDS convention (positive leaves the domain).
        tmp_front: Front-face temperature (°C).
        hrrpua: Heat release rate per unit area (kW/m²).
        adiabatic: If true, ADIABATIC=.TRUE.
        leak_path: Optional [zone_a, zone_b] for leakage surfaces.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    leak = tuple(leak_path) if leak_path and len(leak_path) == 2 else None
    block = model.add_surf(
        surf_id,
        color=color,
        vel=vel,
        volume_flow=volume_flow,
        tmp_front=tmp_front,
        hrrpua=hrrpua,
        adiabatic=adiabatic,
        leak_path=leak,
    )
    _save(model, path)
    note = f"\n{FLOW_NOTE}" if vel is not None else ""
    return f"Added surface in {path}\n{block}{note}"


@mcp.tool()
def add_open_boundaries(
    faces: list[str] | None = None,
    skip_floor: bool = True,
    fds_path: str | None = None,
) -> str:
    """Add OPEN vents on exterior mesh faces (PyroSim 'Mesh Vent' pattern).

    Args:
        faces: xmin, xmax, ymin, ymax, zmin, zmax. Default: all except the floor.
        skip_floor: If true (default) and faces is omitted, do not open zmin.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_open_boundaries(faces=faces, skip_floor=skip_floor)
    _save(model, path)
    return f"Added OPEN boundaries in {path}\n{block}"


@mcp.tool()
def add_flow_vent(
    bounds: list[float],
    velocity: float,
    surf_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Supply or exhaust vent using SURF VEL (jet-fan / Vent Supply sample pattern).

    Args:
        bounds: Vent XB. One axis may be degenerate (a face).
        velocity: m/s. Negative blows into the domain (supply/jet); positive is exhaust.
        surf_id: Optional surface ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    surf_id = surf_id or model.unique_id("flow")
    color = "GREEN" if velocity < 0 else "BLUE"
    written = [
        model.add_surf(surf_id, color=color, vel=velocity),
        model.add_vent(bounds, surf_id),
    ]
    _save(model, path)
    return f"Added flow vent in {path}\n" + "\n".join(written) + f"\n{FLOW_NOTE}"


@mcp.tool()
def add_hvac_fan(
    inlet: list[float],
    outlet: list[float],
    volume_flow: float,
    fan_id: str | None = None,
    max_pressure: float = 1000.0,
    fds_path: str | None = None,
) -> str:
    """Add a two-node HVAC fan (door_crack.fds / atrium extraction pattern).

    Args:
        inlet: XB of the inlet HVAC vent.
        outlet: XB of the outlet HVAC vent.
        volume_flow: Fan MAX_FLOW in m³/s.
        fan_id: Optional fan ID.
        max_pressure: Fan MAX_PRESSURE (Pa).
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_hvac_fan(
        inlet, outlet, volume_flow, fan_id=fan_id, max_pressure=max_pressure
    )
    _save(model, path)
    return f"Added HVAC fan in {path}\n{block}"


@mcp.tool()
def add_pressure_zone(
    bounds: list[float],
    leak_area: float | None = None,
    zone_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Add a &ZONE (leakage / compartment pressure). See door_crack.fds.

    Args:
        bounds: Zone XB.
        leak_area: Optional leak area in m².
        zone_id: Optional zone ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_zone(bounds, zone_id=zone_id, leak_area=leak_area)
    _save(model, path)
    return f"Added pressure zone in {path}\n{block}"


@mcp.tool()
def add_smoke_detector(
    position: list[float],
    detector_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Add a Cleary ionization smoke detector (atrium_with_fans.fds PROP + DEVC).

    Args:
        position: [x, y, z] in meters.
        detector_id: Optional device ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    written = [model.add_prop_cleary()]
    ident = detector_id or model.unique_id("SD_1")
    written.append(
        model.add_devc(
            "",
            position,
            ident,
            prop_id="Cleary Ionization I1",
        )
    )
    _save(model, path)
    return f"Added smoke detector in {path}\n" + "\n".join(written)


@mcp.tool()
def set_output_controls(
    nframes: int | None = None,
    smoke3d: bool | None = None,
    dt_restart: float | None = None,
    fds_path: str | None = None,
) -> str:
    """Set &DUMP controls the way PyroSim writes them (RENDER_FILE, NFRAMES, SMOKE3D).

    Args:
        nframes: Output frames over T_END.
        smoke3d: Enable 3D smoke files.
        dt_restart: Restart dump interval (s).
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.set_dump(
        nframes=nframes,
        smoke3d=smoke3d,
        dt_restart=dt_restart,
        render_file=f"{model.chid}.ge1",
        column_dump_limit=True,
    )
    _save(model, path)
    return f"Updated DUMP in {path}\n{block}"


@mcp.tool()
def set_ambient(tmpa: float, fds_path: str | None = None) -> str:
    """Set ambient temperature &MISC TMPA (Atrium.fds uses TMPA=21).

    Args:
        tmpa: Ambient temperature in °C.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.set_misc(tmpa=tmpa)
    _save(model, path)
    return f"Updated MISC in {path}\n{block}"


@mcp.tool()
def inspect_model(fds_path: str | None = None) -> str:
    """Namelist census plus geometry/output summary (useful after importing a sample).

    Args:
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    counts = model.group_counts()
    lines = [
        f"Model: {path}",
        f"CHID='{model.chid}'  TITLE='{model.title}'  T_END={model.t_end} s",
        "Namelists: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
        f"IDs ({len(model.used_ids)}): " + ", ".join(sorted(model.used_ids)[:40]),
    ]
    if len(model.used_ids) > 40:
        lines[-1] += f" ... +{len(model.used_ids) - 40} more"
    return "\n".join(lines)


@mcp.tool()
def list_catalog() -> str:
    """Materials, slice quantities, and device quantities seen in the PyroSim sample library."""
    lines = ["Materials:"]
    for name, spec in MATERIALS.items():
        lines.append(
            f"  {name}: k={spec['conductivity']} W/m/K, "
            f"cp={spec['specific_heat']} kJ/kg/K, rho={spec['density']} kg/m³, "
            f"t={spec['thickness']} m — {spec['description']}"
        )
    lines.append("Common SLCF quantities: " + ", ".join(SLICE_QUANTITIES))
    lines.append("Common DEVC quantities: " + ", ".join(DEVICE_QUANTITIES))
    lines.append(FLOW_NOTE)
    lines.append(
        "PyroSim notes from Samples/: every &SLCF has PBX/PBY/PBZ or XB; "
        "velocity slices use VECTOR=.TRUE.; fires are often floor VENTs; "
        "doors are HOLEs; mesh faces use SURF_ID='OPEN'."
    )
    return "\n".join(lines)


@mcp.tool()
def create_2d_slice(
    quantity: str,
    axis: str,
    position: float,
    mesh_id: str | None = None,
    vector: bool = False,
    spec_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Write a 2D &SLCF plane (PBX / PBY / PBZ). PyroSim velocity slices set VECTOR=.TRUE.

    Args:
        quantity: FDS output quantity, e.g. TEMPERATURE, VELOCITY, VISIBILITY.
        axis: Plane normal: x, y, or z.
        position: Plane coordinate in meters.
        mesh_id: Optional mesh to restrict the slice to.
        vector: If true, VECTOR=.TRUE. (standard for VELOCITY in PyroSim samples).
        spec_id: Optional species, e.g. SOOT, PROPANE.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    if quantity.upper() == "VELOCITY" and not vector:
        vector = True
    block = model.add_slcf(
        quantity,
        axis=axis,
        position=position,
        mesh_id=mesh_id,
        vector=vector,
        spec_id=spec_id,
    )
    _save(model, path)
    return f"Added 2D slice in {path}\n{block}"


@mcp.tool()
def create_volumetric_output(
    quantity: str,
    cell_centered: bool = True,
    fds_path: str | None = None,
) -> str:
    """Write a full-domain &SLCF (or &BNDF when quantity looks like boundary data).

    Args:
        quantity: FDS output quantity.
        cell_centered: Use CELL_CENTERED=.TRUE. on &SLCF.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    boundary_names = {"wall temperature", "net heat flux", "gauge heat flux", "radiative heat flux"}
    if quantity.strip().lower() in boundary_names:
        block = model.add_bndf(quantity)
    else:
        block = model.add_slcf(
            quantity, xb=model.domain_xb(), cell_centered=cell_centered
        )
    _save(model, path)
    return f"Added volumetric output in {path}\n{block}"


@mcp.tool()
def create_isosurface(
    quantity: str,
    value: float,
    extra_values: list[float] | None = None,
    fds_path: str | None = None,
) -> str:
    """Write an &ISOF 3D isosurface (PyroSim jet-fan samples use multiple VALUE=).

    Args:
        quantity: FDS output quantity, e.g. TEMPERATURE or VELOCITY.
        value: First isosurface value.
        extra_values: Additional values, e.g. [2, 5, 10, 15] for velocity.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    values = [value] + list(extra_values or [])
    block = model.add_isof(quantity, values)
    _save(model, path)
    return f"Added isosurface in {path}\n{block}"


@mcp.tool()
def show_smoke(
    visibility_factor: float = 3.0,
    soot_yield: float = 0.1,
    fds_path: str | None = None,
) -> str:
    """Set SOOT_YIELD on &REAC and add extinction-coefficient slices for Smokeview.

    Args:
        visibility_factor: Recorded for Smokeview visibility scaling (not an FDS namelist).
        soot_yield: Soot yield on the reaction (no soot = no visible smoke).
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    written: list[str] = []
    existing_fuel = "POLYURETHANE"
    for block in model.blocks:
        if block.strip().upper().startswith("&REAC"):
            match = re.search(r"FUEL\s*=\s*'([^']+)'", block, re.IGNORECASE)
            if match:
                existing_fuel = match.group(1)
            break
    written.append(model.set_reac(fuel=existing_fuel, soot_yield=soot_yield))
    bounds = model.domain_xb()
    z_mid = 0.5 * (bounds[4] + bounds[5])
    y_mid = 0.5 * (bounds[2] + bounds[3])
    written.append(model.add_slcf("VISIBILITY", axis="z", position=z_mid))
    written.append(model.add_slcf("VISIBILITY", axis="y", position=y_mid))
    written.append(
        model.add_slcf("EXTINCTION COEFFICIENT", xb=bounds, cell_centered=True)
    )
    _save(model, path)
    return (
        f"Smoke visualization set in {path} "
        f"(visibility_factor={visibility_factor}, SOOT_YIELD={soot_yield})\n"
        + "\n".join(written)
    )


@mcp.tool()
def add_device(
    quantity: str,
    position: list[float],
    id: str,
    xb: list[float] | None = None,
    statistics: str | None = None,
    orientation: list[float] | None = None,
    spec_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Add a sensor &DEVC. Point devices use XYZ; planar integrals use XB + STATISTICS.

    Args:
        quantity: e.g. THERMOCOUPLE, VISIBILITY, MASS FLUX X, LAYER HEIGHT.
        position: [x, y, z] in meters (ignored if xb is set and you pass a dummy).
        id: Device ID.
        xb: Optional [x0,x1,y0,y1,z0,z1] for AREA INTEGRAL devices.
        statistics: e.g. AREA INTEGRAL (jet-fan mass-flux planes).
        orientation: Optional [ox, oy, oz] for velocity probes.
        spec_id: Optional species ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_devc(
        quantity,
        None if xb is not None else position,
        id,
        xb=xb,
        statistics=statistics,
        orientation=orientation,
        spec_id=spec_id,
    )
    _save(model, path)
    return f"Added device in {path}\n{block}"


@mcp.tool()
def list_outputs(fds_path: str | None = None) -> str:
    """Summarize output blocks currently in the model (SLCF, ISOF, DEVC, BNDF).

    Args:
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    outputs = model.list_outputs()
    geometry = model.geometry_summary()
    counts = model.group_counts()
    lines = [
        f"Model: {path}  CHID='{model.chid}'  T_END={model.t_end} s",
        "Namelists: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
        f"IDs in use ({len(model.used_ids)}): {', '.join(sorted(model.used_ids)) or '(none)'}",
    ]
    lines.append("Geometry / fire:")
    if geometry:
        lines.extend(f"  {item}" for item in geometry)
    else:
        lines.append("  (none)")
    lines.append("Outputs:")
    if outputs:
        lines.extend(f"  {item}" for item in outputs)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


@mcp.tool()
def run_simulation(fds_path: str | None = None, n_cores: int = 1) -> str:
    """Run FDS on a model. Blocks until the solver exits.

    Args:
        fds_path: .fds file to run. Defaults to the active model.
        n_cores: Sets OMP_NUM_THREADS for the FDS process.
    """
    target = _active_path(fds_path)
    exe = os.environ.get("FDS_EXE", "fds")
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(max(1, n_cores))
    try:
        result = subprocess.run(
            [exe, target],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(Path(target).parent),
        )
    except FileNotFoundError:
        return (
            f"FDS executable not found ({exe}). "
            "Set FDS_EXE to the full path of fds.exe (or fds on Linux)."
        )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    parts = [f"FDS exit code {result.returncode} for {target} (OMP_NUM_THREADS={n_cores})"]
    if stdout:
        parts.append(stdout[-4000:])
    if stderr:
        parts.append("stderr:\n" + stderr[-2000:])
    return "\n".join(parts)


@mcp.tool()
def open_smokeview(fds_path: str | None = None) -> str:
    """Open Smokeview for a completed (or in-progress) FDS case.

    Args:
        fds_path: .fds or .smv path. Defaults to the active model.
    """
    target = _active_path(fds_path)
    exe = os.environ.get("SMOKEVIEW_EXE", "smokeview")
    try:
        subprocess.Popen([exe, target])
    except FileNotFoundError:
        return (
            f"Smokeview executable not found ({exe}). "
            "Set SMOKEVIEW_EXE to the full path of smokeview.exe."
        )
    return f"Launched Smokeview: {exe} {target}"


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
