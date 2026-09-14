"""Patterns taken from Thunderhead PyroSim sample FDS files.

Counts are from 92 PyroSim-oriented cases under Samples/ (fds-master excluded).
"""

from __future__ import annotations

from typing import Any  # noqa: F401 — kept for callers that import Any via catalog

from materials import MATERIALS, resolve_material, list_materials as catalog_material_rows, MATERIAL_CATEGORIES
from fire_calcs import FUELS, FIRE_MODELING_GUIDANCE

# Patterns taken from Thunderhead PyroSim sample FDS files.

# Most common &SLCF QUANTITY values in the sample set.
SLICE_QUANTITIES = [
    "VELOCITY",
    "TEMPERATURE",
    "HRRPUV",
    "VISIBILITY",
    "PRESSURE",
    "DENSITY",
    "VOLUME FRACTION",
    "MASS FRACTION",
    "EXTINCTION COEFFICIENT",
    "SOOT DENSITY",
    "U-VELOCITY",
    "W-VELOCITY",
]

DEVICE_QUANTITIES = [
    "THERMOCOUPLE",
    "TEMPERATURE",
    "VELOCITY",
    "VISIBILITY",
    "EXTINCTION COEFFICIENT",
    "PRESSURE",
    "LAYER HEIGHT",
    "OPTICAL DENSITY",
    "PATH OBSCURATION",
    "CHAMBER OBSCURATION",
    "LINK TEMPERATURE",
    "VOLUME FRACTION",
    "RADIATIVE HEAT FLUX GAS",
    "NET HEAT FLUX",
    "RADIATIVE HEAT FLUX",
    "CONVECTIVE HEAT FLUX",
    "GAUGE HEAT FLUX",
    "WALL TEMPERATURE",
    "DUCT VOLUME FLOW",
    "DUCT MASS FLOW",
    "DUCT VELOCITY",
    "NODE PRESSURE",
]

# Cleary ionization I1 from atrium_with_fans.fds (PyroSim smoke detector).
CLEARY_I1 = {
    "id": "Cleary Ionization I1",
    "quantity": "CHAMBER OBSCURATION",
    "alpha_e": 2.5,
    "beta_e": -0.7,
    "alpha_c": 0.8,
    "beta_c": -0.9,
}

# FDS: VEL > 0 leaves the domain (exhaust); VEL < 0 enters (supply / jet).
FLOW_NOTE = (
    "FDS SURF VEL is velocity into the solid: negative VEL blows into the domain "
    "(supply/jet), positive VEL is exhaust."
)
