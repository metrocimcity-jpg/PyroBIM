# Fire Presets

FDS fires are usually modeled as **t-squared growth**: HRR = α·t² until peak, using a `&RAMP` curve
feeding a `&SURF` with `HRRPUA` (heat release rate per unit area, kW/m²).

Growth-rate buckets (standard NFPA t² classification):
| Class | α (kW/s²) | Time to 1055 kW |
|---|---|---|
| Slow | 0.0029 | ~600 s |
| Medium | 0.0117 | ~300 s |
| Fast | 0.0469 | ~150 s |
| Ultra-fast | 0.1876 | ~75 s |

## Preset library

### 1. Couch fire (upholstered furniture, polyurethane foam)
- Growth: **Fast to Ultra-fast**
- Peak HRR: **2000–3200 kW**
- Fuel area: ~1.5–2.0 m² (seat + back cushions)
- HRRPUA: ~1500–2000 kW/m²
- Suggested `SOOT_YIELD`: 0.10 (typical polyurethane)
- Time to peak: ~90–150 s, then steady/decay after fuel involvement

### 2. Cigarette fire (smoldering, upholstery ignition source)
- Growth: **Very slow / smoldering**, often held near-constant for long duration before optional transition to flaming
- Peak HRR: **~5 W (cigarette itself) up to 20–40 kW if it transitions to flaming upholstery**
- Fuel area: <0.01 m² (cigarette tip) → 0.3–0.5 m² if flaming transition occurs
- HRRPUA (smoldering phase): low, near 0 kW/m² radiative but include as `&DEVC` heat source or small `HRRPUA` ~5–20 kW/m²
- Model as two-stage: long smolder plateau (600–3000 s) then optional fast ramp if flaming transition requested

### 3. Car fire (single passenger vehicle, interior + engine bay)
- Growth: **Medium to Fast**
- Peak HRR: **4000–8000 kW** (single vehicle, full involvement)
- Fuel area: ~4–6 m² (interior + underbody)
- HRRPUA: ~1000–1500 kW/m²
- Suggested `SOOT_YIELD`: 0.06–0.09 (mixed plastics/foam/fuel)
- Time to peak: ~300–600 s typical for vehicle fires (can vary widely by source)

### 4. Wastebasket fire (small, fast-starting, useful as ignition test case)
- Growth: **Ultra-fast**
- Peak HRR: **50–150 kW**
- Fuel area: ~0.1–0.2 m²
- HRRPUA: ~500–750 kW/m²

## Usage notes
- These are engineering approximations for scenario modeling, not certified test data — good for
  training/demo/what-if simulations, not code-compliance submittals.
- `add_fire_preset` should let the AI pick growth class + peak HRR + area, then auto-generate the
  `&RAMP` time/HRR pairs (5–8 points is usually enough resolution).
- Cite NFPA/SFPE handbook values if a user wants defensible numbers for real design work.
