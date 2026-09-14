"""Solid-material presets for FDS &MATL / layered &SURF.

Engineering defaults come from Thunderhead PyroSim samples (tunnel steel,
VTT concrete, atrium gypsum). The bulk library matches the University of
Maryland FireBID thermal-properties table that PyroSim's materials tutorial
points at: http://firebid.umd.edu/material-database.php

These are starting-point values, not certified test data. Duplicate FireBID
rows (same name, different source) keep the first complete k/ρ/cp set.
"""

from __future__ import annotations

import re
from typing import Any

# Display-name categories as shown in the FireBID / PyroSim copy-from-database UI.
MATERIAL_CATEGORIES = (
    "engineering",
    "plastics",
    "metals",
    "hardwood",
    "softwood",
    "misc_wood",
    "misc",
)

_SLUG_RE = re.compile(r"[^A-Z0-9]+")

REFS = {
    1: "Cleary & Quintiere, NISTIR 4664 (1991)",
    2: "Dillon, UMD ISO 9705 analysis (1998)",
    3: "Dlugogorski et al., Wood & Fire Safety (2000)",
    4: "Harper, Handbook of Building Materials for Fire Protection (2004)",
    5: "Hopkins & Quintiere, Fire Safety Journal (1996)",
    6: "Incropera et al., Fundamentals of Heat and Mass Transfer, 6th ed. (2007)",
    7: "Janssens, Thermophysical Properties of Wood (1991)",
    8: "Lienhard & Lienhard, A Heat Transfer Textbook, 3rd ed. (2006)",
    9: "Quintiere & Harkleroad, NBSIR 84-2943 (1984)",
    10: "Spearpoint & Quintiere, Fire Safety Journal (2001)",
    11: "Tewarson, SFPE Handbook 3rd ed. (2002)",
    12: "Tran & White, Fire and Materials (1992)",
    13: "Young, University Physics, 7th ed. (1992)",
    14: "Janssens, Interflam '93 heat of gasification of wood",
    15: "Drysdale / ATF NIST Multi-Floor Validation (PyroSim STEEL)",
    16: "NBSIR/ATF-style concrete (atrium_with_fans.fds)",
    17: "Generic example concrete (Stairs.fds)",
    18: "Isolatek BLAZE-SHIELD DC/F (PyroSim insulation example)",
}


def slug_id(name: str) -> str:
    text = _SLUG_RE.sub("_", name.upper().replace("/", " ")).strip("_")
    return text or "MATL"


def _entry(
    name: str,
    category: str,
    conductivity: float | None,
    density: float | None,
    specific_heat: float | None,
    *,
    ref: int,
    tig_k: float | None = None,
    heat_of_gasification: float | None = None,
    emissivity: float | None = None,
    thickness: float | None = None,
    color: str | None = None,
    note: str = "",
    fds_id: str | None = None,
) -> dict[str, Any]:
    ident = fds_id or slug_id(name)
    complete = conductivity is not None and density is not None and specific_heat is not None
    if emissivity is None:
        emissivity = {
            "metals": 0.8,
            "plastics": 0.9,
            "hardwood": 0.9,
            "softwood": 0.9,
            "misc_wood": 0.9,
            "misc": 0.9,
            "engineering": 0.9,
        }.get(category, 0.9)
    if thickness is None:
        thickness = {
            "metals": 0.003,
            "plastics": 0.01,
            "hardwood": 0.02,
            "softwood": 0.02,
            "misc_wood": 0.016,
            "misc": 0.01,
            "engineering": 0.02,
        }.get(category, 0.01)
    if color is None:
        color = {
            "metals": "GRAY 80",
            "plastics": "WHITE",
            "hardwood": "BROWN",
            "softwood": "TAN",
            "misc_wood": "BEIGE",
            "misc": "GRAY 50",
            "engineering": "GRAY 50",
        }.get(category, "GRAY 50")
    row: dict[str, Any] = {
        "id": ident,
        "name": name,
        "category": category,
        "conductivity": conductivity,
        "density": density,
        "specific_heat": specific_heat,
        "emissivity": emissivity,
        "thickness": thickness,
        "color": color,
        "complete": complete,
        "ref": ref,
        "source": REFS[ref],
        "description": f"UMD FireBID / {REFS[ref]}" if ref <= 14 else REFS[ref],
    }
    if tig_k is not None:
        row["tig_k"] = tig_k
        row["tmp_ign"] = round(tig_k - 273.15, 1)
    if heat_of_gasification is not None:
        row["heat_of_gasification"] = heat_of_gasification  # MJ/kg
        row["heat_of_reaction"] = heat_of_gasification * 1000.0  # kJ/kg
    if note:
        row["note"] = note
    return row


# PyroSim sample / tutorial materials (always complete).
ENGINEERING_MATERIALS: dict[str, dict[str, Any]] = {
    "CONCRETE": _entry(
        "CONCRETE",
        "engineering",
        1.8,
        2280.0,
        1.04,
        ref=16,
        emissivity=0.9,
        thickness=0.3,
        color="GRAY 50",
        fds_id="CONCRETE",
    ),
    "CONCRETE_LIGHT": _entry(
        "CONCRETE_LIGHT",
        "engineering",
        1.0,
        2200.0,
        0.88,
        ref=17,
        emissivity=0.8,
        thickness=0.25,
        color="GRAY 35",
        fds_id="CONCRETE_LIGHT",
    ),
    "STEEL": _entry(
        "STEEL",
        "engineering",
        45.8,
        7850.0,
        0.46,
        ref=15,
        emissivity=0.95,
        thickness=0.001,
        color="GRAY 80",
        fds_id="STEEL",
        note="1 mm stainless/steel lining used in the Li/Ingason critical-velocity tunnel sample.",
    ),
    "GYPSUM": _entry(
        "GYPSUM",
        "engineering",
        0.17,
        930.0,
        1.09,
        ref=6,
        emissivity=0.9,
        thickness=0.016,
        color="WHITE",
        fds_id="GYPSUM",
        note="PyroSim layered-wall tutorial (½ in gypsum board).",
    ),
    "GLASS": _entry(
        "GLASS",
        "engineering",
        0.8,
        2500.0,
        0.84,
        ref=13,
        emissivity=0.9,
        thickness=0.006,
        color="CYAN",
        fds_id="GLASS",
    ),
    "INSULATION": _entry(
        "INSULATION",
        "engineering",
        0.05,
        208.0,
        0.8,
        ref=18,
        emissivity=0.9,
        thickness=0.09,
        color="YELLOW",
        fds_id="INSULATION",
        note="Room-temperature Isolatek-style values; PyroSim example also has k/cp ramps.",
    ),
}


def _firebid_rows() -> list[dict[str, Any]]:
    """First complete (or best-effort) FireBID row per screenshot name."""
    hwood = dict(category="hardwood")
    swood = dict(category="softwood")
    mwood = dict(category="misc_wood")
    return [
        # Metals
        _entry("Aluminum", "metals", 205.0, 2702.0, 0.903, ref=13, note="Young gave k only; ρ/cp from pure Al (Incropera)."),
        _entry("Aluminum, 6061", "metals", 167.0, 2700.0, 0.896, ref=8),
        _entry("Aluminum, 7075", "metals", 130.0, 2800.0, 0.841, ref=8),
        _entry("Aluminum, Duralumin (4% Cu 0.5% Mg)", "metals", 177.0, 2770.0, 0.875, ref=6, tig_k=775.0),
        _entry("Aluminum, Pure", "metals", 237.0, 2702.0, 0.903, ref=6, tig_k=933.0),
        _entry("Stainless Steel, AISI 304", "metals", 14.9, 7900.0, 0.477, ref=6, tig_k=1670.0),
        _entry("Stainless Steel, AISI 316", "metals", 13.4, 8238.0, 0.468, ref=6),
        _entry("Stainless Steel, AISI 347", "metals", 14.2, 7978.0, 0.48, ref=6),
        _entry("Stainless Steel, AISI 410", "metals", 25.0, 7700.0, 0.46, ref=8),
        _entry("Steel, 0.5% C", "metals", 54.0, 7833.0, 0.465, ref=8),
        _entry("Steel, 1% C", "metals", 43.0, 7801.0, 0.473, ref=8),
        _entry("Steel, 1.5% C", "metals", 36.0, 7753.0, 0.486, ref=8),
        _entry("Steel, AISI 1010", "metals", 63.9, 7832.0, 0.434, ref=6),
        _entry("Steel, Plain", "metals", 60.5, 7854.0, 0.434, ref=6),
        # Plastics — use Tig k/ρ/cp when room-temperature set is incomplete.
        _entry("Nylon", "plastics", 0.33, 1169.0, 2.3, ref=5, tig_k=653.0, heat_of_gasification=3.8, note="Hopkins & Quintiere properties at Tig."),
        _entry("Polyester", "plastics", 0.20, 1345.0, 1.15, ref=4, tig_k=680.0),
        _entry("Polyethylene", "plastics", 0.64, 955.0, 3.0, ref=5, tig_k=573.0, heat_of_gasification=3.6, note="Tig properties (room-temperature k not tabulated)."),
        _entry("Polyethylene, Foam", "plastics", 0.036, 30.0, 2.3, ref=4, heat_of_gasification=1.55, note="Lg from Harper; k/ρ/cp are typical PE foam fills (FireBID has Lg only)."),
        _entry("Polyethylene, HD", "plastics", 0.43, 959.0, 2.0, ref=4, tig_k=653.0, heat_of_gasification=2.30),
        _entry("Polyethylene, LD", "plastics", 0.38, 925.0, 1.55, ref=4, tig_k=650.0, heat_of_gasification=1.80),
        _entry("Polyethylene, MD", "plastics", 0.40, 929.0, 1.7, ref=4, tig_k=635.0),
        _entry("Polymethylmethacrylate", "plastics", 0.43, 1190.0, 4.1, ref=5, tig_k=453.0, heat_of_gasification=2.8, note="PMMA; Tig properties from Hopkins & Quintiere."),
        _entry("Polypropylene", "plastics", 0.15, 880.0, 1.88, ref=4, tig_k=640.0, heat_of_gasification=2.00),
        _entry("Polystyrene", "plastics", 0.14, 1045.0, 1.25, ref=4, tig_k=629.0, heat_of_gasification=1.60),
        _entry("Polystyrene Foam", "plastics", 0.033, 32.0, 1.3, ref=11, tig_k=649.0, heat_of_gasification=1.6, note="k from Tewarson/Young foam row; ρ/cp typical EPS."),
        _entry("Polyurethane", "plastics", 0.02, 30.0, 1.4, ref=13, note="Young listed k only; ρ/cp typical flexible foam."),
        _entry("Polyurethane, Flexible", "plastics", 0.034, 30.0, 1.4, ref=4, tig_k=651.0, heat_of_gasification=1.95, note="Lg/Tig from Harper; k/ρ/cp typical flexible PU foam."),
        _entry("Polyurethane, Rigid", "plastics", 0.19, 1100.0, 1.76, ref=4, tig_k=651.0, heat_of_gasification=3.25),
        _entry("Polyvinylchloride", "plastics", 0.19, 1400.0, 1.0, ref=2, tig_k=688.0, heat_of_gasification=3.1, note="k/ρ/cp typical rigid PVC; FireBID row is mostly Tig/Lg."),
        _entry("Rigid Polyurethane Foam", "plastics", 0.025, 32.0, 1.4, ref=1, tig_k=643.0, heat_of_gasification=3.4, note="Thermal inertia 0.04 at Tig in FireBID; k/ρ/cp typical rigid foam."),
        _entry("Rubber, Hard", "plastics", 0.16, 1190.0, 1.4, ref=6, note="Incropera k/ρ; cp typical elastomer."),
        _entry("Rubber, Soft", "plastics", 0.13, 1100.0, 2.01, ref=6),
        _entry("SBR", "plastics", 0.17, 1100.0, 1.88, ref=4, tig_k=664.0, heat_of_gasification=2.30),
        _entry("Teflon", "plastics", 0.35, 2200.0, 1.0, ref=6, note="Incropera k/ρ; cp typical PTFE."),
        # Hardwood
        _entry("Ash", **hwood, conductivity=0.16, density=740.0, specific_heat=1.6, ref=8, note="k range 0.15–1.30; using 0.16. cp typical hardwood."),
        _entry("Balsa", **hwood, conductivity=0.05, density=100.0, specific_heat=2.0, ref=8, note="Lienhard row (k=0.05, ρ=100). Incropera ρ=1740 looks swapped."),
        _entry("Hardwood", **hwood, conductivity=0.16, density=720.0, specific_heat=1.255, ref=6, heat_of_gasification=3.068),
        _entry("Mahogany", **hwood, conductivity=0.16, density=700.0, specific_heat=1.3, ref=8, note="cp typical hardwood."),
        _entry("Oak", **hwood, conductivity=0.17, density=545.0, specific_heat=2.385, ref=6, note="First FireBID Oak row — the PyroSim materials tutorial example."),
        _entry("Oven Dry Oak", **hwood, conductivity=0.17, density=545.0, specific_heat=2.385, ref=12, tig_k=574.0, note="Tig from Tran & White; k/ρ/cp from Oak (Incropera)."),
        _entry("Red Oak", **hwood, conductivity=0.17, density=660.0, specific_heat=2.4, ref=10, heat_of_gasification=7.3, note="Lg 5.1–9.5 MJ/kg (Spearpoint); thermal props typical red oak."),
        _entry("Victorian Ash", **hwood, conductivity=0.16, density=720.0, specific_heat=1.255, ref=14, heat_of_gasification=2.57, note="Lg from Janssens; thermal props from generic Hardwood."),
        _entry("Blackbutt", **hwood, conductivity=0.16, density=720.0, specific_heat=1.255, ref=14, heat_of_gasification=2.54, note="Lg from Janssens; thermal props from generic Hardwood."),
        # Softwood
        _entry("Cypress", **swood, conductivity=0.097, density=465.0, specific_heat=1.6, ref=6, note="cp typical softwood."),
        _entry("Douglas Fir", **swood, conductivity=0.11, density=510.0, specific_heat=2.72, ref=10, heat_of_gasification=6.5, note="Lg 4.6–8.4 MJ/kg; k/cp from Fir (Incropera)."),
        _entry("Douglas Fir, Plywood", **swood, conductivity=0.12, density=550.0, specific_heat=1.2, ref=8),
        _entry("Fir", **swood, conductivity=0.11, density=415.0, specific_heat=2.72, ref=6),
        _entry("Oven Dry Douglas Fir", **swood, conductivity=0.11, density=510.0, specific_heat=2.72, ref=7, tig_k=623.0),
        _entry("Particle board", **swood, conductivity=0.14, density=800.0, specific_heat=1.3, ref=8),
        _entry("Pitch pine", **swood, conductivity=0.14, density=450.0, specific_heat=1.6, ref=8, note="cp typical pine."),
        _entry("Softwood", **swood, conductivity=0.12, density=510.0, specific_heat=1.38, ref=6, heat_of_gasification=2.555),
        _entry("Spruce", **swood, conductivity=0.11, density=441.0, specific_heat=1.6, ref=8, note="FireBID lists ρ=4410; treated as 441 kg/m³ (typo)."),
        _entry("White Pine", **swood, conductivity=0.11, density=435.0, specific_heat=1.6, ref=6, note="cp typical pine."),
        _entry("Yellow Pine", **swood, conductivity=0.15, density=640.0, specific_heat=2.805, ref=6),
        _entry("Western Red Cedar", **swood, conductivity=0.12, density=510.0, specific_heat=1.38, ref=14, heat_of_gasification=3.27),
        _entry("Redwood", **swood, conductivity=0.12, density=510.0, specific_heat=1.38, ref=14, heat_of_gasification=3.14),
        _entry("Radiata Pine", **swood, conductivity=0.12, density=510.0, specific_heat=1.38, ref=14, heat_of_gasification=3.22),
        # Misc wood / building
        _entry("Gypsum / Plaster Board", **mwood, conductivity=0.17, density=800.0, specific_heat=1.09, ref=6, thickness=0.016, color="WHITE"),
        _entry("Particleboard, HD", **mwood, conductivity=0.17, density=1000.0, specific_heat=1.3, ref=6),
        _entry("Particleboard, LD", **mwood, conductivity=0.078, density=590.0, specific_heat=1.3, ref=6),
        _entry("Plywood", **mwood, conductivity=0.12, density=545.0, specific_heat=1.215, ref=6),
        _entry("Wood", **mwood, conductivity=0.12, density=510.0, specific_heat=1.38, ref=13, note="Young listed a k range; using generic softwood."),
        # Misc
        _entry("Acoustic Tile", "misc", 0.058, 290.0, 1.34, ref=6),
        _entry("Cotton", "misc", 0.06, 80.0, 1.3, ref=6, note="FireBID Cp=0.13 looks like a unit error; using 1.3 kJ/kg/K."),
        _entry("Fiberglass", "misc", 0.04, 48.0, 0.84, ref=13, note="Young listed k only; ρ/cp typical fiberglass batt."),
        _entry("Glass, Plate", "misc", 1.4, 2225.0, 0.835, ref=6, thickness=0.006, color="CYAN"),
        _entry("Glass, Pyrex", "misc", 1.4, 2500.0, 0.75, ref=6, thickness=0.006, color="CYAN"),
        _entry("Leather", "misc", 0.159, 998.0, 1.5, ref=6, note="cp typical leather."),
        _entry("Paper", "misc", 0.18, 930.0, 1.34, ref=6),
        _entry("Paraffin", "misc", 0.24, 900.0, 2.89, ref=6),
        _entry("Refrigerant, R134a", "misc", 80.3, 1198.0, 1.432, ref=6, note="Saturated-liquid values; not a wall material."),
        _entry("Refrigerant, R22", "misc", 82.6, 1183.0, 1.265, ref=6, note="Saturated-liquid values; not a wall material."),
        _entry("Wool Felt", "misc", 0.04, 200.0, 1.4, ref=13, note="Young listed k only; ρ/cp typical felt."),
    ]


FIREBID_MATERIALS: dict[str, dict[str, Any]] = {}
for _row in _firebid_rows():
    FIREBID_MATERIALS[_row["id"]] = _row

# Combined lookup. Engineering IDs win on STEEL/GYPSUM/GLASS/CONCRETE.
MATERIALS: dict[str, dict[str, Any]] = {**FIREBID_MATERIALS, **ENGINEERING_MATERIALS}

ALIASES: dict[str, str] = {
    "PMMA": "POLYMETHYLMETHACRYLATE",
    "PLEXIGLASS": "POLYMETHYLMETHACRYLATE",
    "PVC": "POLYVINYLCHLORIDE",
    "PTFE": "TEFLON",
    "SS304": "STAINLESS_STEEL_AISI_304",
    "SS316": "STAINLESS_STEEL_AISI_316",
    "STAINLESS": "STAINLESS_STEEL_AISI_304",
    "STAINLESS_STEEL": "STAINLESS_STEEL_AISI_304",
    "ALUMINUM_DURALUMIN_4_CU_0_5_MG": "ALUMINUM_DURALUMIN_4_CU_0_5_MG",
    "GYPSUM_BOARD": "GYPSUM",
    "PLASTER": "GYPSUM",
    "PLASTERBOARD": "GYPSUM_PLASTER_BOARD",
    "PARTICLEBOARD": "PARTICLE_BOARD",
    "OAK_WOOD": "OAK",
}


def _normalize(name: str) -> str:
    key = slug_id(name)
    return ALIASES.get(key, key)


def resolve_material(name: str) -> dict[str, Any]:
    key = _normalize(name)
    if key in MATERIALS:
        return dict(MATERIALS[key])
    # Case-insensitive display-name match.
    needle = name.strip().lower()
    for spec in MATERIALS.values():
        if spec["name"].lower() == needle:
            return dict(spec)
    available = ", ".join(sorted(MATERIALS))
    raise ValueError(f"Unknown material '{name}'. Use list_materials(). Known IDs: {available}")


def list_materials(category: str | None = None) -> list[dict[str, Any]]:
    wanted = None if not category else category.strip().lower().replace(" ", "_").replace("-", "_")
    if wanted == "wood":
        wanted_set = {"hardwood", "softwood", "misc_wood"}
    elif wanted:
        wanted_set = {wanted}
        if wanted not in MATERIAL_CATEGORIES and wanted != "engineering":
            raise ValueError(
                f"Unknown category '{category}'. Use: {', '.join(MATERIAL_CATEGORIES)}"
            )
    else:
        wanted_set = None
    rows = []
    for spec in MATERIALS.values():
        if wanted_set and spec["category"] not in wanted_set:
            continue
        rows.append(spec)
    rows.sort(key=lambda item: (MATERIAL_CATEGORIES.index(item["category"]), item["name"].lower()))
    return rows
