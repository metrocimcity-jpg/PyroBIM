"""FDS namelist writer: build, load, save, and validate .fds models."""

from __future__ import annotations

import re
from pathlib import Path


_NAMELIST_RE = re.compile(r"(&[A-Z][A-Z0-9_]*)\s*(.*?)/", re.DOTALL | re.IGNORECASE)
_ID_RE = re.compile(r"\bID\s*=\s*'([^']+)'", re.IGNORECASE)
_HEAD_CHID_RE = re.compile(r"\bCHID\s*=\s*'([^']+)'", re.IGNORECASE)
_HEAD_TITLE_RE = re.compile(r"\bTITLE\s*=\s*'([^']+)'", re.IGNORECASE)
_T_END_RE = re.compile(r"\bT_END\s*=\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)", re.IGNORECASE)
_XB_ASSIGN_RE = re.compile(r"\bXB\s*=\s*([^/]+)", re.IGNORECASE)
_SLCF_PLANE_RE = re.compile(r"\bPB[XYZ]\s*=", re.IGNORECASE)

REQUIRED_GROUPS = ("HEAD", "MESH", "TIME", "TAIL")


def parse_xb(block: str) -> list[float] | None:
    """Extract XB=x0,x1,y0,y1,z0,z1 from a namelist, if present."""
    match = _XB_ASSIGN_RE.search(block)
    if not match:
        return None
    raw = re.split(r"[A-Z_]+\s*=", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
    try:
        nums = [float(part.strip()) for part in raw.split(",") if part.strip()]
    except ValueError:
        return None
    if len(nums) != 6:
        return None
    return nums


def fds_num(value: float) -> str:
    """Format a number the way FDS namelists expect."""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6g}"


def fds_bool(value: bool) -> str:
    return ".TRUE." if value else ".FALSE."


def format_xb(bounds: list[float] | tuple[float, ...], *, planar: bool = False) -> str:
    if len(bounds) != 6:
        raise ValueError("bounds must be [x0, x1, y0, y1, z0, z1]")
    extents = [bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]]
    if any(extent < -1e-12 for extent in extents):
        raise ValueError("Each max bound must be greater than or equal to the corresponding min")
    positive = sum(extent > 1e-12 for extent in extents)
    needed = 2 if planar else 3
    if positive < needed:
        kind = "a plane (two extents)" if planar else "a volume (three extents)"
        raise ValueError(f"XB must describe {kind}")
    return ",".join(fds_num(v) for v in bounds)


def format_xyz(position: list[float] | tuple[float, ...]) -> str:
    if len(position) != 3:
        raise ValueError("position must be [x, y, z]")
    return ",".join(fds_num(v) for v in position)


def ijk_from_bounds(bounds: list[float], cell_size: float) -> tuple[int, int, int]:
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    nx = max(1, round((bounds[1] - bounds[0]) / cell_size))
    ny = max(1, round((bounds[3] - bounds[2]) / cell_size))
    nz = max(1, round((bounds[5] - bounds[4]) / cell_size))
    return nx, ny, nz


def parse_namelists(text: str) -> list[tuple[str, str]]:
    """Return (GROUP, full_block) for each namelist in *text*."""
    results: list[tuple[str, str]] = []
    for match in _NAMELIST_RE.finditer(text):
        group = match.group(1).upper().lstrip("&")
        inner = match.group(2).strip().rstrip(",")
        block = f"&{group} {inner} /" if inner else f"&{group} /"
        results.append((group, block))
    return results


def extract_ids(text: str) -> set[str]:
    return set(_ID_RE.findall(text))


def validate_fds_text(text: str) -> list[str]:
    """Return a list of problem descriptions. Empty means the file looks valid."""
    errors: list[str] = []
    if text.count("&") != text.count("/"):
        errors.append(
            f"Unbalanced namelist delimiters: {text.count('&')} '&' vs {text.count('/')} '/'"
        )

    groups = [group for group, _ in parse_namelists(text)]
    present = set(groups)
    for required in REQUIRED_GROUPS:
        if required not in present:
            errors.append(f"Missing required group &{required}")

    if groups and groups[0] != "HEAD":
        errors.append("File should start with &HEAD")
    if groups and groups[-1] != "TAIL":
        errors.append("File should end with &TAIL")

    seen_by_group: dict[str, set[str]] = {}
    # RAMP reuses the same ID across multiple lines. Other groups must be unique
    # within the group. PyroSim HVAC nodes reuse the matching VENT ID.
    for group, block in parse_namelists(text):
        found = _ID_RE.findall(block)
        if not found:
            continue
        ident = found[0]
        if group == "RAMP":
            continue
        bucket = seen_by_group.setdefault(group, set())
        if ident in bucket:
            errors.append(f"Duplicate ID '{ident}' on &{group}")
        bucket.add(ident)

    quote_count = text.count("'")
    if quote_count % 2:
        errors.append("Unbalanced single quotes")

    for group, block in parse_namelists(text):
        if group == "SLCF" and not (_SLCF_PLANE_RE.search(block) or parse_xb(block)):
            errors.append(
                f"&SLCF must specify geometry (PBX/PBY/PBZ or XB): {block.strip()}"
            )

    return errors


class FdsModel:
    """In-memory FDS model: namelist blocks plus a used-ID registry."""

    def __init__(self, chid: str, title: str = "", t_end: float = 600.0):
        self.chid = chid
        self.title = title or chid
        self.t_end = t_end
        self.blocks: list[str] = []
        self.used_ids: set[str] = set()

    def _claim_id(self, ident: str) -> None:
        if ident in self.used_ids:
            raise ValueError(f"ID already used: {ident}")
        self.used_ids.add(ident)

    def unique_id(self, base: str) -> str:
        if base not in self.used_ids:
            return base
        index = 2
        while f"{base}_{index}" in self.used_ids:
            index += 1
        return f"{base}_{index}"

    def _add(self, block: str, *ids: str) -> str:
        for ident in ids:
            self._claim_id(ident)
        self.blocks.append(block)
        return block

    def add_mesh(
        self,
        bounds: list[float],
        cell_size: float,
        mesh_id: str | None = None,
    ) -> str:
        mesh_id = mesh_id or self.unique_id("MESH1")
        ijk = ijk_from_bounds(bounds, cell_size)
        block = (
            f"&MESH IJK={ijk[0]},{ijk[1]},{ijk[2]}, "
            f"XB={format_xb(bounds)}, ID='{mesh_id}' /"
        )
        return self._add(block, mesh_id)

    def add_reac(
        self,
        fuel: str = "POLYURETHANE",
        soot_yield: float = 0.10,
        co_yield: float = 0.05,
        reac_id: str | None = None,
    ) -> str:
        if any(b.strip().upper().startswith("&REAC") for b in self.blocks):
            raise ValueError("A &REAC group is already present")
        reac_id = reac_id or fuel
        block = (
            f"&REAC ID='{reac_id}', FUEL='{fuel}', "
            f"SOOT_YIELD={fds_num(soot_yield)}, CO_YIELD={fds_num(co_yield)} /"
        )
        return self._add(block, reac_id)

    def set_reac(
        self,
        fuel: str = "POLYURETHANE",
        soot_yield: float = 0.10,
        co_yield: float = 0.05,
        reac_id: str | None = None,
    ) -> str:
        """Add or replace the model's single &REAC group."""
        reac_id = reac_id or fuel
        block = (
            f"&REAC ID='{reac_id}', FUEL='{fuel}', "
            f"SOOT_YIELD={fds_num(soot_yield)}, CO_YIELD={fds_num(co_yield)} /"
        )
        for index, existing in enumerate(self.blocks):
            if existing.strip().upper().startswith("&REAC"):
                old_ids = extract_ids(existing)
                self.used_ids -= old_ids
                if reac_id not in self.used_ids:
                    self.used_ids.add(reac_id)
                self.blocks[index] = block
                return block
        return self._add(block, reac_id)

    def add_surf_with_ramp(
        self,
        surf_id: str,
        hrrpua: float,
        ramp_id: str,
        ramp_points: list[tuple[float, float]],
        color: str = "RED",
    ) -> str:
        if not ramp_points:
            raise ValueError("ramp_points must contain at least one (t, f) pair")
        self._claim_id(surf_id)
        self._claim_id(ramp_id)
        lines = [
            f"&RAMP ID='{ramp_id}', T={fds_num(t)}, F={fds_num(f)} /"
            for t, f in ramp_points
        ]
        lines.append(
            f"&SURF ID='{surf_id}', HRRPUA={fds_num(hrrpua)}, "
            f"RAMP_Q='{ramp_id}', COLOR='{color}' /"
        )
        block = "\n".join(lines)
        self.blocks.append(block)
        return block

    def add_obst(
        self,
        bounds: list[float],
        obst_id: str | None = None,
        surf_id: str | None = None,
        surf_ids: tuple[str, str, str] | None = None,
    ) -> str:
        obst_id = obst_id or self.unique_id("obst_1")
        parts = [f"&OBST XB={format_xb(bounds)}"]
        if surf_ids:
            top, sides, bottom = surf_ids
            parts.append(f"SURF_IDS='{top}','{sides}','{bottom}'")
        elif surf_id:
            parts.append(f"SURF_ID='{surf_id}'")
        parts.append(f"ID='{obst_id}' /")
        block = ", ".join(parts[:-1]) + f", {parts[-1]}"
        return self._add(block, obst_id)

    def add_vent(
        self,
        bounds: list[float],
        surface_id: str,
        vent_id: str | None = None,
    ) -> str:
        vent_id = vent_id or self.unique_id("vent_1")
        block = (
            f"&VENT XB={format_xb(bounds, planar=True)}, SURF_ID='{surface_id}', ID='{vent_id}' /"
        )
        return self._add(block, vent_id)

    def _replace_group(self, group: str, block: str) -> str:
        prefix = f"&{group.upper()}"
        for index, existing in enumerate(self.blocks):
            if existing.strip().upper().startswith(prefix):
                self.used_ids -= extract_ids(existing)
                self.used_ids |= extract_ids(block)
                self.blocks[index] = block
                return block
        self.blocks.insert(0, block)
        self.used_ids |= extract_ids(block)
        return block

    def set_dump(
        self,
        nframes: int | None = None,
        smoke3d: bool | None = None,
        dt_restart: float | None = None,
        render_file: str | None = None,
        dt_slcf: float | None = None,
        dt_devc: float | None = None,
        column_dump_limit: bool | None = True,
    ) -> str:
        parts = ["&DUMP"]
        if render_file:
            parts.append(f"RENDER_FILE='{render_file}'")
        if nframes is not None:
            parts.append(f"NFRAMES={int(nframes)}")
        if smoke3d is not None:
            parts.append(f"SMOKE3D={fds_bool(smoke3d)}")
        if dt_restart is not None:
            parts.append(f"DT_RESTART={fds_num(dt_restart)}")
        if dt_slcf is not None:
            parts.append(f"DT_SLCF={fds_num(dt_slcf)}")
        if dt_devc is not None:
            parts.append(f"DT_DEVC={fds_num(dt_devc)}")
        if column_dump_limit is not None:
            parts.append(f"COLUMN_DUMP_LIMIT={fds_bool(column_dump_limit)}")
        block = ", ".join(parts) + " /"
        return self._replace_group("DUMP", block)

    def set_misc(self, tmpa: float | None = None, extra: dict[str, str] | None = None) -> str:
        parts = ["&MISC"]
        if tmpa is not None:
            parts.append(f"TMPA={fds_num(tmpa)}")
        if extra:
            for key, value in extra.items():
                parts.append(f"{key}={value}")
        block = ", ".join(parts) + " /"
        return self._replace_group("MISC", block)

    def add_hole(self, bounds: list[float], hole_id: str | None = None) -> str:
        hole_id = hole_id or self.unique_id("hole_1")
        block = f"&HOLE XB={format_xb(bounds, planar=True)}, ID='{hole_id}' /"
        return self._add(block, hole_id)

    def add_matl(
        self,
        matl_id: str,
        conductivity: float,
        specific_heat: float,
        density: float,
        emissivity: float | None = None,
    ) -> str:
        parts = [
            f"&MATL ID='{matl_id}'",
            f"CONDUCTIVITY={fds_num(conductivity)}",
            f"SPECIFIC_HEAT={fds_num(specific_heat)}",
            f"DENSITY={fds_num(density)}",
        ]
        if emissivity is not None:
            parts.append(f"EMISSIVITY={fds_num(emissivity)}")
        block = ", ".join(parts) + " /"
        return self._add(block, matl_id)

    def add_surf(
        self,
        surf_id: str,
        *,
        color: str | None = None,
        rgb: tuple[int, int, int] | None = None,
        hrrpua: float | None = None,
        vel: float | None = None,
        volume_flow: float | None = None,
        tmp_front: float | None = None,
        matl_id: str | None = None,
        thickness: float | None = None,
        adiabatic: bool = False,
        leak_path: tuple[int, int] | None = None,
        backing: str | None = None,
        ramp_q: str | None = None,
    ) -> str:
        parts = [f"&SURF ID='{surf_id}'"]
        if color:
            parts.append(f"COLOR='{color}'")
        if rgb:
            parts.append(f"RGB={rgb[0]},{rgb[1]},{rgb[2]}")
        if hrrpua is not None:
            parts.append(f"HRRPUA={fds_num(hrrpua)}")
        if ramp_q:
            parts.append(f"RAMP_Q='{ramp_q}'")
        if vel is not None:
            parts.append(f"VEL={fds_num(vel)}")
        if volume_flow is not None:
            parts.append(f"VOLUME_FLOW={fds_num(volume_flow)}")
        if tmp_front is not None:
            parts.append(f"TMP_FRONT={fds_num(tmp_front)}")
        if matl_id:
            parts.append(f"MATL_ID='{matl_id}'")
        if thickness is not None:
            parts.append(f"THICKNESS={fds_num(thickness)}")
        if adiabatic:
            parts.append("ADIABATIC=.TRUE.")
        if leak_path is not None:
            parts.append(f"LEAK_PATH={leak_path[0]},{leak_path[1]}")
        if backing:
            parts.append(f"BACKING='{backing}'")
        block = ", ".join(parts) + " /"
        return self._add(block, surf_id)

    def add_open_boundaries(
        self,
        faces: list[str] | None = None,
        skip_floor: bool = True,
    ) -> str:
        """OPEN vents on mesh-domain faces. Face names: xmin xmax ymin ymax zmin zmax."""
        xb = self.domain_xb()
        x0, x1, y0, y1, z0, z1 = xb
        catalog = {
            "xmin": [x0, x0, y0, y1, z0, z1],
            "xmax": [x1, x1, y0, y1, z0, z1],
            "ymin": [x0, x1, y0, y0, z0, z1],
            "ymax": [x0, x1, y1, y1, z0, z1],
            "zmin": [x0, x1, y0, y1, z0, z0],
            "zmax": [x0, x1, y0, y1, z1, z1],
        }
        chosen = [f.lower() for f in (faces or list(catalog))]
        if skip_floor and faces is None:
            chosen = [name for name in chosen if name != "zmin"]
        unknown = [name for name in chosen if name not in catalog]
        if unknown:
            raise ValueError(f"Unknown faces {unknown}; use xmin/xmax/ymin/ymax/zmin/zmax")
        written: list[str] = []
        for name in chosen:
            vent_id = self.unique_id(f"open_{name}")
            written.append(self.add_vent(catalog[name], "OPEN", vent_id=vent_id))
        return "\n".join(written)

    def add_zone(
        self,
        bounds: list[float],
        zone_id: str | None = None,
        leak_area: float | None = None,
    ) -> str:
        zone_id = zone_id or self.unique_id("Zone01")
        parts = [f"&ZONE ID='{zone_id}'", f"XB={format_xb(bounds)}"]
        if leak_area is not None:
            parts.append(f"LEAK_AREA={fds_num(leak_area)}")
        block = ", ".join(parts) + " /"
        return self._add(block, zone_id)

    def add_hvac_fan(
        self,
        inlet: list[float],
        outlet: list[float],
        volume_flow: float,
        fan_id: str | None = None,
        max_pressure: float = 1000.0,
        area: float | None = None,
        length: float = 0.1,
    ) -> str:
        """Simple two-node HVAC fan (door_crack.fds / atrium_with_fans.fds)."""
        fan_id = fan_id or self.unique_id("FAN")
        in_id = self.unique_id(f"{fan_id}_IN")
        out_id = self.unique_id(f"{fan_id}_OUT")
        duct_id = self.unique_id(f"{fan_id}_DUCT")
        if area is None:
            dims = [
                abs(inlet[1] - inlet[0]),
                abs(inlet[3] - inlet[2]),
                abs(inlet[5] - inlet[4]),
            ]
            nonzero = sorted(d for d in dims if d > 1e-9)
            area = max((nonzero[0] * nonzero[1]) if len(nonzero) >= 2 else 0.01, 0.01)
        perimeter = 4.0 * (area ** 0.5)
        lines = [
            self.add_vent(inlet, "HVAC", vent_id=in_id),
            self.add_vent(outlet, "HVAC", vent_id=out_id),
            f"&HVAC ID='{in_id}', TYPE_ID='NODE', DUCT_ID='{duct_id}', VENT_ID='{in_id}' /",
            f"&HVAC ID='{out_id}', TYPE_ID='NODE', DUCT_ID='{duct_id}', VENT_ID='{out_id}' /",
            (
                f"&HVAC ID='{duct_id}', TYPE_ID='DUCT', AREA={fds_num(area)}, "
                f"PERIMETER={fds_num(perimeter)}, FAN_ID='{fan_id}', "
                f"NODE_ID='{in_id}','{out_id}', LENGTH={fds_num(length)} /"
            ),
            (
                f"&HVAC ID='{fan_id}', TYPE_ID='FAN', MAX_FLOW={fds_num(volume_flow)}, "
                f"MAX_PRESSURE={fds_num(max_pressure)} /"
            ),
        ]
        for extra in lines[2:]:
            self.blocks.append(extra)
            self.used_ids |= extract_ids(extra)
        self.used_ids.add(fan_id)
        self.used_ids.add(duct_id)
        return "\n".join(lines)

    def add_prop_cleary(self, prop_id: str = "Cleary Ionization I1") -> str:
        if any(
            b.strip().upper().startswith("&PROP") and f"ID='{prop_id.upper()}'" in b.upper().replace(" ", "")
            for b in self.blocks
        ):
            return f"&PROP ID='{prop_id}' /  (already present)"
        block = (
            f"&PROP ID='{prop_id}', QUANTITY='CHAMBER OBSCURATION', "
            f"ALPHA_E=2.5, BETA_E=-0.7, ALPHA_C=0.8, BETA_C=-0.9 /"
        )
        return self._add(block, prop_id)

    def add_spec(self, spec_id: str) -> str:
        needle = f"ID='{spec_id.upper()}'"
        if any(
            b.strip().upper().startswith("&SPEC") and needle in b.upper().replace(" ", "")
            for b in self.blocks
        ):
            return f"&SPEC ID='{spec_id}' /  (already present)"
        block = f"&SPEC ID='{spec_id}' /"
        return self._add(block, spec_id)

    def domain_xb(self) -> list[float]:
        """Axis-aligned union of all &MESH XB bounds."""
        boxes: list[list[float]] = []
        for block in self.blocks:
            if not block.strip().upper().startswith("&MESH"):
                continue
            bounds = parse_xb(block)
            if bounds:
                boxes.append(bounds)
        if not boxes:
            raise ValueError("No &MESH with XB found; add a mesh first")
        return [
            min(box[0] for box in boxes),
            max(box[1] for box in boxes),
            min(box[2] for box in boxes),
            max(box[3] for box in boxes),
            min(box[4] for box in boxes),
            max(box[5] for box in boxes),
        ]

    def add_slcf(
        self,
        quantity: str,
        axis: str | None = None,
        position: float | None = None,
        cell_centered: bool = False,
        mesh_id: str | None = None,
        xb: list[float] | None = None,
        vector: bool = False,
        spec_id: str | None = None,
    ) -> str:
        parts = [f"&SLCF QUANTITY='{quantity}'"]
        if spec_id:
            parts.append(f"SPEC_ID='{spec_id}'")
        if axis is not None:
            axis = axis.lower()
            if axis not in {"x", "y", "z"}:
                raise ValueError("axis must be 'x', 'y', or 'z'")
            if position is None:
                raise ValueError("position is required when axis is set")
            plane = {"x": "PBX", "y": "PBY", "z": "PBZ"}[axis]
            parts.append(f"{plane}={fds_num(position)}")
        elif xb is not None:
            parts.append(f"XB={format_xb(xb)}")
        else:
            raise ValueError(
                "SLCF must specify geometry: a plane (axis + position) or xb bounds"
            )
        if vector:
            parts.append("VECTOR=.TRUE.")
        if cell_centered:
            parts.append("CELL_CENTERED=.TRUE.")
        if mesh_id:
            parts.append(f"MESH_ID='{mesh_id}'")
        block = ", ".join(parts) + " /"
        self.blocks.append(block)
        return block

    def add_isof(self, quantity: str, value: float | list[float]) -> str:
        values = value if isinstance(value, list) else [value]
        formatted = ",".join(fds_num(item) for item in values)
        block = f"&ISOF QUANTITY='{quantity}', VALUE={formatted} /"
        self.blocks.append(block)
        return block

    def add_devc(
        self,
        quantity: str,
        position: list[float] | None,
        ident: str,
        *,
        xb: list[float] | None = None,
        statistics: str | None = None,
        orientation: list[float] | None = None,
        spec_id: str | None = None,
        prop_id: str | None = None,
    ) -> str:
        ident = ident or self.unique_id("TC_1")
        if ident in self.used_ids:
            ident = self.unique_id(ident)
        parts = [f"&DEVC ID='{ident}'"]
        if quantity:
            parts.append(f"QUANTITY='{quantity}'")
        if position is not None:
            parts.append(f"XYZ={format_xyz(position)}")
        if xb is not None:
            parts.append(f"XB={format_xb(xb, planar=True)}")
        if statistics:
            parts.append(f"STATISTICS='{statistics}'")
        if orientation:
            if len(orientation) != 3:
                raise ValueError("orientation must be [x, y, z]")
            parts.append("ORIENTATION=" + ",".join(fds_num(v) for v in orientation))
        if spec_id:
            parts.append(f"SPEC_ID='{spec_id}'")
        if prop_id:
            parts.append(f"PROP_ID='{prop_id}'")
        block = ", ".join(parts) + " /"
        return self._add(block, ident)

    def add_bndf(self, quantity: str) -> str:
        block = f"&BNDF QUANTITY='{quantity}' /"
        self.blocks.append(block)
        return block

    def to_fds(self) -> str:
        lines = [
            f"&HEAD CHID='{self.chid}', TITLE='{self.title}' /",
            f"&TIME T_END={fds_num(self.t_end)} /",
            *self.blocks,
            "&TAIL /",
        ]
        return "\n".join(lines) + "\n"

    def save(self, path: str | Path) -> Path:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self.to_fds(), encoding="utf-8")
        return dest

    def list_outputs(self) -> list[str]:
        summaries: list[str] = []
        for block in self.blocks:
            stripped = block.strip()
            upper = stripped.upper()
            if upper.startswith("&SLCF") or upper.startswith("&ISOF") or upper.startswith(
                "&DEVC"
            ) or upper.startswith("&BNDF"):
                summaries.append(stripped.split("\n")[0])
        return summaries

    def geometry_summary(self) -> list[str]:
        summaries: list[str] = []
        for block in self.blocks:
            stripped = block.strip()
            upper = stripped.upper()
            if upper.startswith(("&MESH", "&OBST", "&VENT", "&SURF", "&REAC", "&HOLE", "&MATL", "&HVAC", "&ZONE")):
                summaries.append(stripped.split("\n")[0])
        return summaries

    def group_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for group, _block in parse_namelists(self.to_fds()):
            counts[group] = counts.get(group, 0) + 1
        return counts

    @classmethod
    def load(cls, path: str | Path) -> "FdsModel":
        text = Path(path).read_text(encoding="utf-8")
        namelists = parse_namelists(text)
        chid = "model"
        title = ""
        t_end = 600.0
        blocks: list[str] = []
        for group, block in namelists:
            if group == "HEAD":
                chid_match = _HEAD_CHID_RE.search(block)
                title_match = _HEAD_TITLE_RE.search(block)
                if chid_match:
                    chid = chid_match.group(1)
                if title_match:
                    title = title_match.group(1)
                continue
            if group == "TIME":
                t_match = _T_END_RE.search(block)
                if t_match:
                    t_end = float(t_match.group(1))
                continue
            if group == "TAIL":
                continue
            blocks.append(block)

        model = cls(chid=chid, title=title, t_end=t_end)
        model.blocks = blocks
        model.used_ids = extract_ids("\n".join(blocks))
        return model
