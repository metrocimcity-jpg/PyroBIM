# Fire, chemistry, and NFPA presets

FDS fires are usually **t-squared**: HRR = α·t² until peak, via `&RAMP` + `&SURF HRRPUA`.

## NFPA t² growth
| Class | α (kW/s²) | Time to 1055 kW |
|---|---|---|
| Slow | 0.0029 | ~600 s |
| Medium | 0.0117 | ~300 s |
| Fast | 0.0469 | ~150 s |
| Ultra-fast | 0.1876 | ~75 s |

## Scenario presets (`add_fire_preset`)
| Name | Growth | Peak HRR | Area | Notes |
|---|---|---|---|---|
| couch | ultra-fast | 2500 kW | 1.75 m² | PU foam furniture |
| cigarette | slow / smolder | 20 kW (35 kW flaming) | 0.3 m² | `flaming_after` optional |
| car | fast | 6000 kW | 5.0 m² | vehicle interior + bay |
| wastebasket | ultra-fast | 100 kW | 0.15 m² | ignition test |

These are engineering approximations, not certified test data.

## Simple chemistry (`add_reaction` / `list_fuels`)
Thunderhead [Modeling Fire](https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/modeling-fire/): specifying HRR sets fuel mass flow \(\dot m = \mathrm{HRR}/\Delta H_c\).

| Fuel | Use |
|---|---|
| PROPANE | Li/Ingason tunnel burner |
| N-HEPTANE | VTT large-hall HRR fire |
| WOOD | crib / cellulosic, burn-away |
| POLYURETHANE | generic PU (SPEC formula) |
| POLYURETHANE_GM27 | sooty car-park fire (SFPE GM27) |
| METHANE | clean gas |
| NATURAL_GAS / LNG | McCaffrey plume (NBSIR 79-1910) |
| METHANOL | Waterloo methanol pool fire |
| CELLULOSE | CSIRO grassland vegetation |

## Specified HRR vs HRRPUA vs pyrolysis
1. **HRR / HRRPUA + RAMP** — preferred engineering approach (`add_hrr_fire`)
2. **HRRPUA + TMP_IGN + BURN_AWAY** — next level without full pyrolysis (`add_hrrpua_fire`)
3. **Variable HRRPUA** — experimental `(t, kW)` curve on `add_hrr_fire(hrr_curve=...)`

## NFPA 13 sprinklers (`list_sprinklers`)
Default ordinary rating **68.33 °C** (PyroSim Generic Commercial Link). RTI: standard 148, QR 50, ESFR 36, residential 28. Flow from US K-factor at psi, written as FDS `FLOW_RATE` in L/min.

## NFPA 72 / 720 detectors (`list_detectors`)
| Kind | FDS | Default |
|---|---|---|
| Ionization smoke | `CHAMBER OBSCURATION` Cleary I1 | 3.24 %/m |
| Photoelectric smoke | Cleary P1 | 6.6 %/m |
| Heskestad smoke | `LENGTH=1.8` | 3.24 %/m |
| Spot heat | `LINK TEMPERATURE` | ordinary 57.2 °C, RTI 50 |
| CO | `VOLUME FRACTION` SPEC_ID='CARBON MONOXIDE' | 70 ppm |
| Beam | `PATH OBSCURATION` | 15 % |
| Aspiration | `ASPIRATION` + sampling `FLOWRATE`/`DELAY` | Verification pattern |
| Flame analogue | `RADIATIVE HEAT FLUX GAS` | 5 kW/m² |

Also: `add_tenability_device` for visibility, optical density (NIST Smoke Alarms), thermocouple, layer height.

## NFPA 502
`nfpa_502_critical_velocity` iterates \(V_c\) and \(T_f\). Suggest fire-region mesh ≈ D\*/10. Long tunnels: `set_pressure_solver(max_pressure_iterations=50)`.

## Materials
UMD FireBID table (PyroSim materials tutorial): `list_materials("oak"|"plastics"|"metals"|...)`. Layered wall example: gypsum 0.01 + insulation 0.09 + gypsum 0.01.
