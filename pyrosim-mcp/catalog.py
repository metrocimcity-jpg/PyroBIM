"""Patterns taken from Thunderhead PyroSim sample FDS files.

Counts are from 92 PyroSim-oriented cases under Samples/ (fds-master excluded).
"""

from __future__ import annotations

from typing import Any

# PyroSim sample MATL blocks (Stairs.fds, atrium_with_fans.fds).
MATERIALS: dict[str, dict[str, Any]] = {
    "CONCRETE": {
        "description": "NBSIR/ATF-style concrete (atrium_with_fans.fds)",
        "conductivity": 1.8,
        "specific_heat": 1.04,
        "density": 2280.0,
        "emissivity": 0.9,
        "thickness": 0.3,
        "color": "GRAY 50",
    },
    "CONCRETE_LIGHT": {
        "description": "Generic example concrete (Stairs.fds)",
        "conductivity": 1.0,
        "specific_heat": 0.88,
        "density": 2200.0,
        "emissivity": 0.8,
        "thickness": 0.25,
        "color": "GRAY 35",
    },
    "STEEL": {
        "description": "Mild steel (typical handbook values)",
        "conductivity": 45.8,
        "specific_heat": 0.46,
        "density": 7850.0,
        "emissivity": 0.7,
        "thickness": 0.006,
        "color": "BLACK",
    },
    "GYPSUM": {
        "description": "Gypsum wallboard",
        "conductivity": 0.17,
        "specific_heat": 1.09,
        "density": 930.0,
        "emissivity": 0.9,
        "thickness": 0.016,
        "color": "WHITE",
    },
    "GLASS": {
        "description": "Window glazing",
        "conductivity": 0.8,
        "specific_heat": 0.84,
        "density": 2500.0,
        "emissivity": 0.9,
        "thickness": 0.006,
        "color": "CYAN",
    },
}

# Most common &SLCF QUANTITY values in the sample set.
SLICE_QUANTITIES = [
    "VELOCITY",
    "TEMPERATURE",
    "VISIBILITY",
    "PRESSURE",
    "DENSITY",
    "VOLUME FRACTION",
    "MASS FRACTION",
    "EXTINCTION COEFFICIENT",
    "SOOT DENSITY",
    "U-VELOCITY",
]

DEVICE_QUANTITIES = [
    "THERMOCOUPLE",
    "TEMPERATURE",
    "VELOCITY",
    "VISIBILITY",
    "EXTINCTION COEFFICIENT",
    "PRESSURE",
    "LAYER HEIGHT",
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
