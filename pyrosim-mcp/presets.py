"""Fire presets and t-squared HRR ramp generation."""

from __future__ import annotations

from typing import Any

# NFPA t-squared growth coefficients (kW/s²)
GROWTH_ALPHA: dict[str, float] = {
    "slow": 0.0029,
    "medium": 0.0117,
    "fast": 0.0469,
    "ultra-fast": 0.1876,
    "ultra_fast": 0.1876,
    "ultrafast": 0.1876,
}

PRESETS: dict[str, dict[str, Any]] = {
    "couch": {
        "name": "couch",
        "description": "Upholstered furniture, polyurethane foam (fast/ultra-fast)",
        "growth_class": "ultra-fast",
        "peak_hrr": 2500.0,
        "area": 1.75,
        "hrrpua": 1750.0,
        "soot_yield": 0.10,
        "co_yield": 0.05,
        "fuel": "POLYURETHANE",
        "color": "RED",
        "height": 0.5,
        "lx": 1.75,
        "ly": 1.0,
    },
    "cigarette": {
        "name": "cigarette",
        "description": "Smoldering cigarette / upholstery ignition source",
        "growth_class": "slow",
        "peak_hrr": 20.0,
        "flaming_hrr": 35.0,
        "area": 0.3,
        "flaming_area": 0.4,
        "hrrpua": 20.0,
        "soot_yield": 0.08,
        "co_yield": 0.10,
        "fuel": "POLYURETHANE",
        "color": "MAROON",
        "height": 0.05,
        "lx": 0.55,
        "ly": 0.55,
        "smoldering": True,
    },
    "car": {
        "name": "car",
        "description": "Single passenger vehicle, interior + engine bay",
        "growth_class": "fast",
        "peak_hrr": 6000.0,
        "area": 5.0,
        "hrrpua": 1250.0,
        "soot_yield": 0.075,
        "co_yield": 0.04,
        "fuel": "N-HEPTANE",
        "color": "ORANGE",
        "height": 1.2,
        "lx": 4.0,
        "ly": 1.25,
    },
    "wastebasket": {
        "name": "wastebasket",
        "description": "Small ultra-fast wastebasket ignition test case",
        "growth_class": "ultra-fast",
        "peak_hrr": 100.0,
        "area": 0.15,
        "hrrpua": 650.0,
        "soot_yield": 0.10,
        "co_yield": 0.05,
        "fuel": "POLYURETHANE",
        "color": "RED",
        "height": 0.3,
        "lx": 0.4,
        "ly": 0.375,
    },
}

ALIASES = {
    "couch_fire": "couch",
    "sofa": "couch",
    "cigarette_fire": "cigarette",
    "smolder": "cigarette",
    "smoldering": "cigarette",
    "car_fire": "car",
    "vehicle": "car",
    "waste": "wastebasket",
    "trash": "wastebasket",
    "wastebasket_fire": "wastebasket",
}


def normalize_growth_class(growth_class: str) -> str:
    key = growth_class.strip().lower().replace(" ", "-")
    if key not in GROWTH_ALPHA:
        known = "slow, medium, fast, ultra-fast"
        raise ValueError(f"Unknown growth class '{growth_class}'. Use: {known}")
    return key


def resolve_preset(name: str) -> dict[str, Any]:
    key = name.strip().lower().replace(" ", "_")
    key = ALIASES.get(key, key)
    if key not in PRESETS:
        available = ", ".join(PRESETS)
        raise ValueError(f"Unknown preset '{name}'. Available: {available}")
    return PRESETS[key]


def build_ramp(
    growth_class: str,
    peak_hrr: float,
    hold_s: float | None = None,
) -> list[tuple[float, float]]:
    """t-squared ramp as (t, f) pairs. f is the fraction of peak HRR."""
    if peak_hrr <= 0:
        raise ValueError("peak_hrr must be positive")
    key = normalize_growth_class(growth_class)
    alpha = GROWTH_ALPHA[key]
    t_peak = (peak_hrr / alpha) ** 0.5
    fractions = (0.0, 0.25, 0.5, 0.75, 1.0)
    points: list[tuple[float, float]] = []
    for fraction in fractions:
        time = (fraction * peak_hrr / alpha) ** 0.5
        points.append((round(time, 1), fraction))
    hold = hold_s if hold_s is not None else max(t_peak * 2.0, t_peak + 300.0)
    if hold > t_peak + 1e-6:
        points.append((round(hold, 1), 1.0))
    return points


def build_cigarette_ramp(
    flaming_after: float | None = None,
    smolder_hrr: float = 20.0,
    flaming_hrr: float = 35.0,
    hold_s: float = 600.0,
) -> list[tuple[float, float]]:
    """Two-stage smolder plateau, optional fast flaming transition.

    Returned F values are relative to flaming_hrr when flaming_after is set,
    otherwise relative to smolder_hrr.
    """
    if flaming_after is None:
        return [
            (0.0, 0.0),
            (60.0, 1.0),
            (max(hold_s, 600.0), 1.0),
        ]
    if flaming_after < 0:
        raise ValueError("flaming_after must be >= 0")
    if flaming_hrr <= 0:
        raise ValueError("flaming_hrr must be positive")
    smolder_f = min(1.0, smolder_hrr / flaming_hrr)
    flaming_end = flaming_after + 150.0
    return [
        (0.0, 0.0),
        (60.0, smolder_f),
        (float(flaming_after), smolder_f),
        (round(flaming_end, 1), 1.0),
        (round(max(hold_s, flaming_end + 300.0), 1), 1.0),
    ]


def preset_summaries() -> list[dict[str, Any]]:
    rows = []
    for preset in PRESETS.values():
        rows.append(
            {
                "name": preset["name"],
                "description": preset["description"],
                "growth_class": preset["growth_class"],
                "peak_hrr_kW": preset["peak_hrr"],
                "area_m2": preset["area"],
                "hrrpua_kW_m2": preset["hrrpua"],
                "soot_yield": preset["soot_yield"],
            }
        )
    return rows
