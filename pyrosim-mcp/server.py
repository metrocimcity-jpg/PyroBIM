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
from fire_calcs import (
    FIRE_MODELING_GUIDANCE,
    FUELS,
    characteristic_fire_diameter,
    fuel_mass_from_hrr,
    hrrpua_from_hrr,
    nfpa_502_critical_velocity as calc_nfpa_502,
    ramp_from_hrr_curve,
    recommended_cell_size,
    resolve_fuel,
)
from materials import resolve_material, list_materials as material_rows, MATERIAL_CATEGORIES
from sprinklers import (
    flow_lpm,
    list_sprinkler_summaries,
    resolve_sprinkler,
    resolve_temperature_rating,
)
from detectors import (
    list_detector_summaries,
    resolve_gas,
    resolve_heat,
    resolve_other,
    resolve_smoke,
)
from presets import (
    build_cigarette_ramp,
    build_ramp,
    preset_summaries,
    resolve_preset,
)
from validation import (
    CATEGORIES,
    SERIES,
    VALIDATION_GUIDANCE,
    find_series_dir,
    format_series,
    list_case_files,
    resolve_series,
    search_series,
    validation_roots,
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
def list_sample_library(query: str = "", include_validation: bool = False) -> str:
    """List PyroSim sample .fds files. Optionally include NIST FDS Validation cases.

    Args:
        query: Optional substring filter on file path.
        include_validation: If true, also list fds-master/Validation FDS_Input_Files.
            Prefer list_fds_validation() for the 135-series catalog.
    """
    root = SAMPLES_ROOT
    if not root.exists():
        return (
            f"Sample library not found at {root}. "
            "Set PYROSIM_SAMPLES to your Thunderhead Samples folder."
        )
    needle = query.lower().strip()
    lines = [f"Samples under {root}:"]
    count = 0
    for path in sorted(root.rglob("*.fds")):
        in_fds_master = "fds-master" in path.parts
        if in_fds_master and not include_validation:
            continue
        if in_fds_master and "Validation" not in path.parts:
            continue
        if in_fds_master and "Current_Results" in path.parts:
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
    if not include_validation:
        lines.append(
            f"NIST FDS Validation ({len(SERIES)} series): list_fds_validation() "
            "or list_sample_library(include_validation=True)."
        )
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
        name: Catalog ID or FireBID name, e.g. CONCRETE, STEEL, Oak, Nylon, AISI 304.
        surf_id: Optional SURF ID (defaults to the material name).
        thickness: Override default thickness in meters.
        fds_path: Model path. Defaults to the active model.
    """
    spec = resolve_material(name)
    if spec.get("conductivity") is None or spec.get("density") is None or spec.get("specific_heat") is None:
        raise ValueError(
            f"Material '{name}' is incomplete in FireBID (missing k, ρ, or cp). "
            "Pick a sibling with full thermal properties from list_materials()."
        )
    model, path = _load(fds_path)
    matl_id = spec["id"]
    written = [
        model.add_matl(
            matl_id,
            conductivity=float(spec["conductivity"]),
            specific_heat=float(spec["specific_heat"]),
            density=float(spec["density"]),
            emissivity=spec.get("emissivity"),
            fyi=str(spec.get("description") or "")[:80] or None,
        )
    ]
    surf_name = surf_id or f"{matl_id}_SURF"
    written.append(
        model.add_surf(
            surf_name,
            color=spec.get("color"),
            matl_id=matl_id,
            thickness=float(thickness if thickness is not None else spec["thickness"]),
            backing="VOID",
        )
    )
    _save(model, path)
    note = spec.get("note")
    extra = f"\nNote: {note}" if note else ""
    return f"Added material {matl_id} ({spec['name']}) in {path}\n" + "\n".join(written) + extra


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
    tau_q: float | None = None,
    mlrpua: float | None = None,
    mass_flux: float | None = None,
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
        tau_q: FDS TAU_Q ramp time (s). Negative grows from 0 (Validation burners).
        mlrpua: Mass loss rate per unit area (kg/s/m²) — pool-fire Validation.
        mass_flux: Species mass flux (kg/s/m²).
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
        tau_q=tau_q,
        mlrpua=mlrpua,
        mass_flux=mass_flux,
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
    detector_type: str = "ionization",
    detector_id: str | None = None,
    activation_obscuration: float | None = None,
    fds_path: str | None = None,
) -> str:
    """Add an NFPA 72 / FDS smoke detector (Cleary, Heskestad, or NIST Dunes 2000).

    Args:
        position: [x, y, z] in meters (typically at the ceiling).
        detector_type: ionization, photoelectric, heskestad, cleary_i1/i2,
            cleary_p1/p2, nist_ionization, nist_photoelectric.
        detector_id: Optional DEVC ID.
        activation_obscuration: Override trip point in %/m (Heskestad 3.24, photo 6.6).
        fds_path: Model path. Defaults to the active model.
    """
    spec = resolve_smoke(detector_type)
    model, path = _load(fds_path)
    obsc = (
        activation_obscuration
        if activation_obscuration is not None
        else spec.get("activation_obscuration")
    )
    block = model.add_smoke_detector(
        position,
        prop_id=model.unique_id(spec["name"]),
        detector_id=detector_id,
        cleary=spec.get("cleary"),
        length=spec.get("length"),
        activation_obscuration=obsc,
        smokeview_id=str(spec.get("smokeview_id") or "smoke_detector"),
    )
    _save(model, path)
    return (
        f"Added {spec['name']} smoke detector in {path} ({spec['nfpa']})\n"
        f"{block}"
    )


@mcp.tool()
def add_gas_detector(
    position: list[float],
    gas: str = "co",
    setpoint: float | None = None,
    setpoint_ppm: float | None = None,
    detector_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Add a gas / species detector (VOLUME FRACTION + SPEC_ID).

    Args:
        position: [x, y, z] in meters.
        gas: co, co_low, co2, oxygen, fuel, methane, propane, hcn, hcl, soot.
        setpoint: Mole-fraction trip (overrides the catalog). 70 ppm CO = 7e-5.
        setpoint_ppm: Alternate trip in ppm (converted to mole fraction).
        detector_id: Optional DEVC ID.
        fds_path: Model path. Defaults to the active model.
    """
    spec = resolve_gas(gas)
    if setpoint_ppm is not None:
        trip = float(setpoint_ppm) * 1e-6
    elif setpoint is not None:
        trip = float(setpoint)
    else:
        trip = float(spec["setpoint"])
    model, path = _load(fds_path)
    block = model.add_gas_detector(
        position,
        spec["spec_id"],
        setpoint=trip,
        detector_id=detector_id,
        smokeview_id=str(spec.get("smokeview_id") or "sensor"),
    )
    _save(model, path)
    note = ""
    if spec.get("falling"):
        note = (
            "\nNote: FDS SETPOINT trips when the quantity *rises*. "
            "O2 is logged at 19.5 % vol; use a CTRL if you need a falling alarm."
        )
    return (
        f"Added {spec['name']} gas detector in {path} ({spec['nfpa']})\n"
        f"SPEC_ID='{spec['spec_id']}', SETPOINT={trip} ({spec['unit']})\n"
        f"{block}{note}"
    )


@mcp.tool()
def add_beam_detector(
    start: list[float],
    end: list[float],
    setpoint: float = 15.0,
    detector_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Add a projected-beam smoke detector (PATH OBSCURATION).

    Args:
        start: Transmitter [x, y, z] (m).
        end: Receiver [x, y, z] (m).
        setpoint: Path obscuration trip in percent (FDS Verification uses a measurement;
            15 % is a typical engineering beam alarm).
        detector_id: Optional DEVC ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_beam_detector(start, end, setpoint=setpoint, detector_id=detector_id)
    _save(model, path)
    return f"Added beam detector in {path} (PATH OBSCURATION, SETPOINT={setpoint} %)\n{block}"


@mcp.tool()
def add_aspiration_detector(
    chamber: list[float],
    samples: list[list[float]],
    flowrate: float = 0.3,
    delays: list[float] | None = None,
    detector_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Add an aspirating smoke detector (VESDA-style sampling).

    Args:
        chamber: Detector cabinet XYZ (m).
        samples: Sampling-hole XYZ list.
        flowrate: Per-hole FLOWRATE (default 0.3, FDS Verification).
        delays: Optional transport DELAY (s) per hole. Default 50, 100, 150, …
        detector_id: Optional ASPIRATION DEVC ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_aspiration_detector(
        chamber,
        samples,
        flowrate=flowrate,
        delays=delays,
        detector_id=detector_id,
    )
    _save(model, path)
    return f"Added aspiration detector in {path} ({len(samples)} sample holes)\n{block}"


@mcp.tool()
def add_flame_detector(
    position: list[float],
    setpoint: float = 5.0,
    orientation: list[float] | None = None,
    detector_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Add an IR/UV flame-detector analogue (RADIATIVE HEAT FLUX GAS).

    Args:
        position: [x, y, z] of the sensor (m).
        setpoint: Trip in kW/m² (engineering default 5).
        orientation: View direction [ox, oy, oz]. Default downward (0,0,-1).
        detector_id: Optional DEVC ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_flame_detector(
        position,
        setpoint=setpoint,
        orientation=orientation,
        detector_id=detector_id,
    )
    _save(model, path)
    return f"Added flame detector in {path} (SETPOINT={setpoint} kW/m²)\n{block}"


@mcp.tool()
def add_tenability_device(
    detector_type: str,
    position: list[float] | None = None,
    xb: list[float] | None = None,
    setpoint: float | None = None,
    detector_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Add a tenability / measurement device (visibility, optical density, thermocouple, layer height).

    Args:
        detector_type: visibility, optical_density, thermocouple, layer_height.
        position: [x, y, z] for point devices.
        xb: Required for layer_height (vertical column).
        setpoint: Optional trip (visibility metres, etc.).
        detector_id: Optional DEVC ID.
        fds_path: Model path. Defaults to the active model.
    """
    spec = resolve_other(detector_type)
    if spec["kind"] in {"beam", "aspiration", "flame"}:
        raise ValueError(
            f"Use add_{spec['name']}_detector for '{detector_type}'."
        )
    model, path = _load(fds_path)
    ident = detector_id or model.unique_id(spec["name"][:8].upper())
    trip = setpoint if setpoint is not None else spec.get("setpoint")
    if spec["name"] == "layer_height":
        if xb is None:
            raise ValueError("layer_height needs xb as a vertical column [x,x,y,y,z0,z1]")
        block = model.add_devc(
            spec["quantity"], None, ident, xb=xb, setpoint=trip, linear=True
        )
    else:
        if position is None:
            raise ValueError(f"{spec['name']} needs position [x, y, z]")
        prop_id = None
        glyph = spec.get("smokeview_id")
        if glyph:
            prop_id = model.unique_id(f"{ident}_prop")
            if not model._prop_present(prop_id):
                model._add(f"&PROP ID='{prop_id}', SMOKEVIEW_ID='{glyph}' /", prop_id)
        block = model.add_devc(
            spec["quantity"], position, ident, setpoint=trip, prop_id=prop_id
        )
    _save(model, path)
    return f"Added {spec['name']} in {path} ({spec['nfpa']})\n{block}"


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
    lines = ["Materials (engineering + UMD FireBID / PyroSim materials tutorial):"]
    for spec in MATERIALS.values():
        if spec.get("category") != "engineering":
            continue
        lines.append(
            f"  {spec['id']}: k={spec['conductivity']} W/m/K, "
            f"cp={spec['specific_heat']} kJ/kg/K, rho={spec['density']} kg/m³, "
            f"t={spec['thickness']} m — {spec.get('description', '')}"
        )
    lines.append(
        "Full FireBID categories: "
        + ", ".join(MATERIAL_CATEGORIES)
        + ". Call list_materials(category) for the screenshot library "
        "(plastics, metals, hardwood, softwood, misc_wood, misc)."
    )
    lines.append("Simple-chemistry fuels: " + ", ".join(FUELS))
    lines.append("Common SLCF quantities: " + ", ".join(SLICE_QUANTITIES))
    lines.append("Common DEVC quantities: " + ", ".join(DEVICE_QUANTITIES))
    lines.append(FLOW_NOTE)
    lines.append(
        "PyroSim notes from Samples/: every &SLCF has PBX/PBY/PBZ or XB; "
        "velocity slices use VECTOR=.TRUE.; fires are often floor VENTs; "
        "doors are HOLEs; mesh faces use SURF_ID='OPEN'."
    )
    lines.append("Sprinklers: list_sprinklers() for NFPA 13 pendent/upright/sidewall/ESFR/...")
    lines.append(
        "Detectors: list_detectors() — smoke (Cleary/Heskestad), heat (NFPA 72), "
        "gas (CO/LEL), beam, aspiration, flame."
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


def _apply_fuel(model: FdsModel, fuel_name: str) -> str | None:
    spec = resolve_fuel(fuel_name)
    kwargs = dict(
        fuel=spec["fuel"],
        soot_yield=float(spec.get("soot_yield", 0.01)),
        co_yield=float(spec.get("co_yield", 0.0)),
        heat_of_combustion=spec.get("heat_of_combustion"),
        radiative_fraction=spec.get("radiative_fraction"),
        formula=spec.get("formula") if spec.get("needs_spec") else None,
        c=spec.get("c"),
        h=spec.get("h"),
        o=spec.get("o"),
        n=spec.get("n"),
        fyi=spec.get("description"),
        critical_flame_temperature=spec.get("critical_flame_temperature"),
        needs_spec=bool(spec.get("needs_spec")),
    )
    if any(b.strip().upper().startswith("&REAC") for b in model.blocks):
        return None
    return model.add_reac(**kwargs)


@mcp.tool()
def list_materials(category: str = "") -> str:
    """List solid-material presets (PyroSim engineering library + UMD FireBID table).

    Args:
        category: engineering, plastics, metals, hardwood, softwood, misc_wood, misc, wood.
            Empty lists every category.
    """
    rows = material_rows(category or None)
    lines = [
        "UMD FireBID / PyroSim materials tutorial. Starting-point values, not a standard library.",
        "http://firebid.umd.edu/material-database.php",
        f"Category filter: {category or 'all'} ({len(rows)} entries)",
    ]
    for spec in rows:
        tig = f", Tig={spec['tmp_ign']}°C" if spec.get("tmp_ign") is not None else ""
        lg = f", Lg={spec['heat_of_gasification']} MJ/kg" if spec.get("heat_of_gasification") else ""
        lines.append(
            f"- {spec['id']} ({spec['name']}, {spec['category']}): "
            f"k={spec['conductivity']} W/m/K, ρ={spec['density']} kg/m³, "
            f"cp={spec['specific_heat']} kJ/kg/K{tig}{lg}. {spec.get('source', '')}"
        )
    return "\n".join(lines)


@mcp.tool()
def add_layered_surface(
    surf_id: str,
    materials: list[str],
    thicknesses: list[float],
    color: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Layered &SURF (PyroSim gypsum / insulation / gypsum wall tutorial).

    Args:
        surf_id: Surface ID.
        materials: Catalog names in outside-to-inside order, e.g. [GYPSUM, INSULATION, GYPSUM].
        thicknesses: Layer thicknesses in meters, same length as materials.
        color: Optional named color.
        fds_path: Model path. Defaults to the active model.
    """
    if len(materials) != len(thicknesses) or not materials:
        raise ValueError("materials and thicknesses must be non-empty and the same length")
    model, path = _load(fds_path)
    written: list[str] = []
    ids: list[str] = []
    for name in materials:
        spec = resolve_material(name)
        ids.append(spec["id"])
        written.append(
            model.add_matl(
                spec["id"],
                conductivity=float(spec["conductivity"]),
                specific_heat=float(spec["specific_heat"]),
                density=float(spec["density"]),
                emissivity=spec.get("emissivity"),
                fyi=str(spec.get("description") or "")[:80] or None,
            )
        )
    written.append(
        model.add_surf(
            surf_id,
            color=color or "WHITE",
            matl_id=ids,
            thickness=list(thicknesses),
            backing="VOID",
        )
    )
    _save(model, path)
    return f"Added layered surface in {path}\n" + "\n".join(written)


@mcp.tool()
def list_fuels() -> str:
    """Simple-chemistry fuels for &REAC (Modeling Fire in PyroSim tutorial)."""
    lines = [
        "FDS simple chemistry: C,H,O,N fuel + O2 → H2O, CO2, soot, CO, N2 (mixing-controlled).",
        "https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/modeling-fire/",
    ]
    for spec in FUELS.values():
        lines.append(
            f"- {spec['fuel']}: ΔHc={spec.get('heat_of_combustion')} kJ/kg, "
            f"soot={spec.get('soot_yield')}, CO={spec.get('co_yield')}. {spec.get('description')}"
        )
    return "\n".join(lines)


@mcp.tool()
def add_reaction(
    fuel: str = "PROPANE",
    soot_yield: float | None = None,
    co_yield: float | None = None,
    hcn_yield: float | None = None,
    hcl_yield: float | None = None,
    radiative_fraction: float | None = None,
    fds_path: str | None = None,
) -> str:
    """Add or replace the model's &REAC simple-chemistry reaction.

    Args:
        fuel: PROPANE, N-HEPTANE, METHANE, POLYURETHANE, POLYURETHANE_GM27, WOOD.
        soot_yield: Override catalog soot yield.
        co_yield: Override catalog CO yield.
        hcn_yield: Optional HCN yield (combustion calculator tutorial).
        hcl_yield: Optional HCl yield.
        radiative_fraction: Override catalog χ_r.
        fds_path: Model path. Defaults to the active model.
    """
    spec = resolve_fuel(fuel)
    model, path = _load(fds_path)
    block = model.set_reac(
        fuel=spec["fuel"],
        soot_yield=float(soot_yield if soot_yield is not None else spec.get("soot_yield", 0.01)),
        co_yield=float(co_yield if co_yield is not None else spec.get("co_yield", 0.0)),
        heat_of_combustion=spec.get("heat_of_combustion"),
        radiative_fraction=(
            radiative_fraction
            if radiative_fraction is not None
            else spec.get("radiative_fraction")
        ),
        formula=spec.get("formula") if spec.get("needs_spec") else None,
        c=spec.get("c"),
        h=spec.get("h"),
        o=spec.get("o"),
        n=spec.get("n"),
        fyi=spec.get("description"),
        critical_flame_temperature=spec.get("critical_flame_temperature"),
        needs_spec=bool(spec.get("needs_spec")),
        hcn_yield=hcn_yield if hcn_yield is not None else 0.0,
        hcl_yield=hcl_yield,
    )
    _save(model, path)
    return f"Set reaction in {path}\n{block}"


@mcp.tool()
def fire_stoichiometry(
    hrr_kw: float,
    area_m2: float = 1.0,
    fuel: str = "N-HEPTANE",
    heat_of_combustion: float | None = None,
    tmpa_c: float = 20.0,
) -> str:
    """Convert specified HRR to fuel mass flow (Modeling Fire tutorial).

    m_dot = HRR / ΔHc. FDS injects that fuel so combustion matches the requested HRR.
    Also reports D* and a D*/10 mesh suggestion (NFPA 502 tunnel tutorial).
    """
    spec = resolve_fuel(fuel)
    hoc = float(heat_of_combustion if heat_of_combustion is not None else spec["heat_of_combustion"])
    mdot = fuel_mass_from_hrr(hrr_kw, hoc)
    hrrpua = hrrpua_from_hrr(hrr_kw, area_m2)
    mesh = recommended_cell_size(hrr_kw, tmpa_c=tmpa_c)
    return (
        f"Fuel {spec['fuel']}, ΔHc={hoc} kJ/kg\n"
        f"HRR={hrr_kw} kW over {area_m2} m² → HRRPUA={hrrpua:.4g} kW/m²\n"
        f"Fuel mass flow m_dot={mdot:.6g} kg/s "
        f"({mdot / area_m2:.6g} kg/s/m²)\n"
        f"D*={mesh['d_star_m']:.4g} m; recommended dx≈D*/10={mesh['dx_m']:.4g} m"
    )


@mcp.tool()
def add_hrr_fire(
    peak_hrr: float,
    area: float,
    position: list[float],
    fuel: str = "N-HEPTANE",
    growth_rate: str | None = None,
    hrr_curve: list[list[float]] | None = None,
    surface_id: str | None = None,
    placement: str = "vent",
    radius: float | None = None,
    tau_q: float | None = None,
    fds_path: str | None = None,
) -> str:
    """Specified-HRR fire (Thunderhead Modeling Fire / VTT heptane / McCaffrey pattern).

    Args:
        peak_hrr: Peak heat release rate in kW.
        area: Fuel area in m² (square unless radius is set).
        position: Min-corner [x, y, z] or circle center if radius is set.
        fuel: Simple-chemistry fuel preset.
        growth_rate: Optional NFPA t² class: slow, medium, fast, ultra-fast.
        hrr_curve: Optional experimental [(t, kW), ...] samples (variable HRRPUA).
        surface_id: Optional &SURF ID.
        placement: 'vent' (floor burner) or 'obst'.
        radius: Optional circular vent radius (Li/Ingason / NIST pool fires).
        tau_q: If set, use FDS TAU_Q instead of an explicit RAMP (Validation burners).
        fds_path: Model path. Defaults to the active model.
    """
    if area <= 0 or peak_hrr <= 0:
        raise ValueError("peak_hrr and area must be positive")
    model, path = _load(fds_path)
    written: list[str] = []
    reac = _apply_fuel(model, fuel)
    if reac:
        written.append(reac)
    surf_id = surface_id or model.unique_id("hrr_fire")
    ramp_id = model.unique_id(f"{surf_id}_ramp")
    if hrr_curve:
        pairs = [(float(row[0]), float(row[1])) for row in hrr_curve]
        peak, ramp = ramp_from_hrr_curve(pairs)
        peak_hrr = peak
    elif growth_rate:
        ramp = build_ramp(growth_rate, peak_hrr)
    else:
        ramp = [(0.0, 0.0), (1.0, 1.0), (max(model.t_end, 10.0), 1.0)]
    hrrpua = peak_hrr / area
    if tau_q is not None and not hrr_curve and not growth_rate:
        written.append(
            model.add_surf(surf_id, hrrpua=hrrpua, tau_q=tau_q, color="RED", tmp_front=100.0)
        )
    else:
        written.append(
            model.add_surf_with_ramp(surf_id, hrrpua, ramp_id, ramp, color="RED")
        )
    x, y, z = position
    if radius is not None:
        xb = [x - radius, x + radius, y - radius, y + radius, z, z]
        written.append(
            model.add_vent(xb, surf_id, radius=radius, xyz=[x, y, z], color="RED")
        )
    elif placement == "vent":
        side = area ** 0.5
        written.append(
            model.add_vent([x, x + side, y, y + side, z, z], surf_id)
        )
    else:
        side = area ** 0.5
        written.append(
            model.add_obst(
                [x, x + side, y, y + side, z, z + 0.2],
                surf_ids=(surf_id, "INERT", "INERT"),
            )
        )
    _save(model, path)
    mdot = fuel_mass_from_hrr(peak_hrr, float(resolve_fuel(fuel)["heat_of_combustion"]))
    return (
        f"Added HRR fire in {path} (peak {peak_hrr} kW, HRRPUA={hrrpua:.4g} kW/m², "
        f"m_dot={mdot:.4g} kg/s)\n" + "\n".join(written)
    )


@mcp.tool()
def add_hrrpua_fire(
    hrrpua: float,
    bounds: list[float],
    fuel: str = "WOOD",
    tmp_ign: float | None = 300.0,
    burn_away: bool = True,
    material: str = "Softwood",
    thickness: float = 0.05,
    surface_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """HRRPUA + TMP_IGN + BURN_AWAY fire (Modeling Fire tutorial part 4).

    Args:
        hrrpua: kW/m².
        bounds: Burner OBST [x0, x1, y0, y1, z0, z1].
        fuel: Simple-chemistry fuel.
        tmp_ign: Ignition temperature °C. None skips TMP_IGN.
        burn_away: If true, the obstruction is consumed.
        material: Catalog material for the solid (needed for burn-away mass).
        thickness: Solid thickness in meters.
        surface_id: Optional SURF ID.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    written: list[str] = []
    reac = _apply_fuel(model, fuel)
    if reac:
        written.append(reac)
    spec = resolve_material(material)
    written.append(
        model.add_matl(
            spec["id"],
            conductivity=float(spec["conductivity"]),
            specific_heat=float(spec["specific_heat"]),
            density=float(spec["density"]),
            emissivity=spec.get("emissivity"),
        )
    )
    surf_id = surface_id or model.unique_id("hrrpua_fire")
    written.append(
        model.add_surf(
            surf_id,
            color="ORANGE",
            hrrpua=hrrpua,
            tmp_ign=tmp_ign,
            burn_away=burn_away,
            matl_id=spec["id"],
            thickness=thickness,
        )
    )
    written.append(
        model.add_obst(bounds, surf_id=surf_id, burn_away=burn_away)
    )
    _save(model, path)
    return f"Added HRRPUA fire in {path}\n" + "\n".join(written)


@mcp.tool()
def fire_modeling_guidance() -> str:
    """Thunderhead Modeling Fire + materials + NFPA 502 notes for FDS input."""
    return FIRE_MODELING_GUIDANCE


@mcp.tool()
def nfpa_502_critical_velocity(
    hrr_kw: float,
    height_m: float,
    area_m2: float,
    grade_percent: float = 0.0,
    tmpa_c: float = 20.0,
) -> str:
    """Iterate NFPA 502 critical velocity (2017 equations; 2020 Annex D keeps the same pair).

    Args:
        hrr_kw: Fire heat release rate (kW).
        height_m: Tunnel height H (m).
        area_m2: Tunnel cross-section A (m²).
        grade_percent: Grade in percent. Kg ≈ 1 + 0.0374 |G|^0.8 (level = 0).
        tmpa_c: Approach-air temperature °C.
    """
    grade_factor = 1.0
    if abs(grade_percent) > 1e-9:
        grade_factor = 1.0 + 0.0374 * (abs(grade_percent) ** 0.8)
    result = calc_nfpa_502(
        hrr_kw,
        height_m,
        area_m2,
        grade_factor=grade_factor,
        tmpa_c=tmpa_c,
    )
    mesh = recommended_cell_size(hrr_kw, tmpa_c=tmpa_c)
    return (
        f"NFPA 502 critical velocity\n"
        f"https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/critical-velocity-tunnel/\n"
        f"V_c={result['v_c_m_s']:.4g} m/s, T_f={result['t_f_c']:.4g} °C "
        f"(K1={result['k1']}, Kg={grade_factor:.4g} for {grade_percent}% grade)\n"
        f"D*={mesh['d_star_m']:.4g} m, suggested fire-mesh dx={mesh['dx_m']:.4g} m (D*/10)\n"
        "Long tunnels: set_pressure_solver(max_pressure_iterations=50) and tighten "
        "PRESSURE_TOLERANCE (FDS User Guide §6.6.2)."
    )


@mcp.tool()
def set_pressure_solver(
    pressure_tolerance: float | None = None,
    max_pressure_iterations: int = 50,
    fds_path: str | None = None,
) -> str:
    """Set &PRES for long tunnels (Thunderhead critical-velocity tutorial).

    Args:
        pressure_tolerance: Optional PRESSURE_TOLERANCE. Default FDS is 20/δx².
        max_pressure_iterations: Default 50 (tutorial used 50 vs FDS default 10).
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.set_pres(
        pressure_tolerance=pressure_tolerance,
        max_pressure_iterations=max_pressure_iterations,
    )
    _save(model, path)
    return f"Updated PRES in {path}\n{block}"


@mcp.tool()
def set_wind(
    speed: float,
    direction: float = 270.0,
    z_0: float | None = None,
    z_ref: float | None = None,
    monin_obukhov_length: float | None = None,
    fds_path: str | None = None,
) -> str:
    """Add &WIND (Simple Wind / CSIRO grassland Validation). DIRECTION is meteorological degrees.

    Args:
        speed: Wind speed (m/s).
        direction: Direction the wind comes FROM, degrees (270 = west wind, +X).
        z_0: Optional aerodynamic roughness length (m). CSIRO grassland uses 0.03 m.
        z_ref: Optional reference height (m) for SPEED.
        monin_obukhov_length: Optional Monin–Obukhov L (m). CSIRO uses L=-500.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.set_wind(
        speed,
        direction=direction,
        z_0=z_0,
        z_ref=z_ref,
        monin_obukhov_length=monin_obukhov_length,
    )
    _save(model, path)
    return f"Updated WIND in {path}\n{block}"


@mcp.tool()
def add_velocity_patch(
    bounds: list[float],
    velocity: float,
    component: str = "x",
    fds_path: str | None = None,
) -> str:
    """Specify gas velocity in a volume (Velocity Patch in FDS / jet-fan tutorial).

    Args:
        bounds: Patch XB [x0, x1, y0, y1, z0, z1].
        velocity: Signed P0 (m/s). Negative often used for −X car-park fans.
        component: x, y, or z (VELOCITY_COMPONENT 1/2/3).
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_velocity_patch(bounds, velocity, component=component)
    _save(model, path)
    return f"Added velocity patch in {path}\n{block}"


@mcp.tool()
def add_control(
    ctrl_id: str,
    detector_id: str,
    delay: float = 0.0,
    function_type: str = "ANY",
    fds_path: str | None = None,
) -> str:
    """Activation control (Fire Protection Systems tutorial: exhaust 30 s after detector).

    Args:
        ctrl_id: Control ID.
        detector_id: INPUT_ID of the triggering DEVC (smoke detector, sprinkler, ...).
        delay: Seconds after the detector before the control fires.
        function_type: FDS FUNCTION_TYPE (ANY is typical for one detector).
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    block = model.add_ctrl(
        ctrl_id,
        function_type,
        [detector_id],
        delay=delay if delay else None,
    )
    _save(model, path)
    return (
        f"Added control in {path}\n{block}\n"
        "Attach it with ctrl_id on add_vent / add_obstruction (INITIAL_STATE for doors)."
    )


@mcp.tool()
def list_detectors() -> str:
    """NFPA 72 / FDS smoke, heat, gas, beam, aspiration, and flame detector presets."""
    lines = [
        "FDS detector catalog (PROP + DEVC). Glyphs: smoke_detector, heat_detector, sensor, target.",
        "https://github.com/firemodels/fds/tree/master/Verification/Detectors",
        "NIST Smoke Alarms: open_fds_validation('NIST_Smoke_Alarms').",
        *list_detector_summaries(),
        "Heat ratings (NFPA 72): ordinary 57.2°C, intermediate 79.4, high 121, extra_high 163.",
        "CO default 70 ppm (UL 2034 / NFPA 720). Gas SETPOINT is mole fraction.",
    ]
    return "\n".join(lines)


@mcp.tool()
def list_sprinklers() -> str:
    """NFPA 13 / 13D / 13R / 15 sprinkler types mapped to FDS PROP + Smokeview glyphs."""
    lines = [
        "NFPA 13 sprinkler presets (K*sqrt(P) -> L/min). Smokeview glyphs: "
        "sprinkler_pendent, sprinkler_upright, nozzle. Sidewall uses pendent + ORIENTATION.",
        "PyroSim Generic Commercial Link = 68.33 °C (155 °F ordinary).",
        "https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/fundamentals/5-fire-protection-systems/",
        *list_sprinkler_summaries(),
        "Temperature ratings: ordinary 68.33°C, intermediate 93.3, high 141, extra_high 182.",
        "RTI: standard 148, QR 50, ESFR 36, residential 28 (m·s)^0.5.",
    ]
    return "\n".join(lines)


@mcp.tool()
def add_sprinkler(
    position: list[float],
    sprinkler_type: str = "pendent",
    k_factor: float | None = None,
    pressure_psi: float | None = None,
    flow_rate: float | None = None,
    temperature_rating: str = "ordinary",
    orientation: list[float] | None = None,
    rti: float | None = None,
    sprinkler_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Insert an NFPA 13 sprinkler head (pendent, upright, sidewall, ESFR, deluge, ...).

    Args:
        position: [x, y, z] of the head (m).
        sprinkler_type: See list_sprinklers(). Aliases: pendant, sidewall, esfr, qr, 13d, deluge.
        k_factor: Optional US K-factor (gpm/psi^0.5), e.g. 5.6, 8.0, 14.0, 16.8, 25.2.
        pressure_psi: Operating pressure in psi (NFPA 13 min 7 psi for standard spray).
        flow_rate: Override FLOW_RATE in L/min. Otherwise Q = K * sqrt(P) converted to L/min.
        temperature_rating: ordinary/intermediate/high/... or a number in °C.
        orientation: Spray axis [ox, oy, oz]. Default from the type (sidewall = +X).
        rti: Override RTI (m·s)^0.5.
        sprinkler_id: Optional DEVC ID.
        fds_path: Model path. Defaults to the active model.
    """
    spec = resolve_sprinkler(sprinkler_type)
    k_us = float(k_factor if k_factor is not None else spec["k_us"])
    pressure = float(pressure_psi if pressure_psi is not None else spec["pressure_psi"])
    q_lpm = float(flow_rate if flow_rate is not None else flow_lpm(k_us, pressure))
    t_act = resolve_temperature_rating(temperature_rating)
    if t_act is None:
        t_act = spec["activation_temperature"]
    model, path = _load(fds_path)
    block = model.add_sprinkler_head(
        position,
        flow_rate=q_lpm,
        activation_temperature=t_act,
        rti=float(rti if rti is not None else spec["rti"]),
        particle_velocity=float(spec["particle_velocity"]),
        spray_angle=tuple(spec["spray_angle"]),
        offset=float(spec["offset"]),
        smokeview_id=str(spec["smokeview_id"]),
        orientation=orientation or list(spec["orientation"]),
        open_head=bool(spec["open_head"]),
        sprinkler_id=sprinkler_id,
        prop_id=model.unique_id(spec["name"]),
    )
    _save(model, path)
    return (
        f"Added {spec['name']} sprinkler in {path} ({spec['nfpa']})\n"
        f"K={k_us} @ {pressure} psi → {q_lpm:.3g} L/min, "
        f"T={t_act}°C, RTI={rti if rti is not None else spec['rti']}, "
        f"SMOKEVIEW_ID={spec['smokeview_id']}\n"
        f"{block}"
    )


@mcp.tool()
def add_heat_detector(
    position: list[float],
    detector_type: str = "ordinary",
    activation_temperature: float | None = None,
    rti: float | None = None,
    detector_id: str | None = None,
    fds_path: str | None = None,
) -> str:
    """Add an NFPA 72 spot heat detector (FDS QUANTITY='LINK TEMPERATURE').

    Args:
        position: [x, y, z] in meters.
        detector_type: ordinary (135 °F / 57 °C), intermediate, high, extra_high,
            rate_compensation, rate_of_rise, combination, fds_example (74 °C).
        activation_temperature: Override °C.
        rti: Override RTI (m·s)^0.5. Fast ≈ 50, standard ≈ 148.
        detector_id: Optional DEVC ID.
        fds_path: Model path. Defaults to the active model.
    """
    spec = resolve_heat(detector_type)
    t_act = float(
        activation_temperature if activation_temperature is not None else spec["activation_temperature"]
    )
    rti_val = float(rti if rti is not None else spec["rti"])
    model, path = _load(fds_path)
    block = model.add_heat_detector(
        position,
        activation_temperature=t_act,
        rti=rti_val,
        detector_id=detector_id,
        prop_id=model.unique_id(spec["name"]),
        c_factor=spec.get("c_factor") or None,
        smokeview_id=str(spec.get("smokeview_id") or "heat_detector"),
    )
    _save(model, path)
    return (
        f"Added {spec['name']} heat detector in {path} ({spec['nfpa']})\n"
        f"T={t_act}°C, RTI={rti_val}, SMOKEVIEW_ID={spec.get('smokeview_id')}\n"
        f"{block}"
    )


@mcp.tool()
def list_fds_validation(query: str = "", category: str = "") -> str:
    """List NIST FDS Validation series (firemodels/fds Validation/).

    Args:
        query: Filter on series id, title, or summary (e.g. tunnel, McCaffrey, sprinkler).
        category: Optional category: plume, compartment, ceiling_jet, vegetation,
            tunnel, suppression, burning_rate, pyrolysis, wind, jet_lng, heat_flux,
            velocity, species, pressure, structure, aerosol, flow, materials, scaling.
    """
    rows = search_series(query, category)
    cats = ", ".join(CATEGORIES)
    lines = [
        f"NIST FDS Validation — {len(SERIES)} series on GitHub.",
        "https://github.com/firemodels/fds/tree/master/Validation",
        f"Categories: {cats}",
        f"Showing {len(rows)} match(es). Open with open_fds_validation(series, case).",
        "",
    ]
    roots = validation_roots(SAMPLES_ROOT)
    local_note = f"Local Validation roots: {', '.join(str(p) for p in roots)}" if roots else (
        "No local Validation tree. Set PYROSIM_SAMPLES (…/fds-master) or FDS_VALIDATION."
    )
    lines.append(local_note)
    cap = 40 if query or category else 25
    for row in rows[:cap]:
        local = find_series_dir(row["id"], SAMPLES_ROOT)
        n_cases = len(list_case_files(row["id"], SAMPLES_ROOT)) if local else None
        lines.append("")
        lines.append(format_series(row, local=local, n_cases=n_cases))
    if len(rows) > cap:
        lines.append(f"\n… {len(rows) - cap} more. Narrow query or category.")
    return "\n".join(lines)


@mcp.tool()
def open_fds_validation(series: str, case: str | None = None) -> str:
    """Open a NIST FDS Validation input file as the active model (copied into models/).

    Args:
        series: Validation folder name, e.g. McCaffrey_Plume, Steckler_Compartment,
            CSIRO_Grassland_Fires, Memorial_Tunnel.
        case: Optional .fds file name (or unique substring). Omit to list cases.
    """
    row = resolve_series(series)
    files = list_case_files(row["id"], SAMPLES_ROOT)
    if not files:
        local = find_series_dir(row["id"], SAMPLES_ROOT)
        return (
            f"{format_series(row, local=local)}\n"
            "No local FDS_Input_Files found. Clone firemodels/fds or point "
            "PYROSIM_SAMPLES at a tree that contains fds-master/Validation."
        )
    if not case:
        lines = [
            format_series(row, local=find_series_dir(row["id"], SAMPLES_ROOT), n_cases=len(files)),
            "Cases:",
        ]
        for path in files[:80]:
            lines.append(f"  {path.name}")
        if len(files) > 80:
            lines.append(f"  … {len(files) - 80} more.")
        lines.append("Re-call with case='the_file.fds' to import a copy.")
        return "\n".join(lines)
    needle = case.lower().replace("\\", "/")
    matches = [
        path for path in files
        if needle in path.name.lower() or needle in str(path).lower().replace("\\", "/")
    ]
    if not matches:
        names = ", ".join(p.name for p in files[:12])
        raise FileNotFoundError(
            f"No case matching '{case}' in {row['id']}. Examples: {names}"
        )
    if len(matches) > 1 and not any(p.name.lower() == case.lower() for p in matches):
        listed = "\n".join(f"  {p.name}" for p in matches[:20])
        return f"Multiple matches for '{case}':\n{listed}\nPass the exact file name."
    chosen = next((p for p in matches if p.name.lower() == case.lower()), matches[0])
    imported = import_fds(str(chosen), copy=True)
    return f"Opened Validation case {row['id']}/{chosen.name}\n{row['github']}\n{imported}"


@mcp.tool()
def fds_validation_guidance(topic: str = "") -> str:
    """How to reuse NIST FDS Validation cases (ASTM E1355 / SP 1018-3).

    Args:
        topic: Optional keyword (plume, tunnel, sprinkler, vegetation, pool, wind, …)
            to list matching series plus the tool mapping.
    """
    if not topic.strip():
        return VALIDATION_GUIDANCE
    rows = search_series(topic)
    lines = [VALIDATION_GUIDANCE, "", f"Matches for '{topic}': {len(rows)}"]
    for row in rows[:20]:
        lines.append(f"- {row['id']}: {row['summary']}")
    return "\n".join(lines)


@mcp.tool()
def add_line_device(
    quantity: str,
    bounds: list[float],
    points: int = 20,
    device_id: str | None = None,
    z_id: str = "Height",
    fds_path: str | None = None,
) -> str:
    """Add a McCaffrey-style line of devices (&DEVC XB + POINTS).

    Args:
        quantity: THERMOCOUPLE, W-VELOCITY, TEMPERATURE, VOLUME FRACTION, …
        bounds: Line XB [x0,x1,y0,y1,z0,z1] (typically a vertical line).
        points: Number of samples along the line.
        device_id: Optional DEVC ID.
        z_id: Coordinate label written to the _line.csv (McCaffrey uses Height).
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    ident = device_id or model.unique_id("line_1")
    block = model.add_line_device(quantity, bounds, ident, points=points, z_id=z_id)
    _save(model, path)
    return f"Added line device in {path}\n{block}"


@mcp.tool()
def add_vegetation_bed(
    bounds: list[float],
    packing_ratio: float = 0.0026,
    moisture_fraction: float = 0.06,
    height: float | None = None,
    fds_path: str | None = None,
) -> str:
    """Add a CSIRO-style packed vegetation bed (STATIC PART + INIT packing).

    Args:
        bounds: Fuel-bed XB [x0,x1,y0,y1,z0,z1] in meters.
        packing_ratio: Solid volume fraction (CSIRO C064 uses 0.0026).
        moisture_fraction: Dry-basis moisture on the vegetation SURF.
        height: Particle length / bed height (m). Default = Δz of bounds.
        fds_path: Model path. Defaults to the active model.
    """
    model, path = _load(fds_path)
    if not any(b.strip().upper().startswith("&REAC") for b in model.blocks):
        _apply_fuel(model, "CELLULOSE")
    block = model.add_vegetation_bed(
        bounds,
        packing_ratio=packing_ratio,
        height=height,
        moisture_fraction=moisture_fraction,
    )
    _save(model, path)
    return (
        f"Added vegetation bed in {path} (CSIRO grassland Validation pattern)\n"
        f"{block}"
    )


@mcp.tool()
def pyrosim_examples_index() -> str:
    """Index of Thunderhead PyroSim 2026.1 examples wired into this MCP."""
    return """\
PyroSim 2026.1 examples → MCP tools
https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/

Fundamentals
- Materials and Layered Surfaces → list_materials, add_material, add_layered_surface
  http://firebid.umd.edu/material-database.php
- Fire Protection Systems and Controls → list_detectors, add_sprinkler, add_smoke_detector, add_heat_detector, add_gas_detector, add_beam_detector, add_control
- Basic Data Output → create_2d_slice, add_device, show_smoke
- Fire Design Scenarios / How-to Scenarios → new_model + add_hrr_fire per case

Applications
- Modeling Fire → add_reaction, add_hrr_fire, add_hrrpua_fire, fire_stoichiometry, fire_modeling_guidance
- Critical Velocity / NFPA 502 2020 calculator → nfpa_502_critical_velocity, set_pressure_solver
- Modeling Jet Fans / Velocity Patch → add_velocity_patch, add_flow_vent, add_hvac_fan
- t² HRR freeze / stop after device → add_hrr_fire(growth_rate=...), add_device(..., stop_fds via writer)
- Pressure relief / leakage → add_pressure_zone, add_surface(leak_path=...)
- Simple Wind → set_wind
- Smoke visibility → show_smoke

How-to
- Combustion calculator HCN/HCl/soot → add_reaction(hcn_yield=, hcl_yield=, soot_yield=)
- HVAC pressure drop → add_hvac_fan
- Heat conduction / radiation on surfaces → add_layered_surface, add_material
- MPI meshes → add_mesh (separate meshes; assign MPI in the FDS launch)

NFPA references in presets
- NFPA 13 / 13D / 13R / 15 sprinklers (list_sprinklers)
- NFPA 72 smoke / heat / CO (list_detectors, add_smoke_detector, add_heat_detector, add_gas_detector)
- NFPA 92/92B-style t² growth (add_fire_preset / add_hrr_fire growth_rate)
- NFPA 502 critical velocity (nfpa_502_critical_velocity)

NIST FDS Validation (firemodels/fds Validation/) — {n} series
- list_fds_validation(query, category) / open_fds_validation(series, case)
- fds_validation_guidance()
- McCaffrey line trees → add_line_device; CSIRO grass → add_vegetation_bed, set_wind(L, z_0)
- Steckler door holes → add_hole; pool fires → add_hrr_fire(radius=...); TAU_Q → add_hrr_fire(tau_q=)
- https://github.com/firemodels/fds/tree/master/Validation
""".format(n=len(SERIES))


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
