"""Fire-modeling helpers from Thunderhead PyroSim tutorials and NFPA 502.

Sources:
- Modeling Fire in PyroSim (simple chemistry, HRR vs HRRPUA, burn-away)
  https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/modeling-fire/
- Critical Velocity in tunnel fires (NFPA 502, D*/10 mesh)
  https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/critical-velocity-tunnel/
"""

from __future__ import annotations

from typing import Any

# Ambient air used by NFPA 502 / FDS D* guidance.
RHO_AIR = 1.204  # kg/m³ at ~20 °C
CP_AIR = 1.005  # kJ/(kg·K)
G = 9.81  # m/s²
T_INF_K = 293.15
NFPA_502_K1 = 0.606  # Froude number factor


FUELS: dict[str, dict[str, Any]] = {
    "PROPANE": {
        "fuel": "PROPANE",
        "formula": "C3H8",
        "soot_yield": 0.024,
        "co_yield": 0.005,
        "heat_of_combustion": 46400.0,
        "radiative_fraction": 0.3,
        "critical_flame_temperature": 1327.0,
        "description": "FDS built-in. Li/Ingason tunnel critical-velocity sample.",
    },
    "N-HEPTANE": {
        "fuel": "N-HEPTANE",
        "formula": "C7H16",
        "soot_yield": 0.015,
        "co_yield": 0.0,
        "heat_of_combustion": 44500.0,
        "radiative_fraction": 0.35,
        "description": "VTT large-hall heptane fire (Modeling Fire tutorial / VTT_01.fds).",
    },
    "METHANE": {
        "fuel": "METHANE",
        "formula": "CH4",
        "soot_yield": 0.0,
        "co_yield": 0.0,
        "heat_of_combustion": 50000.0,
        "radiative_fraction": 0.2,
        "description": "FDS built-in methane.",
    },
    "POLYURETHANE": {
        "fuel": "POLYURETHANE",
        "formula": "C1H1.13O0.33N0.16",
        "needs_spec": True,
        "soot_yield": 0.10,
        "co_yield": 0.05,
        "heat_of_combustion": 25300.0,
        "radiative_fraction": 0.35,
        "description": "Generic PU; SPEC formula avoids FDS ERROR(171).",
    },
    "POLYURETHANE_GM27": {
        "fuel": "POLYURETHANE_GM27",
        "c": 1.0,
        "h": 1.7,
        "o": 0.3,
        "n": 0.08,
        "soot_yield": 0.198,
        "co_yield": 0.042,
        "heat_of_combustion": 25300.0,
        "radiative_fraction": 0.35,
        "description": "SFPE Handbook GM27 sooty PU (Thunderhead car-park / jet-fan tutorial).",
    },
    "WOOD": {
        "fuel": "WOOD",
        "formula": "C3.4H6.2O2.5",
        "needs_spec": True,
        "soot_yield": 0.015,
        "co_yield": 0.004,
        "heat_of_combustion": 15000.0,
        "radiative_fraction": 0.35,
        "description": "Cellulosic / wood-crib simple chemistry.",
    },
    "CELLULOSE": {
        "fuel": "CELLULOSE",
        "c": 6.0,
        "h": 10.0,
        "o": 5.0,
        "soot_yield": 0.02,
        "co_yield": 0.0,
        "heat_of_combustion": 15600.0,
        "radiative_fraction": 0.35,
        "description": "CSIRO grassland / vegetation Validation (C6H10O5).",
    },
    "NATURAL_GAS": {
        "fuel": "LNG",
        "formula": "C1.2143H4.4286",
        "needs_spec": True,
        "soot_yield": 0.0,
        "co_yield": 0.0,
        "heat_of_combustion": 45000.0,
        "radiative_fraction": 0.27,
        "description": "McCaffrey plume Validation natural-gas burner (NBSIR 79-1910).",
    },
    "METHANOL": {
        "fuel": "METHANOL",
        "formula": "CH3OH",
        "needs_spec": True,
        "soot_yield": 0.0,
        "co_yield": 0.0,
        "heat_of_combustion": 20000.0,
        "radiative_fraction": 0.18,
        "description": "Waterloo methanol pool-fire Validation.",
    },
}

FUEL_ALIASES = {
    "HEPTANE": "N-HEPTANE",
    "NHEPTANE": "N-HEPTANE",
    "PU": "POLYURETHANE",
    "GM27": "POLYURETHANE_GM27",
    "POLYURETHANE GM27": "POLYURETHANE_GM27",
    "CELLULOSE": "CELLULOSE",
    "WOOD CRIB": "WOOD",
    "LNG": "NATURAL_GAS",
    "NATURAL GAS": "NATURAL_GAS",
    "METHANOL": "METHANOL",
}


def resolve_fuel(name: str) -> dict[str, Any]:
    key = name.strip().upper().replace("_", " ")
    key = FUEL_ALIASES.get(key, key.replace(" ", "_") if key.replace(" ", "_") in FUELS else key)
    if key in FUEL_ALIASES:
        key = FUEL_ALIASES[key]
    if key not in FUELS:
        # Try underscore form.
        alt = name.strip().upper().replace(" ", "_")
        if alt in FUELS:
            key = alt
        else:
            raise ValueError(f"Unknown fuel '{name}'. Available: {', '.join(FUELS)}")
    return dict(FUELS[key])


def fuel_mass_from_hrr(hrr_kw: float, heat_of_combustion: float) -> float:
    """Fuel mass flow (kg/s) implied by a specified HRR.

    Thunderhead: specifying HRR tells FDS the fuel injection rate
    m_dot = HRR / ΔHc so combustion releases heat at that rate.
    HRR in kW, ΔHc in kJ/kg → kg/s.
    """
    if hrr_kw < 0:
        raise ValueError("hrr_kw must be >= 0")
    if heat_of_combustion <= 0:
        raise ValueError("heat_of_combustion must be positive (kJ/kg)")
    return hrr_kw / heat_of_combustion


def hrrpua_from_hrr(hrr_kw: float, area_m2: float) -> float:
    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")
    return hrr_kw / area_m2


def ramp_from_hrr_curve(points: list[tuple[float, float]]) -> tuple[float, list[tuple[float, float]]]:
    """Convert (t, HRR_kW) samples to (peak_hrr, fractional RAMP_Q points)."""
    if not points:
        raise ValueError("points must contain at least one (t, hrr_kw) pair")
    peak = max(hrr for _, hrr in points)
    if peak <= 0:
        raise ValueError("HRR curve peak must be positive")
    return peak, [(float(t), float(hrr) / peak) for t, hrr in points]


def characteristic_fire_diameter(hrr_kw: float, tmpa_c: float = 20.0) -> float:
    """FDS D* = (Q / (ρ cp T∞ √g))^(2/5). Q in kW → kJ/s."""
    if hrr_kw < 0:
        raise ValueError("hrr_kw must be >= 0")
    t_inf = tmpa_c + 273.15
    return (hrr_kw / (RHO_AIR * CP_AIR * t_inf * (G ** 0.5))) ** 0.4


def recommended_cell_size(hrr_kw: float, tmpa_c: float = 20.0, cells_per_dstar: float = 10.0) -> dict[str, float]:
    """Tunnel tutorial: fire-region mesh ≈ D*/10."""
    dstar = characteristic_fire_diameter(hrr_kw, tmpa_c=tmpa_c)
    dx = dstar / cells_per_dstar if dstar > 0 else 0.0
    return {"d_star_m": dstar, "dx_m": dx, "cells_per_dstar": cells_per_dstar}


def nfpa_502_critical_velocity(
    hrr_kw: float,
    height_m: float,
    area_m2: float,
    *,
    grade_factor: float = 1.0,
    tmpa_c: float = 20.0,
    k1: float = NFPA_502_K1,
    rho: float = RHO_AIR,
    cp: float = CP_AIR,
    iterations: int = 80,
) -> dict[str, float]:
    """Iterate the NFPA 502 critical-velocity pair.

    V_c = K1 Kg (g H Q / (ρ cp A T_f))^(1/3)
    T_f = T + Q / (ρ cp A V_c)
    Q in kW, cp in kJ/(kg·K), ρ in kg/m³ → V_c in m/s, T_f in K.
    """
    if hrr_kw < 0:
        raise ValueError("hrr_kw must be >= 0")
    if height_m <= 0 or area_m2 <= 0:
        raise ValueError("height_m and area_m2 must be positive")
    t_air = tmpa_c + 273.15
    v_c = 1.0
    t_f = t_air
    for _ in range(iterations):
        t_f = t_air + hrr_kw / (rho * cp * area_m2 * max(v_c, 1e-9))
        v_c = k1 * grade_factor * (G * height_m * hrr_kw / (rho * cp * area_m2 * t_f)) ** (1.0 / 3.0)
    return {
        "v_c_m_s": v_c,
        "t_f_k": t_f,
        "t_f_c": t_f - 273.15,
        "k1": k1,
        "grade_factor": grade_factor,
        "hrr_kw": hrr_kw,
        "height_m": height_m,
        "area_m2": area_m2,
        "tmpa_c": tmpa_c,
    }


FIRE_MODELING_GUIDANCE = """\
Thunderhead: Modeling Fire in PyroSim
https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/modeling-fire/

1. Simple chemistry
   Fuel is C,H,O,N. It mixes with oxygen and forms H2O, CO2, soot, CO, N2.
   The reaction is infinitely fast and mixing-controlled. Every combusting
   model needs one &REAC. Use add_reaction() with PROPANE, N-HEPTANE,
   POLYURETHANE, POLYURETHANE_GM27, WOOD, or METHANE.

2. HRR-defined fire (preferred engineering approach)
   Specifying HRR really specifies the fuel mass-release rate:
       m_dot_fuel (kg/s) = HRR (kW) / ΔHc (kJ/kg)
   FDS injects that fuel; combustion releases heat at the requested rate.
   Use add_hrr_fire() or fire_stoichiometry() to check the mass flux.
   The VTT large-hall heptane case uses an experimental RAMP_Q on HRRPUA
   (VTT_01.fds: HRRPUA=1290 kW/m², 1.2 m × 1.2 m burner).

3. HRRPUA + ignition + burn-away
   Next level of detail without full pyrolysis:
       &SURF HRRPUA=..., TMP_IGN=..., BURN_AWAY=.TRUE., MATL_ID=..., THICKNESS=...
   The solid disappears after its fuel is consumed. Drawbacks: burning does
   not respond to local heat flux the way real pyrolysis would.
   Use add_hrrpua_fire(burn_away=True, tmp_ign=...).

4. Variable HRRPUA (experimental curve)
   A constant HRRPUA often misses the measured HRR shape. Drive HRRPUA
   with RAMP_Q whose F values are fractions of peak. Pass hrr_curve
   [(t, kW), ...] to add_hrr_fire().

Materials
  PyroSim's materials tutorial copies GYPSUM/INSULATION from its library
  and builds Oak from the UMD FireBID table:
  http://firebid.umd.edu/material-database.php
  Use list_materials() / add_material() / add_layered_surface().
  Values are starting points, not a standard library.

Tunnel critical velocity
  https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/critical-velocity-tunnel/
  NFPA 502 V_c from nfpa_502_critical_velocity(). Fire-region mesh ≈ D*/10
  (characteristic_fire_diameter). Long tunnels: tighten PRESSURE_TOLERANCE
  and raise MAX_PRESSURE_ITERATIONS. Li/Ingason scale tunnel is 0.25 m
  square × 12 m, 1 mm steel lining, propane burner RADIUS=0.05 m.
"""
