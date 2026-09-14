"""NFPA 13 sprinkler orientations, K-factors, RTI classes, and FDS PROP mapping.

Smokeview only ships `sprinkler_pendent`, `sprinkler_upright`, and `nozzle`
glyphs (see FDS Verification/Detectors/objects_static.fds). Sidewall, concealed,
ESFR, and dry heads reuse those glyphs; throw direction is DEVC ORIENTATION.

References:
- NFPA 13 (Standard for the Installation of Sprinkler Systems): temperature
  ratings, RTI classes, K-factors, minimum operating pressure.
- NFPA 13D / 13R: residential pendent and sidewall.
- NFPA 15: open nozzles / water spray.
- PyroSim Fire Protection Systems tutorial (Generic Commercial Link = 68.33 °C):
  https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/fundamentals/5-fire-protection-systems/
- NIST bucket_test_1.fds (K-11 upright, FLOW_RATE in L/min).
"""

from __future__ import annotations

from typing import Any

GPM_TO_LPM = 3.785411784

# NFPA 13 temperature classification (typical glass-bulb ratings).
TEMPERATURE_RATINGS_C: dict[str, float] = {
    "ordinary": 68.33,       # 155 °F — PyroSim Generic Commercial Link
    "intermediate": 93.3,    # 200 °F
    "high": 141.0,           # 286 °F
    "extra_high": 182.0,     # 360 °F
    "very_extra_high": 227.0,
    "ultra_high": 260.0,
}

# NFPA 13 RTI classes, (m·s)^0.5
RTI_STANDARD = 148.0  # typical standard-response solder/bulb
RTI_SPECIAL = 80.0
RTI_QUICK = 50.0      # fast/QR; FDS heat-detector example
RTI_ESFR = 36.0
RTI_RESIDENTIAL = 28.0

# Common US K-factors (gpm/psi^0.5) → metric L/min/bar^0.5 ≈ K*14.0
K_FACTORS_US: dict[str, float] = {
    "k14": 1.4,
    "k28": 2.8,
    "k42": 4.2,
    "k56": 5.6,
    "k80": 8.0,
    "k112": 11.2,
    "k140": 14.0,
    "k168": 16.8,
    "k196": 19.6,
    "k224": 22.4,
    "k252": 25.2,
    "k363": 36.3,
}


def flow_lpm(k_us: float, pressure_psi: float) -> float:
    """Q = K * sqrt(P) (gpm), converted to L/min for FDS FLOW_RATE."""
    if k_us <= 0 or pressure_psi < 0:
        raise ValueError("k_us must be positive and pressure_psi >= 0")
    return k_us * (pressure_psi ** 0.5) * GPM_TO_LPM


def _type(
    name: str,
    *,
    smokeview_id: str,
    orientation: tuple[float, float, float],
    k_us: float,
    pressure_psi: float,
    rti: float,
    spray_angle: tuple[float, float],
    offset: float,
    particle_velocity: float,
    open_head: bool = False,
    nfpa: str,
    description: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "smokeview_id": smokeview_id,
        "orientation": list(orientation),
        "k_us": k_us,
        "pressure_psi": pressure_psi,
        "flow_lpm": round(flow_lpm(k_us, pressure_psi), 2),
        "rti": rti,
        "spray_angle": list(spray_angle),
        "offset": offset,
        "particle_velocity": particle_velocity,
        "open_head": open_head,
        "activation_temperature": TEMPERATURE_RATINGS_C["ordinary"],
        "nfpa": nfpa,
        "description": description,
    }


# Geometry / listing types used in NFPA 13, 13D, 13R, and 15.
SPRINKLER_TYPES: dict[str, dict[str, Any]] = {
    "pendent": _type(
        "pendent",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 standard spray pendent",
        description="Ceiling-mounted pendent, spray downward. Default K-5.6 at 7 psi.",
    ),
    "upright": _type(
        "upright",
        smokeview_id="sprinkler_upright",
        orientation=(0.0, 0.0, 1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 standard spray upright",
        description="Upright deflector (typically on exposed pipe). NIST bucket_test glyph.",
    ),
    "sidewall": _type(
        "sidewall",
        smokeview_id="sprinkler_pendent",
        orientation=(1.0, 0.0, 0.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(40.0, 90.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 horizontal sidewall",
        description="Horizontal sidewall. Set orientation to the throw direction (default +X).",
    ),
    "horizontal_sidewall": _type(
        "horizontal_sidewall",
        smokeview_id="sprinkler_pendent",
        orientation=(1.0, 0.0, 0.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(40.0, 90.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 horizontal sidewall",
        description="Alias of sidewall.",
    ),
    "vertical_sidewall": _type(
        "vertical_sidewall",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 90.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 vertical sidewall",
        description="Vertical sidewall (deflector down along a wall).",
    ),
    "recessed_pendent": _type(
        "recessed_pendent",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.05,
        particle_velocity=10.0,
        nfpa="NFPA 13 recessed pendent",
        description="Pendent in a recessed escutcheon; shorter link OFFSET.",
    ),
    "flush_pendent": _type(
        "flush_pendent",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.02,
        particle_velocity=10.0,
        nfpa="NFPA 13 flush pendent",
        description="Flush pendent; link close to the ceiling.",
    ),
    "concealed_pendent": _type(
        "concealed_pendent",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.02,
        particle_velocity=10.0,
        nfpa="NFPA 13 concealed pendent",
        description="Concealed pendent (cover plate). Thermal response is still a link model.",
    ),
    "dry_pendent": _type(
        "dry_pendent",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 dry pendent",
        description="Dry pendent (unheated space below a wet system). Same spray as pendent.",
    ),
    "dry_upright": _type(
        "dry_upright",
        smokeview_id="sprinkler_upright",
        orientation=(0.0, 0.0, 1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 dry upright",
        description="Dry upright.",
    ),
    "dry_sidewall": _type(
        "dry_sidewall",
        smokeview_id="sprinkler_pendent",
        orientation=(1.0, 0.0, 0.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(40.0, 90.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 dry sidewall",
        description="Dry horizontal sidewall. Set orientation to throw direction.",
    ),
    "conventional": _type(
        "conventional",
        smokeview_id="sprinkler_upright",
        orientation=(0.0, 0.0, 1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(80.0, 100.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 old-style / conventional",
        description="Old-style/conventional: spray both above and below the deflector.",
    ),
    "quick_response_pendent": _type(
        "quick_response_pendent",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_QUICK,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 QR pendent (RTI ≤ 50)",
        description="Quick-response pendent. PyroSim Generic Commercial uses 68.33 °C.",
    ),
    "quick_response_upright": _type(
        "quick_response_upright",
        smokeview_id="sprinkler_upright",
        orientation=(0.0, 0.0, 1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_QUICK,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 QR upright",
        description="Quick-response upright.",
    ),
    "quick_response_sidewall": _type(
        "quick_response_sidewall",
        smokeview_id="sprinkler_pendent",
        orientation=(1.0, 0.0, 0.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_QUICK,
        spray_angle=(40.0, 90.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 QR horizontal sidewall",
        description="Quick-response sidewall.",
    ),
    "residential_pendent": _type(
        "residential_pendent",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=4.2,
        pressure_psi=7.0,
        rti=RTI_RESIDENTIAL,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13D / 13R residential pendent",
        description="Residential pendent (typically K-4.2). Listed spray is higher-wall.",
    ),
    "residential_sidewall": _type(
        "residential_sidewall",
        smokeview_id="sprinkler_pendent",
        orientation=(1.0, 0.0, 0.0),
        k_us=4.2,
        pressure_psi=7.0,
        rti=RTI_RESIDENTIAL,
        spray_angle=(40.0, 90.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13D / 13R residential sidewall",
        description="Residential horizontal sidewall.",
    ),
    "esfr_pendent": _type(
        "esfr_pendent",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=14.0,
        pressure_psi=50.0,
        rti=RTI_ESFR,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=20.0,
        nfpa="NFPA 13 ESFR pendent",
        description="Early Suppression Fast Response pendent. Default K-14 at 50 psi; listings vary (K-14 to K-25.2).",
    ),
    "esfr_upright": _type(
        "esfr_upright",
        smokeview_id="sprinkler_upright",
        orientation=(0.0, 0.0, 1.0),
        k_us=14.0,
        pressure_psi=50.0,
        rti=RTI_ESFR,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=20.0,
        nfpa="NFPA 13 ESFR upright",
        description="ESFR upright (less common than pendent).",
    ),
    "cmsa_pendent": _type(
        "cmsa_pendent",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=11.2,
        pressure_psi=25.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=15.0,
        nfpa="NFPA 13 CMSA pendent",
        description="Control Mode Specific Application (large-drop / CMSA). Default K-11.2.",
    ),
    "cmsa_upright": _type(
        "cmsa_upright",
        smokeview_id="sprinkler_upright",
        orientation=(0.0, 0.0, 1.0),
        k_us=11.2,
        pressure_psi=25.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=15.0,
        nfpa="NFPA 13 CMSA upright",
        description="CMSA upright. NIST K-11 bucket_test uses 180 L/min upright.",
    ),
    "in_rack": _type(
        "in_rack",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=8.0,
        pressure_psi=15.0,
        rti=RTI_QUICK,
        spray_angle=(30.0, 80.0),
        offset=0.08,
        particle_velocity=10.0,
        nfpa="NFPA 13 in-rack / intermediate level",
        description="In-rack / intermediate-level sprinkler (storage).",
    ),
    "window": _type(
        "window",
        smokeview_id="sprinkler_pendent",
        orientation=(1.0, 0.0, 0.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_QUICK,
        spray_angle=(50.0, 90.0),
        offset=0.05,
        particle_velocity=10.0,
        nfpa="NFPA 13 window sprinkler",
        description="Window/glazing sprinkler; aim ORIENTATION at the glass.",
    ),
    "attic": _type(
        "attic",
        smokeview_id="sprinkler_pendent",
        orientation=(1.0, 0.0, 0.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_QUICK,
        spray_angle=(40.0, 90.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="NFPA 13 specific-application attic",
        description="Attic / sloped-ceiling specific-application sprinkler.",
    ),
    "institutional": _type(
        "institutional",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_QUICK,
        spray_angle=(30.0, 80.0),
        offset=0.05,
        particle_velocity=10.0,
        nfpa="NFPA 13 institutional pendent",
        description="Institutional/vandal-resistant pendent.",
    ),
    "open": _type(
        "open",
        smokeview_id="nozzle",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(0.0, 90.0),
        offset=0.10,
        particle_velocity=10.0,
        open_head=True,
        nfpa="NFPA 13 / 15 open sprinkler (deluge)",
        description="Open orifice — no fusible link. Activate with TIME SETPOINT=0 or a CTRL.",
    ),
    "deluge": _type(
        "deluge",
        smokeview_id="nozzle",
        orientation=(0.0, 0.0, -1.0),
        k_us=8.0,
        pressure_psi=15.0,
        rti=RTI_STANDARD,
        spray_angle=(0.0, 90.0),
        offset=0.10,
        particle_velocity=10.0,
        open_head=True,
        nfpa="NFPA 13 / 15 deluge nozzle",
        description="Deluge/open head. Pair with a detection CTRL to open the system.",
    ),
    "nozzle": _type(
        "nozzle",
        smokeview_id="nozzle",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(0.0, 35.0),
        offset=0.10,
        particle_velocity=10.0,
        open_head=True,
        nfpa="NFPA 15 water-spray nozzle",
        description="Directional water-spray nozzle (narrow cone). Set orientation to aim.",
    ),
    "water_spray": _type(
        "water_spray",
        smokeview_id="nozzle",
        orientation=(1.0, 0.0, 0.0),
        k_us=8.0,
        pressure_psi=20.0,
        rti=RTI_STANDARD,
        spray_angle=(0.0, 60.0),
        offset=0.10,
        particle_velocity=15.0,
        open_head=True,
        nfpa="NFPA 15 water spray",
        description="NFPA 15 directional water spray. Default throw +X.",
    ),
    "generic_commercial": _type(
        "generic_commercial",
        smokeview_id="sprinkler_pendent",
        orientation=(0.0, 0.0, -1.0),
        k_us=5.6,
        pressure_psi=7.0,
        rti=RTI_STANDARD,
        spray_angle=(30.0, 80.0),
        offset=0.10,
        particle_velocity=10.0,
        nfpa="PyroSim Generic Commercial Link (example only)",
        description="PyroSim tutorial default: 68.33 °C pendent. Not a listed product.",
    ),
}

ALIASES = {
    "pendant": "pendent",
    "pendent_sprinkler": "pendent",
    "upright_sprinkler": "upright",
    "side": "sidewall",
    "hsw": "sidewall",
    "horizontal": "sidewall",
    "qr": "quick_response_pendent",
    "qr_pendent": "quick_response_pendent",
    "qr_upright": "quick_response_upright",
    "qr_sidewall": "quick_response_sidewall",
    "fast_response": "quick_response_pendent",
    "esfr": "esfr_pendent",
    "cmsa": "cmsa_upright",
    "k11": "cmsa_upright",
    "large_drop": "cmsa_upright",
    "residential": "residential_pendent",
    "13d": "residential_pendent",
    "13r": "residential_pendent",
    "old_style": "conventional",
    "old-style": "conventional",
    "in-rack": "in_rack",
    "intermediate": "in_rack",
    "concealed": "concealed_pendent",
    "flush": "flush_pendent",
    "recessed": "recessed_pendent",
    "dry": "dry_pendent",
    "open_sprinkler": "open",
    "nfpa15": "water_spray",
}


def resolve_sprinkler(name: str) -> dict[str, Any]:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    key = ALIASES.get(key, key)
    if key not in SPRINKLER_TYPES:
        raise ValueError(
            f"Unknown sprinkler type '{name}'. Available: {', '.join(SPRINKLER_TYPES)}"
        )
    return dict(SPRINKLER_TYPES[key])


def resolve_temperature_rating(name_or_c: str | float | None) -> float | None:
    if name_or_c is None:
        return None
    if isinstance(name_or_c, (int, float)):
        return float(name_or_c)
    key = str(name_or_c).strip().lower().replace(" ", "_")
    if key in TEMPERATURE_RATINGS_C:
        return TEMPERATURE_RATINGS_C[key]
    return float(name_or_c)


def list_sprinkler_summaries() -> list[str]:
    lines = []
    for spec in SPRINKLER_TYPES.values():
        extra = " OPEN" if spec["open_head"] else ""
        lines.append(
            f"- {spec['name']}{extra}: {spec['nfpa']}. "
            f"K={spec['k_us']}, P={spec['pressure_psi']} psi → {spec['flow_lpm']} L/min, "
            f"RTI={spec['rti']}, T={spec['activation_temperature']}°C, "
            f"SMOKEVIEW_ID={spec['smokeview_id']}, ORIENTATION={spec['orientation']}. "
            f"{spec['description']}"
        )
    return lines
