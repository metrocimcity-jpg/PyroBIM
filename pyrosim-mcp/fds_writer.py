"""FDS namelist writer: build, load, save, and validate .fds models."""

from __future__ import annotations

import re
from pathlib import Path


_NAMELIST_RE = re.compile(r"(&[A-Z][A-Z0-9_]*)\s*(.*?)/", re.DOTALL | re.IGNORECASE)
_ID_RE = re.compile(r"\bID\s*=\s*'([^']+)'", re.IGNORECASE)
_HEAD_CHID_RE = re.compile(r"\bCHID\s*=\s*'([^']+)'", re.IGNORECASE)
_HEAD_TITLE_RE = re.compile(r"\bTITLE\s*=\s*'([^']+)'", re.IGNORECASE)
_T_END_RE = re.compile(r"\bT_END\s*=\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)", re.IGNORECASE)
_DT_RE = re.compile(r"\bDT\s*=\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)", re.IGNORECASE)
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


def fds_fyi(text: str | None) -> str | None:
    """FYI strings cannot contain '/' (namelist terminator) or unescaped quotes."""
    if not text:
        return None
    cleaned = (
        str(text)
        .replace("/", " - ")
        .replace("'", "")
        .replace("\n", " ")
        .strip()
    )
    return cleaned[:120] or None


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

    def __init__(self, chid: str, title: str = "", t_end: float = 600.0, dt: float | None = None):
        self.chid = chid
        self.title = title or chid
        self.t_end = t_end
        self.dt = dt
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

    # Custom fuels need an explicit &SPEC formula; bare FUEL='POLYURETHANE'
    # has no built-in composition and triggers FDS ERROR(171) carbon balance.
    # Use per-carbon (~C1) formulas so MW stays low and PyroSim/FDS do not
    # abort on "high molecular weight fuels not in the FDS database".
    FUEL_FORMULAS: dict[str, str] = {
        "POLYURETHANE": "C1H1.13O0.33N0.16",  # equiv. C6.3H7.1N1O2.1 / 6.3
    }
    FUEL_SPECIFIC_HEAT: dict[str, float] = {
        "POLYURETHANE": 1.0,  # kJ/(kg·K)
    }

    def _reac_text(
        self,
        fuel: str,
        soot_yield: float,
        co_yield: float,
        reac_id: str,
        hcn_yield: float | None = 0.0,
        heat_of_combustion: float | None = 25300.0,
        radiative_fraction: float | None = None,
        formula: str | None = None,
        c: float | None = None,
        h: float | None = None,
        o: float | None = None,
        n: float | None = None,
        fyi: str | None = None,
        critical_flame_temperature: float | None = None,
        needs_spec: bool = False,
        hcl_yield: float | None = None,
    ) -> tuple[str | None, str]:
        """Return optional &SPEC block and &REAC block for fuel chemistry."""
        formula = formula or self.FUEL_FORMULAS.get(fuel.upper())
        spec_block = None
        if formula and (needs_spec or fuel.upper() in self.FUEL_FORMULAS):
            parts = [f"&SPEC ID='{fuel}', FORMULA='{formula}'"]
            cp = self.FUEL_SPECIFIC_HEAT.get(fuel.upper())
            if cp is not None:
                parts.append(f", SPECIFIC_HEAT={fds_num(cp)}")
            spec_block = "".join(parts) + " /"
        reac_parts = [f"&REAC ID='{reac_id}'"]
        if fyi:
            cleaned = fds_fyi(fyi)
            if cleaned:
                reac_parts.append(f"FYI='{cleaned}'")
        reac_parts.append(f"FUEL='{fuel}'")
        if c is not None:
            reac_parts.append(f"C={fds_num(c)}")
        if h is not None:
            reac_parts.append(f"H={fds_num(h)}")
        if o is not None:
            reac_parts.append(f"O={fds_num(o)}")
        if n is not None:
            reac_parts.append(f"N={fds_num(n)}")
        reac_parts.append(f"SOOT_YIELD={fds_num(soot_yield)}")
        reac_parts.append(f"CO_YIELD={fds_num(co_yield)}")
        if hcn_yield is not None:
            reac_parts.append(f"HCN_YIELD={fds_num(hcn_yield)}")
        if hcl_yield is not None:
            reac_parts.append(f"HCL_YIELD={fds_num(hcl_yield)}")
        if heat_of_combustion is not None:
            reac_parts.append(f"HEAT_OF_COMBUSTION={fds_num(heat_of_combustion)}")
        if radiative_fraction is not None:
            reac_parts.append(f"RADIATIVE_FRACTION={fds_num(radiative_fraction)}")
        if critical_flame_temperature is not None:
            reac_parts.append(
                f"CRITICAL_FLAME_TEMPERATURE={fds_num(critical_flame_temperature)}"
            )
        reac_block = ", ".join(reac_parts) + " /"
        return spec_block, reac_block

    def add_reac(
        self,
        fuel: str = "POLYURETHANE",
        soot_yield: float = 0.10,
        co_yield: float = 0.05,
        reac_id: str | None = None,
        hcn_yield: float | None = 0.0,
        heat_of_combustion: float | None = 25300.0,
        radiative_fraction: float | None = None,
        formula: str | None = None,
        c: float | None = None,
        h: float | None = None,
        o: float | None = None,
        n: float | None = None,
        fyi: str | None = None,
        critical_flame_temperature: float | None = None,
        needs_spec: bool = False,
        hcl_yield: float | None = None,
    ) -> str:
        if any(b.strip().upper().startswith("&REAC") for b in self.blocks):
            raise ValueError("A &REAC group is already present")
        use_spec = needs_spec or fuel.upper() in self.FUEL_FORMULAS or bool(formula)
        # SPEC and REAC both use ID=; keep them distinct in our ID registry.
        reac_id = reac_id or (f"{fuel}_RXN" if use_spec else fuel)
        spec_block, reac_block = self._reac_text(
            fuel,
            soot_yield,
            co_yield,
            reac_id,
            hcn_yield=hcn_yield,
            heat_of_combustion=heat_of_combustion,
            radiative_fraction=radiative_fraction,
            formula=formula,
            c=c,
            h=h,
            o=o,
            n=n,
            fyi=fyi,
            critical_flame_temperature=critical_flame_temperature,
            needs_spec=use_spec,
            hcl_yield=hcl_yield,
        )
        written: list[str] = []
        if spec_block and not any(
            b.strip().upper().startswith("&SPEC") and f"ID='{fuel}'" in b
            for b in self.blocks
        ):
            written.append(self._add(spec_block, fuel))
        written.append(self._add(reac_block, reac_id))
        return "\n".join(written)

    def set_reac(
        self,
        fuel: str = "POLYURETHANE",
        soot_yield: float = 0.10,
        co_yield: float = 0.05,
        reac_id: str | None = None,
        hcn_yield: float | None = 0.0,
        heat_of_combustion: float | None = 25300.0,
        radiative_fraction: float | None = None,
        formula: str | None = None,
        c: float | None = None,
        h: float | None = None,
        o: float | None = None,
        n: float | None = None,
        fyi: str | None = None,
        critical_flame_temperature: float | None = None,
        needs_spec: bool = False,
        hcl_yield: float | None = None,
    ) -> str:
        """Add or replace the model's single &REAC group (and fuel &SPEC if needed)."""
        use_spec = needs_spec or fuel.upper() in self.FUEL_FORMULAS or bool(formula)
        reac_id = reac_id or (f"{fuel}_RXN" if use_spec else fuel)
        spec_block, reac_block = self._reac_text(
            fuel,
            soot_yield,
            co_yield,
            reac_id,
            hcn_yield=hcn_yield,
            heat_of_combustion=heat_of_combustion,
            radiative_fraction=radiative_fraction,
            formula=formula,
            c=c,
            h=h,
            o=o,
            n=n,
            fyi=fyi,
            critical_flame_temperature=critical_flame_temperature,
            needs_spec=use_spec,
            hcl_yield=hcl_yield,
        )
        kept: list[str] = []
        for existing in self.blocks:
            upper = existing.strip().upper()
            if upper.startswith("&REAC"):
                self.used_ids -= extract_ids(existing)
                continue
            if (
                use_spec
                and upper.startswith("&SPEC")
                and f"ID='{fuel.upper()}'" in upper.replace('"', "'")
            ):
                self.used_ids -= extract_ids(existing)
                continue
            kept.append(existing)
        self.blocks = kept
        written: list[str] = []
        if spec_block:
            written.append(self._add(spec_block, fuel))
        written.append(self._add(reac_block, reac_id))
        return "\n".join(written)

    def add_surf_with_ramp(
        self,
        surf_id: str,
        hrrpua: float,
        ramp_id: str,
        ramp_points: list[tuple[float, float]],
        color: str = "RED",
        tmp_ign: float | None = None,
        burn_away: bool = False,
        matl_id: str | None = None,
        thickness: float | None = None,
    ) -> str:
        if not ramp_points:
            raise ValueError("ramp_points must contain at least one (t, f) pair")
        self._claim_id(surf_id)
        self._claim_id(ramp_id)
        lines = [
            f"&RAMP ID='{ramp_id}', T={fds_num(t)}, F={fds_num(f)} /"
            for t, f in ramp_points
        ]
        parts = [
            f"&SURF ID='{surf_id}'",
            f"HRRPUA={fds_num(hrrpua)}",
            f"RAMP_Q='{ramp_id}'",
            f"COLOR='{color}'",
        ]
        if tmp_ign is not None:
            parts.append(f"TMP_IGN={fds_num(tmp_ign)}")
        if burn_away:
            parts.append("BURN_AWAY=.TRUE.")
        if matl_id:
            parts.append(f"MATL_ID='{matl_id}'")
        if thickness is not None:
            parts.append(f"THICKNESS={fds_num(thickness)}")
        lines.append(", ".join(parts) + " /")
        block = "\n".join(lines)
        self.blocks.append(block)
        return block

    def add_obst(
        self,
        bounds: list[float],
        obst_id: str | None = None,
        surf_id: str | None = None,
        surf_ids: tuple[str, str, str] | None = None,
        burn_away: bool = False,
        ctrl_id: str | None = None,
        initial_state: bool | None = None,
    ) -> str:
        obst_id = obst_id or self.unique_id("obst_1")
        parts = [f"&OBST XB={format_xb(bounds)}"]
        if surf_ids:
            top, sides, bottom = surf_ids
            parts.append(f"SURF_IDS='{top}','{sides}','{bottom}'")
        elif surf_id:
            parts.append(f"SURF_ID='{surf_id}'")
        if burn_away:
            parts.append("BURN_AWAY=.TRUE.")
        if ctrl_id:
            parts.append(f"CTRL_ID='{ctrl_id}'")
        if initial_state is not None:
            parts.append(f"INITIAL_STATE={fds_bool(initial_state)}")
        parts.append(f"ID='{obst_id}' /")
        block = ", ".join(parts[:-1]) + f", {parts[-1]}"
        return self._add(block, obst_id)

    def add_vent(
        self,
        bounds: list[float] | None,
        surface_id: str,
        vent_id: str | None = None,
        mb: str | None = None,
        radius: float | None = None,
        xyz: list[float] | None = None,
        color: str | None = None,
        ctrl_id: str | None = None,
    ) -> str:
        vent_id = vent_id or self.unique_id("vent_1")
        if mb:
            face = mb.upper()
            allowed = {"XMIN", "XMAX", "YMIN", "YMAX", "ZMIN", "ZMAX"}
            if face not in allowed:
                raise ValueError(f"mb must be one of {sorted(allowed)}")
            parts = [
                f"&VENT ID='{vent_id}'",
                f"MB='{face}'",
                f"SURF_ID='{surface_id}'",
            ]
        else:
            if bounds is None:
                raise ValueError("VENT needs bounds or mb")
            parts = [
                f"&VENT ID='{vent_id}'",
                f"XB={format_xb(bounds, planar=True)}",
                f"SURF_ID='{surface_id}'",
            ]
        if radius is not None:
            parts.append(f"RADIUS={fds_num(radius)}")
        if xyz is not None:
            parts.append(f"XYZ={format_xyz(xyz)}")
        if color:
            parts.append(f"COLOR='{color}'")
        if ctrl_id:
            parts.append(f"CTRL_ID='{ctrl_id}'")
        block = ", ".join(parts) + " /"
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
        parts: list[str] = []
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
        if not parts:
            block = "&DUMP /"
        else:
            block = "&DUMP " + ", ".join(parts) + " /"
        return self._replace_group("DUMP", block)

    def set_misc(
        self,
        tmpa: float | None = None,
        humidity: float | None = None,
        simulation_mode: str | None = None,
        p_inf: float | None = None,
        extra: dict[str, str] | None = None,
    ) -> str:
        parts = ["&MISC"]
        if tmpa is not None:
            parts.append(f"TMPA={fds_num(tmpa)}")
        if humidity is not None:
            parts.append(f"HUMIDITY={fds_num(humidity)}")
        if simulation_mode:
            parts.append(f"SIMULATION_MODE='{simulation_mode}'")
        if p_inf is not None:
            parts.append(f"P_INF={fds_num(p_inf)}")
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
        fyi: str | None = None,
        heat_of_combustion: float | None = None,
        heat_of_reaction: float | None = None,
        n_reactions: int | None = None,
        reference_temperature: float | None = None,
        nu_fuel: float | None = None,
    ) -> str:
        needle = f"ID='{matl_id.upper()}'"
        if any(
            b.strip().upper().startswith("&MATL") and needle in b.upper().replace(" ", "")
            for b in self.blocks
        ):
            return f"&MATL ID='{matl_id}' /  (already present)"
        parts = [f"&MATL ID='{matl_id}'"]
        if fyi:
            cleaned = fds_fyi(fyi)
            if cleaned:
                parts.append(f"FYI='{cleaned}'")
        parts.extend(
            [
                f"CONDUCTIVITY={fds_num(conductivity)}",
                f"SPECIFIC_HEAT={fds_num(specific_heat)}",
                f"DENSITY={fds_num(density)}",
            ]
        )
        if emissivity is not None:
            parts.append(f"EMISSIVITY={fds_num(emissivity)}")
        if heat_of_combustion is not None:
            parts.append(f"HEAT_OF_COMBUSTION={fds_num(heat_of_combustion)}")
        if n_reactions is not None:
            parts.append(f"N_REACTIONS={int(n_reactions)}")
        if reference_temperature is not None:
            parts.append(f"REFERENCE_TEMPERATURE={fds_num(reference_temperature)}")
        if heat_of_reaction is not None:
            parts.append(f"HEAT_OF_REACTION={fds_num(heat_of_reaction)}")
        if nu_fuel is not None:
            parts.append(f"NU_FUEL={fds_num(nu_fuel)}")
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
        matl_id: str | list[str] | tuple[str, ...] | None = None,
        thickness: float | list[float] | tuple[float, ...] | None = None,
        adiabatic: bool = False,
        leak_path: tuple[int, int] | None = None,
        backing: str | None = None,
        ramp_q: str | None = None,
        tmp_ign: float | None = None,
        burn_away: bool = False,
        ctrl_id: str | None = None,
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
        if tmp_ign is not None:
            parts.append(f"TMP_IGN={fds_num(tmp_ign)}")
        if burn_away:
            parts.append("BURN_AWAY=.TRUE.")
        if matl_id:
            if isinstance(matl_id, (list, tuple)):
                parts.append("MATL_ID=" + ",".join(f"'{item}'" for item in matl_id))
            else:
                parts.append(f"MATL_ID='{matl_id}'")
        if thickness is not None:
            if isinstance(thickness, (list, tuple)):
                parts.append("THICKNESS=" + ",".join(fds_num(v) for v in thickness))
            else:
                parts.append(f"THICKNESS={fds_num(thickness)}")
        if adiabatic:
            parts.append("ADIABATIC=.TRUE.")
        if leak_path is not None:
            parts.append(f"LEAK_PATH={leak_path[0]},{leak_path[1]}")
        if backing:
            parts.append(f"BACKING='{backing}'")
        if ctrl_id:
            parts.append(f"CTRL_ID='{ctrl_id}'")
        block = ", ".join(parts) + " /"
        return self._add(block, surf_id)

    def add_open_boundaries(
        self,
        faces: list[str] | None = None,
        skip_floor: bool = True,
    ) -> str:
        """OPEN vents on mesh faces. Uses NIST FDS MB='XMIN' style (activate_sprinklers.fds)."""
        catalog = {
            "xmin": "XMIN",
            "xmax": "XMAX",
            "ymin": "YMIN",
            "ymax": "YMAX",
            "zmin": "ZMIN",
            "zmax": "ZMAX",
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
            written.append(self.add_vent(None, "OPEN", vent_id=vent_id, mb=catalog[name]))
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
        compact = spec_id.upper().replace(" ", "")
        if any(
            b.strip().upper().startswith("&SPEC")
            and f"ID='{compact}'" in b.upper().replace(" ", "")
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
        part_id: str | None = None,
    ) -> str:
        parts = [f"&SLCF QUANTITY='{quantity}'"]
        if spec_id:
            parts.append(f"SPEC_ID='{spec_id}'")
        if part_id:
            parts.append(f"PART_ID='{part_id}'")
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
        setpoint: float | None = None,
        part_id: str | None = None,
        ctrl_id: str | None = None,
        trigger_id: str | None = None,
        initial_state: bool | None = None,
        stop_fds: bool = False,
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
        if part_id:
            parts.append(f"PART_ID='{part_id}'")
        if setpoint is not None:
            parts.append(f"SETPOINT={fds_num(setpoint)}")
        if ctrl_id:
            parts.append(f"CTRL_ID='{ctrl_id}'")
        if trigger_id:
            parts.append(f"DEVC_ID='{trigger_id}'")
        if initial_state is not None:
            parts.append(f"INITIAL_STATE={fds_bool(initial_state)}")
        if stop_fds:
            parts.append("STOP_FDS=.TRUE.")
        block = ", ".join(parts) + " /"
        return self._add(block, ident)

    def set_radi(
        self,
        radiation: bool = True,
        number_radiation_angles: int | None = None,
    ) -> str:
        parts = [f"&RADI RADIATION={fds_bool(radiation)}"]
        if number_radiation_angles is not None:
            parts.append(f"NUMBER_RADIATION_ANGLES={int(number_radiation_angles)}")
        block = ", ".join(parts) + " /"
        return self._replace_group("RADI", block)

    def set_wind(
        self,
        speed: float,
        direction: float = 270.0,
        z_0: float | None = None,
    ) -> str:
        parts = [
            f"&WIND SPEED={fds_num(speed)}",
            f"DIRECTION={fds_num(direction)}",
        ]
        if z_0 is not None:
            parts.append(f"Z_0={fds_num(z_0)}")
        block = ", ".join(parts) + " /"
        return self._replace_group("WIND", block)

    def set_time(self, t_end: float | None = None, dt: float | None = None) -> str:
        if t_end is not None:
            self.t_end = t_end
        if dt is not None:
            self.dt = dt
        return self._time_line()

    def _time_line(self) -> str:
        parts = [f"T_END={fds_num(self.t_end)}"]
        if self.dt is not None:
            parts.append(f"DT={fds_num(self.dt)}")
        return "&TIME " + ", ".join(parts) + " /"

    def add_init(
        self,
        bounds: list[float],
        temperature: float | None = None,
        spec_id: str | None = None,
        mass_fraction: float | None = None,
        init_id: str | None = None,
    ) -> str:
        init_id = init_id or self.unique_id("init_1")
        parts = [f"&INIT ID='{init_id}'", f"XB={format_xb(bounds)}"]
        if temperature is not None:
            parts.append(f"TEMPERATURE={fds_num(temperature)}")
        if spec_id:
            parts.append(f"SPEC_ID='{spec_id}'")
        if mass_fraction is not None:
            parts.append(f"MASS_FRACTION={fds_num(mass_fraction)}")
        block = ", ".join(parts) + " /"
        return self._add(block, init_id)

    def add_ctrl(
        self,
        ctrl_id: str,
        function_type: str,
        input_ids: list[str],
        latch: bool = True,
        delay: float | None = None,
    ) -> str:
        if not input_ids:
            raise ValueError("CTRL needs at least one INPUT_ID")
        inputs = ",".join(f"'{item}'" for item in input_ids)
        parts = [
            f"&CTRL ID='{ctrl_id}'",
            f"FUNCTION_TYPE='{function_type.upper()}'",
            f"INPUT_ID={inputs}",
            f"LATCH={fds_bool(latch)}",
        ]
        if delay is not None:
            parts.append(f"DELAY={fds_num(delay)}")
        block = ", ".join(parts) + " /"
        return self._add(block, ctrl_id)

    def add_water_particles(
        self,
        part_id: str = "water drops",
        diameter: float = 750.0,
    ) -> str:
        written: list[str] = []
        spec_line = self.add_spec("WATER VAPOR")
        if "already present" not in spec_line:
            written.append(spec_line)
        needle = f"ID='{part_id.upper().replace(' ', '')}'"
        if any(
            b.strip().upper().startswith("&PART") and needle in b.upper().replace(" ", "")
            for b in self.blocks
        ):
            written.append(f"&PART ID='{part_id}' /  (already present)")
            return "\n".join(written)
        block = (
            f"&PART ID='{part_id}', SPEC_ID='WATER VAPOR', "
            f"DIAMETER={fds_num(diameter)}, SAMPLING_FACTOR=1, "
            f"QUANTITIES='PARTICLE DIAMETER' /"
        )
        written.append(self._add(block, part_id))
        return "\n".join(written)

    def add_sprinkler_head(
        self,
        position: list[float],
        flow_rate: float = 80.0,
        activation_temperature: float = 74.0,
        rti: float = 148.0,
        particle_velocity: float = 10.0,
        spray_angle: tuple[float, float] | list[float] = (30.0, 80.0),
        offset: float = 0.10,
        diameter: float = 750.0,
        prop_id: str | None = None,
        sprinkler_id: str | None = None,
        part_id: str = "water drops",
        smokeview_id: str = "sprinkler_upright",
        orientation: list[float] | None = None,
        open_head: bool = False,
        c_factor: float | None = None,
        ctrl_id: str | None = None,
    ) -> str:
        """NIST sprinkler: PART water drops + PROP SPRINKLER LINK TEMPERATURE + DEVC.

        Pattern from Verification/Sprinklers_and_Sprays/bucket_test_1.fds.
        FLOW_RATE is L/min. RTI is (m·s)^0.5. Activation temperature is °C.
        Open/deluge heads use a TIME device (SETPOINT=0) instead of a fusible link.
        """
        written = [self.add_water_particles(part_id=part_id, diameter=diameter)]
        prop_id = prop_id or self.unique_id("sprinkler")
        if not any(
            b.strip().upper().startswith("&PROP")
            and f"ID='{prop_id.upper()}'" in b.upper().replace(" ", "")
            for b in self.blocks
        ):
            parts = [
                f"&PROP ID='{prop_id}'",
                "QUANTITY='SPRINKLER LINK TEMPERATURE'",
                f"OFFSET={fds_num(offset)}",
                f"PART_ID='{part_id}'",
                f"FLOW_RATE={fds_num(flow_rate)}",
                f"PARTICLE_VELOCITY={fds_num(particle_velocity)}",
                f"SPRAY_ANGLE={fds_num(spray_angle[0])},{fds_num(spray_angle[1])}",
                f"SMOKEVIEW_ID='{smokeview_id}'",
            ]
            if not open_head:
                parts.append(f"ACTIVATION_TEMPERATURE={fds_num(activation_temperature)}")
                parts.append(f"RTI={fds_num(rti)}")
            if c_factor is not None:
                parts.append(f"C_FACTOR={fds_num(c_factor)}")
            written.append(self._add(", ".join(parts) + " /", prop_id))
        ident = sprinkler_id or self.unique_id("Spr_1")
        if open_head:
            written.append(
                self.add_devc(
                    "TIME",
                    position,
                    ident,
                    prop_id=prop_id,
                    setpoint=0.0,
                    orientation=orientation,
                    ctrl_id=ctrl_id,
                )
            )
        else:
            written.append(
                self.add_devc(
                    "",
                    position,
                    ident,
                    prop_id=prop_id,
                    orientation=orientation,
                    ctrl_id=ctrl_id,
                )
            )
        return "\n".join(written)

    def add_velocity_patch(
        self,
        bounds: list[float],
        velocity: float,
        component: int | str = 1,
        prop_id: str | None = None,
        patch_id: str | None = None,
        clock_id: str = "jet_patch_clock",
    ) -> str:
        """FDS VELOCITY PATCH (jet-fan / sprinkler-entrainment tutorial).

        component: 1/2/3 or x/y/z. P0 is the signed axial velocity (m/s).
        """
        axis = str(component).strip().lower()
        component_map = {"x": 1, "y": 2, "z": 3, "1": 1, "2": 2, "3": 3}
        if axis not in component_map:
            raise ValueError("component must be 1/2/3 or x/y/z")
        index = component_map[axis]
        prop_id = prop_id or self.unique_id(f"vpatch_{'xyz'[index - 1]}")
        written: list[str] = []
        if not any(
            b.strip().upper().startswith("&PROP")
            and f"ID='{prop_id.upper()}'" in b.upper().replace(" ", "")
            for b in self.blocks
        ):
            written.append(
                self._add(
                    (
                        f"&PROP ID='{prop_id}', VELOCITY_COMPONENT={index}, "
                        f"P0={fds_num(velocity)} /"
                    ),
                    prop_id,
                )
            )
        if not any(
            b.strip().upper().startswith("&DEVC")
            and f"ID='{clock_id.upper()}'" in b.upper().replace(" ", "")
            for b in self.blocks
        ):
            written.append(
                self.add_devc("TIME", [0.0, 0.0, 0.0], clock_id, setpoint=0.0)
            )
        patch_id = patch_id or self.unique_id("velocity_patch")
        written.append(
            self.add_devc(
                "VELOCITY PATCH",
                None,
                patch_id,
                xb=bounds,
                prop_id=prop_id,
                trigger_id=clock_id,
            )
        )
        return "\n".join(written)

    def set_pres(
        self,
        pressure_tolerance: float | None = None,
        max_pressure_iterations: int | None = None,
    ) -> str:
        """&PRES for long tunnels (FDS User Guide §6.6.2 / Thunderhead tutorial)."""
        parts = ["&PRES"]
        if pressure_tolerance is not None:
            parts.append(f"PRESSURE_TOLERANCE={fds_num(pressure_tolerance)}")
        if max_pressure_iterations is not None:
            parts.append(f"MAX_PRESSURE_ITERATIONS={int(max_pressure_iterations)}")
        if len(parts) == 1:
            block = "&PRES /"
        else:
            block = ", ".join(parts) + " /"
        return self._replace_group("PRES", block)

    def add_heat_detector(
        self,
        position: list[float],
        activation_temperature: float = 74.0,
        rti: float = 50.0,
        detector_id: str | None = None,
        prop_id: str = "heat_detector",
    ) -> str:
        written: list[str] = []
        if not any(
            b.strip().upper().startswith("&PROP") and f"ID='{prop_id.upper()}'" in b.upper().replace(" ", "")
            for b in self.blocks
        ):
            block = (
                f"&PROP ID='{prop_id}', QUANTITY='LINK TEMPERATURE', "
                f"ACTIVATION_TEMPERATURE={fds_num(activation_temperature)}, "
                f"RTI={fds_num(rti)} /"
            )
            written.append(self._add(block, prop_id))
        ident = detector_id or self.unique_id("HD_1")
        written.append(self.add_devc("", position, ident, prop_id=prop_id))
        return "\n".join(written)

    def add_bndf(self, quantity: str) -> str:
        block = f"&BNDF QUANTITY='{quantity}' /"
        self.blocks.append(block)
        return block

    def to_fds(self) -> str:
        lines = [
            f"&HEAD CHID='{self.chid}', TITLE='{self.title}' /",
            self._time_line(),
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
            if upper.startswith((
                "&MESH", "&OBST", "&VENT", "&SURF", "&REAC", "&HOLE", "&MATL",
                "&HVAC", "&ZONE", "&PART", "&PROP", "&CTRL", "&WIND", "&RADI", "&INIT",
            )):
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
