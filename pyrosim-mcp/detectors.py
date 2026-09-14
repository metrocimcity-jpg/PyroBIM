"""NFPA 72 / FDS detector presets: smoke, heat, gas, beam, aspiration, flame.

FDS models (User Guide, Verification/Detectors, NIST_Smoke_Alarms):
- Smoke: QUANTITY='CHAMBER OBSCURATION' (Cleary α/β or Heskestad LENGTH)
- Heat: QUANTITY='LINK TEMPERATURE' (RTI + ACTIVATION_TEMPERATURE)
- Beam: QUANTITY='PATH OBSCURATION' on a line XB
- Aspiration: QUANTITY='ASPIRATION' plus sampling DEVCs with FLOWRATE/DELAY
- Gas: QUANTITY='VOLUME FRACTION' + SPEC_ID (simple-chemistry products)

References:
- NFPA 72 National Fire Alarm and Signaling Code (spot heat ratings, smoke)
- NFPA 720 / UL 2034 CO alarms (~70 ppm)
- FDS Verification/Detectors/smoke_detector.fds, beam_detector.fds, aspiration_detector.fds
- NIST Smoke Alarms Validation (Dunes 2000)
- PyroSim atrium_with_fans.fds Cleary I1
"""

from __future__ import annotations

from typing import Any

# NFPA 72 Table 17.6.2.1 temperature classification (spot heat detectors).
HEAT_RATINGS_C: dict[str, float] = {
    "low": 49.0,             # ~120 °F
    "ordinary": 57.2,        # 135 °F
    "intermediate": 79.4,    # 175 °F
    "high": 121.1,           # 250 °F
    "extra_high": 162.8,     # 325 °F
    "very_extra_high": 204.4,  # 400 °F
    "ultra_high": 260.0,     # 500 °F
    "fds_example": 74.0,     # historic FDS heat-detector example
}

# Spot heat RTI (m·s)^0.5. Rate-compensation heads are faster than standard.
HEAT_RTI_FAST = 50.0
HEAT_RTI_STANDARD = 148.0
HEAT_RTI_RATE_COMP = 25.0

# Heskestad / UL 217-style obscuration thresholds (%/m).
OBSCURATION_ION = 3.24
OBSCURATION_PHOTO = 6.6
HESKESTAD_LENGTH_M = 1.8

# Cleary ionization / photoelectric (FDS User Guide).
CLEARY: dict[str, dict[str, float]] = {
    "I1": {"alpha_e": 2.5, "beta_e": -0.7, "alpha_c": 0.8, "beta_c": -0.9},
    "I2": {"alpha_e": 1.8, "beta_e": -1.1, "alpha_c": 1.0, "beta_c": -0.8},
    "P1": {"alpha_e": 1.8, "beta_e": -1.0, "alpha_c": 1.0, "beta_c": -0.8},
    "P2": {"alpha_e": 1.8, "beta_e": -0.8, "alpha_c": 0.8, "beta_c": -0.8},
}

# Fitted NIST Dunes 2000 smoke-alarm Validation (same α/β; different SETPOINT).
NIST_CLEARY = {"alpha_e": 0.015, "beta_e": -1.9, "alpha_c": 0.15, "beta_c": -1.4}


def _smoke(
    name: str,
    *,
    model: str,
    description: str,
    nfpa: str,
    activation_obscuration: float | None = None,
    length: float | None = None,
    cleary: dict[str, float] | None = None,
    smokeview_id: str = "smoke_detector",
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "smoke",
        "model": model,
        "quantity": "CHAMBER OBSCURATION",
        "activation_obscuration": activation_obscuration,
        "length": length,
        "cleary": dict(cleary) if cleary else None,
        "smokeview_id": smokeview_id,
        "nfpa": nfpa,
        "description": description,
    }


SMOKE_TYPES: dict[str, dict[str, Any]] = {
    "ionization": _smoke(
        "ionization",
        model="cleary_i1",
        activation_obscuration=OBSCURATION_ION,
        cleary=CLEARY["I1"],
        nfpa="NFPA 72 ionization smoke (Cleary I1)",
        description="PyroSim atrium_with_fans / FDS Cleary ionization I1. Typical 3.24 %/m.",
    ),
    "photoelectric": _smoke(
        "photoelectric",
        model="cleary_p1",
        activation_obscuration=OBSCURATION_PHOTO,
        cleary=CLEARY["P1"],
        nfpa="NFPA 72 photoelectric smoke (Cleary P1)",
        description="Cleary photoelectric P1. Typical 6.6 %/m (NIST photo alarms).",
    ),
    "cleary_i1": _smoke(
        "cleary_i1",
        model="cleary_i1",
        activation_obscuration=OBSCURATION_ION,
        cleary=CLEARY["I1"],
        nfpa="FDS Cleary ionization I1",
        description="ALPHA_E=2.5, BETA_E=-0.7, ALPHA_C=0.8, BETA_C=-0.9.",
    ),
    "cleary_i2": _smoke(
        "cleary_i2",
        model="cleary_i2",
        activation_obscuration=OBSCURATION_ION,
        cleary=CLEARY["I2"],
        nfpa="FDS Cleary ionization I2",
        description="Second Cleary ionization parameter set.",
    ),
    "cleary_p1": _smoke(
        "cleary_p1",
        model="cleary_p1",
        activation_obscuration=OBSCURATION_PHOTO,
        cleary=CLEARY["P1"],
        nfpa="FDS Cleary photoelectric P1",
        description="First Cleary photoelectric parameter set.",
    ),
    "cleary_p2": _smoke(
        "cleary_p2",
        model="cleary_p2",
        activation_obscuration=OBSCURATION_PHOTO,
        cleary=CLEARY["P2"],
        nfpa="FDS Cleary photoelectric P2",
        description="Second Cleary photoelectric parameter set.",
    ),
    "heskestad": _smoke(
        "heskestad",
        model="heskestad",
        activation_obscuration=OBSCURATION_ION,
        length=HESKESTAD_LENGTH_M,
        nfpa="Heskestad smoke detector (FDS Verification)",
        description="LENGTH=1.8 m, ACTIVATION_OBSCURATION=3.24 %/m (smoke_detector.fds).",
    ),
    "nist_ionization": _smoke(
        "nist_ionization",
        model="nist_fitted",
        activation_obscuration=4.3,
        cleary=NIST_CLEARY,
        nfpa="NIST Smoke Alarms Validation (ion)",
        description="Dunes 2000 fitted ionization (ACTIVATION_OBSCURATION=4.3 %/m).",
    ),
    "nist_photoelectric": _smoke(
        "nist_photoelectric",
        model="nist_fitted",
        activation_obscuration=6.6,
        cleary=NIST_CLEARY,
        nfpa="NIST Smoke Alarms Validation (photo)",
        description="Dunes 2000 fitted photoelectric (ACTIVATION_OBSCURATION=6.6 %/m).",
    ),
}

SMOKE_ALIASES = {
    "ion": "ionization",
    "ionic": "ionization",
    "i1": "cleary_i1",
    "i2": "cleary_i2",
    "photo": "photoelectric",
    "optical": "photoelectric",
    "p1": "cleary_p1",
    "p2": "cleary_p2",
    "smoke": "ionization",
    "smoke_alarm": "ionization",
    "hes": "heskestad",
    "dunes": "nist_ionization",
}


def _heat(
    name: str,
    *,
    activation_temperature: float,
    rti: float,
    description: str,
    nfpa: str,
    c_factor: float = 0.0,
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "heat",
        "quantity": "LINK TEMPERATURE",
        "activation_temperature": activation_temperature,
        "rti": rti,
        "c_factor": c_factor,
        "smokeview_id": "heat_detector",
        "nfpa": nfpa,
        "description": description,
    }


HEAT_TYPES: dict[str, dict[str, Any]] = {
    "ordinary": _heat(
        "ordinary",
        activation_temperature=HEAT_RATINGS_C["ordinary"],
        rti=HEAT_RTI_FAST,
        nfpa="NFPA 72 ordinary spot heat (135 °F / 57 °C)",
        description="Fixed-temperature spot heat detector. RTI=50 (fast/rate-compensation class).",
    ),
    "intermediate": _heat(
        "intermediate",
        activation_temperature=HEAT_RATINGS_C["intermediate"],
        rti=HEAT_RTI_FAST,
        nfpa="NFPA 72 intermediate (175 °F / 79 °C)",
        description="Intermediate-temperature spot heat detector.",
    ),
    "high": _heat(
        "high",
        activation_temperature=HEAT_RATINGS_C["high"],
        rti=HEAT_RTI_STANDARD,
        nfpa="NFPA 72 high (250 °F / 121 °C)",
        description="High-temperature spot heat detector.",
    ),
    "extra_high": _heat(
        "extra_high",
        activation_temperature=HEAT_RATINGS_C["extra_high"],
        rti=HEAT_RTI_STANDARD,
        nfpa="NFPA 72 extra high (325 °F / 163 °C)",
        description="Extra-high temperature spot heat detector.",
    ),
    "rate_compensation": _heat(
        "rate_compensation",
        activation_temperature=HEAT_RATINGS_C["ordinary"],
        rti=HEAT_RTI_RATE_COMP,
        nfpa="NFPA 72 rate-compensation heat",
        description="Faster RTI (25) at ordinary 57 °C. FDS still uses the link model, not a true RoR algorithm.",
    ),
    "rate_of_rise": _heat(
        "rate_of_rise",
        activation_temperature=HEAT_RATINGS_C["ordinary"],
        rti=HEAT_RTI_FAST,
        c_factor=0.0,
        nfpa="NFPA 72 rate-of-rise (approximated)",
        description="FDS has no native °C/min trip. Uses a fast RTI link at 57 °C as an engineering stand-in.",
    ),
    "combination": _heat(
        "combination",
        activation_temperature=HEAT_RATINGS_C["ordinary"],
        rti=HEAT_RTI_FAST,
        nfpa="NFPA 72 combination fixed + RoR (approximated)",
        description="Single LINK TEMPERATURE head at 57 °C, RTI=50. Pair with a thermocouple if you need a separate RoR log.",
    ),
    "fds_example": _heat(
        "fds_example",
        activation_temperature=74.0,
        rti=HEAT_RTI_FAST,
        nfpa="FDS example heat detector (74 °C, RTI=50)",
        description="Historic FDS/PyroSim default (not an NFPA 72 listing).",
    ),
}

HEAT_ALIASES = {
    "heat": "ordinary",
    "spot": "ordinary",
    "fixed": "ordinary",
    "fixed_temperature": "ordinary",
    "135f": "ordinary",
    "175f": "intermediate",
    "250f": "high",
    "ror": "rate_of_rise",
    "rate-of-rise": "rate_of_rise",
    "rc": "rate_compensation",
}


def _gas(
    name: str,
    *,
    spec_id: str,
    setpoint: float,
    unit: str,
    description: str,
    nfpa: str,
    falling: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "gas",
        "quantity": "VOLUME FRACTION",
        "spec_id": spec_id,
        "setpoint": setpoint,
        "unit": unit,
        "falling": falling,
        "smokeview_id": "sensor",
        "nfpa": nfpa,
        "description": description,
    }


# VOLUME FRACTION setpoints are mole fractions (ppm * 1e-6).
GAS_TYPES: dict[str, dict[str, Any]] = {
    "co": _gas(
        "co",
        spec_id="CARBON MONOXIDE",
        setpoint=70e-6,
        unit="70 ppm",
        nfpa="UL 2034 / NFPA 720 CO alarm (~70 ppm)",
        description="CO volume fraction. Simple chemistry tracks CO when CO_YIELD > 0.",
    ),
    "co_low": _gas(
        "co_low",
        spec_id="CARBON MONOXIDE",
        setpoint=30e-6,
        unit="30 ppm",
        nfpa="Low-level CO warning (30 ppm)",
        description="Early CO warning. Not a listed alarm threshold.",
    ),
    "co2": _gas(
        "co2",
        spec_id="CARBON DIOXIDE",
        setpoint=0.005,
        unit="0.5 % vol",
        nfpa="Engineering CO2 monitor (0.5 % vol)",
        description="Combustion product. Not a listed fire-alarm device.",
    ),
    "oxygen": _gas(
        "oxygen",
        spec_id="OXYGEN",
        setpoint=0.195,
        unit="19.5 % vol",
        falling=True,
        nfpa="OSHA O2 deficiency (19.5 % vol)",
        description="Measurement only: FDS SETPOINT trips on rising quantity. Log O2; use a CTRL for a falling alarm.",
    ),
    "fuel": _gas(
        "fuel",
        spec_id="FUEL",
        setpoint=0.005,
        unit="0.5 % vol (~10 % LEL methane-class)",
        nfpa="Flammable-gas 10 % LEL (order-of-magnitude)",
        description="Unburned fuel volume fraction. Tune setpoint to the fuel LEL.",
    ),
    "methane": _gas(
        "methane",
        spec_id="METHANE",
        setpoint=0.005,
        unit="0.5 % vol (10 % of 5 % LEL)",
        nfpa="Methane 10 % LEL",
        description="Requires METHANE as fuel or an explicit &SPEC ID='METHANE'.",
    ),
    "propane": _gas(
        "propane",
        spec_id="PROPANE",
        setpoint=0.0021,
        unit="0.21 % vol (10 % of 2.1 % LEL)",
        nfpa="Propane 10 % LEL",
        description="Requires PROPANE fuel or &SPEC ID='PROPANE'.",
    ),
    "hcn": _gas(
        "hcn",
        spec_id="HYDROGEN CYANIDE",
        setpoint=10e-6,
        unit="10 ppm",
        nfpa="HCN toxicity monitor (engineering)",
        description="Needs add_reaction(hcn_yield=...).",
    ),
    "hcl": _gas(
        "hcl",
        spec_id="HYDROGEN CHLORIDE",
        setpoint=5e-6,
        unit="5 ppm",
        nfpa="HCl monitor (engineering)",
        description="Needs add_reaction(hcl_yield=...).",
    ),
    "soot": _gas(
        "soot",
        spec_id="SOOT",
        setpoint=1e-5,
        unit="10 ppm mass-fraction order",
        nfpa="Soot / smoke species probe",
        description="Uses VOLUME FRACTION of SOOT. Prefer a smoke detector for alarms.",
    ),
}

GAS_ALIASES = {
    "carbon_monoxide": "co",
    "carbon monoxide": "co",
    "co_alarm": "co",
    "carbon_dioxide": "co2",
    "carbon dioxide": "co2",
    "o2": "oxygen",
    "o2_deficiency": "oxygen",
    "lel": "fuel",
    "combustible": "fuel",
    "ch4": "methane",
    "c3h8": "propane",
    "hydrogen_cyanide": "hcn",
    "hydrogen_chloride": "hcl",
    "smoke_gas": "soot",
}

OTHER_TYPES: dict[str, dict[str, Any]] = {
    "beam": {
        "name": "beam",
        "kind": "beam",
        "quantity": "PATH OBSCURATION",
        "setpoint": 15.0,
        "nfpa": "NFPA 72 projected-beam smoke (engineering 15 % obscuration)",
        "description": "Line-of-sight PATH OBSCURATION (beam_detector.fds). Pass start and end XYZ.",
    },
    "aspiration": {
        "name": "aspiration",
        "kind": "aspiration",
        "quantity": "ASPIRATION",
        "flowrate": 0.3,
        "nfpa": "Aspirating smoke detector (VESDA-style sampling)",
        "description": "FDS Verification aspiration_detector.fds: chamber ASPIRATION + sampling DEVCs.",
    },
    "flame": {
        "name": "flame",
        "kind": "flame",
        "quantity": "RADIATIVE HEAT FLUX GAS",
        "setpoint": 5.0,
        "smokeview_id": "target",
        "nfpa": "IR/UV flame detector analogue",
        "description": "Gas-phase radiative flux (kW/m²). Aim ORIENTATION at the fire. Not a listed flame detector.",
    },
    "visibility": {
        "name": "visibility",
        "kind": "tenability",
        "quantity": "VISIBILITY",
        "setpoint": 10.0,
        "smokeview_id": "smokesensor",
        "nfpa": "Tenability visibility (m)",
        "description": "Visibility probe. SETPOINT in metres (e.g. 10 m SFPE tenability).",
    },
    "optical_density": {
        "name": "optical_density",
        "kind": "tenability",
        "quantity": "OPTICAL DENSITY",
        "smokeview_id": "sensor",
        "nfpa": "NIST Smoke Alarms optical-density probe",
        "description": "QUANTITY='OPTICAL DENSITY' as in Dunes 2000 Validation.",
    },
    "layer_height": {
        "name": "layer_height",
        "kind": "tenability",
        "quantity": "LAYER HEIGHT",
        "nfpa": "Hot-layer height",
        "description": "Needs a vertical XB column, not a single XYZ.",
    },
    "thermocouple": {
        "name": "thermocouple",
        "kind": "sensor",
        "quantity": "THERMOCOUPLE",
        "smokeview_id": "thermocouple",
        "nfpa": "Bare thermocouple",
        "description": "Gas thermocouple (not a listed heat detector).",
    },
}

OTHER_ALIASES = {
    "beam_smoke": "beam",
    "projected_beam": "beam",
    "vesda": "aspiration",
    "asd": "aspiration",
    "aspirating": "aspiration",
    "ir_flame": "flame",
    "uv_flame": "flame",
    "od": "optical_density",
    "tc": "thermocouple",
}


def resolve_smoke(name: str) -> dict[str, Any]:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    key = SMOKE_ALIASES.get(key, key)
    if key not in SMOKE_TYPES:
        raise ValueError(
            f"Unknown smoke detector '{name}'. Available: {', '.join(SMOKE_TYPES)}"
        )
    return dict(SMOKE_TYPES[key])


def resolve_heat(name: str) -> dict[str, Any]:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    key = HEAT_ALIASES.get(key, key)
    if key not in HEAT_TYPES:
        raise ValueError(
            f"Unknown heat detector '{name}'. Available: {', '.join(HEAT_TYPES)}"
        )
    return dict(HEAT_TYPES[key])


def resolve_gas(name: str) -> dict[str, Any]:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    key = GAS_ALIASES.get(key, key)
    if key not in GAS_TYPES:
        raise ValueError(
            f"Unknown gas detector '{name}'. Available: {', '.join(GAS_TYPES)}"
        )
    return dict(GAS_TYPES[key])


def resolve_other(name: str) -> dict[str, Any]:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    key = OTHER_ALIASES.get(key, key)
    if key not in OTHER_TYPES:
        raise ValueError(
            f"Unknown detector '{name}'. Try list_detectors()."
        )
    return dict(OTHER_TYPES[key])


def list_detector_summaries() -> list[str]:
    lines = ["Smoke (CHAMBER OBSCURATION):"]
    for spec in SMOKE_TYPES.values():
        extra = (
            f" {spec['activation_obscuration']} %/m"
            if spec.get("activation_obscuration") is not None
            else ""
        )
        lines.append(f"- {spec['name']}{extra}: {spec['nfpa']}. {spec['description']}")
    lines.append("Heat (LINK TEMPERATURE):")
    for spec in HEAT_TYPES.values():
        lines.append(
            f"- {spec['name']}: {spec['nfpa']}. T={spec['activation_temperature']}°C, "
            f"RTI={spec['rti']}. {spec['description']}"
        )
    lines.append("Gas (VOLUME FRACTION):")
    for spec in GAS_TYPES.values():
        fall = " falling" if spec["falling"] else ""
        lines.append(
            f"- {spec['name']}{fall}: {spec['nfpa']}. SPEC_ID='{spec['spec_id']}', "
            f"SETPOINT={spec['setpoint']} ({spec['unit']}). {spec['description']}"
        )
    lines.append("Other:")
    for spec in OTHER_TYPES.values():
        lines.append(f"- {spec['name']}: {spec['nfpa']}. {spec['description']}")
    return lines
