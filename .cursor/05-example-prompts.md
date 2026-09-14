# PyroSim MCP — example prompts

Use these with the connected **pyrosim** MCP server. Prefer calling tools over hand-writing namelists.

Sources: Thunderhead [PyroSim 2026.1 examples](https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/), [Modeling Fire](https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/modeling-fire/), [Jet Fans](https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/modeling-jet-fans/), [Critical Velocity](https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/applications/critical-velocity-tunnel/), [Fire Protection Systems](https://www.thunderheadeng.com/docs/2026-1/pyrosim/examples/fundamentals/5-fire-protection-systems/), UMD [FireBID](http://firebid.umd.edu/material-database.php).

---

## Beginner (1–30)

Getting a model on disk, presets, slices, and simple sensors.

1. What fire presets are available, and what peak HRR does each use?
2. Create a new PyroSim model named `demo_room` for a 5×5×3 m room with 0.2 m cells, T_END 600 s.
3. Add a couch fire in the corner at (0.5, 0.5, 0).
4. Put a car fire preset in the garage bay at (3, 2, 0).
5. Add a wastebasket fire at (2, 2, 0) as a small ignition source.
6. Give me a smoldering cigarette on the sofa that stays smoldering (no flaming).
7. Same cigarette, but transition to flaming after 10 minutes.
8. Add a horizontal temperature slice at z = 1.5 m.
9. Add a velocity slice on the mid-room x plane and make it a vector slice.
10. Show smoke: visibility planes and soot yield for polyurethane.
11. Add a thermocouple 2 m above the fire.
12. List every output currently in this model.
13. Validate the FDS file and tell me if PyroSim would reject the slices.
14. Export the model to `models/demo_room.fds`.
15. Open this model in the PyroSim GUI.
16. Set ambient temperature to 21 °C.
17. Dump 600 frames, enable SMOKE3D, restart every 300 s.
18. What materials can I add from the catalog? List engineering defaults first.
19. Add concrete walls (CONCRETE material) as the default solid surface.
20. Add OPEN vents on all mesh faces except the floor.
21. Cut a 1 m × 2.1 m door hole in the south wall at x = 2 to 3 m.
22. Add a 0.2 m supply jet (VEL = −2 m/s) on the west wall.
23. Inspect the model: namelist counts, CHID, T_END, IDs.
24. List PyroSim sample FDS files that mention atrium or leakage.
25. Open the `door_crack` sample as a copy I can edit.
26. Add a gypsum board surface 16 mm thick.
27. Create a 60 °C temperature isosurface.
28. Add a wall-temperature boundary file.
29. What simple-chemistry fuels does the MCP know?
30. Run FDS on the active model with 4 cores, then open Smokeview.

---

## Intermediate (31–70)

Materials, chemistry, sprinklers, HVAC, specified HRR, and controls.

31. List FireBID hardwoods and add Oak the way the PyroSim materials tutorial does.
32. Build a US interior wall: 10 mm gypsum, 90 mm insulation, 10 mm gypsum, named `Default_Wall`.
33. Add AISI 304 stainless steel 1 mm thick for a tunnel lining (critical-velocity sample).
34. Add Nylon and PMMA from the plastics library; warn me these are FireBID starting points.
35. Set the reaction to propane with the tunnel-sample soot and radiative fraction.
36. Switch chemistry to sooty polyurethane GM27 for a car-park fire.
37. Compute fuel mass flow for a 1858 kW heptane fire on 1.44 m² (VTT HRRPUA check).
38. Add a specified-HRR heptane fire, 1290 kW/m² on 1.2×1.2 m, using the VTT ramp 0–13–288–438 s.
39. Add a 3 MW t-squared fast fire on 6 m² as a floor vent, not an obstruction.
40. Explain simple chemistry vs specified HRR vs HRRPUA+ignition+burn-away, then apply option 1.
41. Add an HRRPUA wood fire that ignites at 300 °C and burns away (Modeling Fire part 4).
42. Add HCN yield 0.01 and soot 0.1 on the current reaction (combustion calculator how-to).
43. List NFPA 13 sprinkler types the MCP can write.
44. Put a standard pendent sprinkler at (5, 5, 2.9) — ordinary 68.33 °C, K-5.6 at 7 psi.
45. Add an upright sprinkler on exposed pipe at (5, 5, 2.7).
46. Add a horizontal sidewall sprinkler on the west wall throwing +X.
47. Add a quick-response pendent (RTI 50) at the same location as the standard head.
48. Add a residential pendent (NFPA 13D) K-4.2 over a bedroom.
49. Add an ESFR K-14 pendent at 50 psi over a storage aisle.
50. Add a CMSA upright K-11.2 like the NIST bucket test.
51. Add an open deluge nozzle that starts immediately (no fusible link).
52. Aim an NFPA 15 water-spray nozzle at a transformer along −Y.
53. Add a concealed pendent with a short link offset.
54. Add a dry sidewall for an unheated loading dock, throw toward +X.
55. Add a Cleary ionization smoke detector at the ceiling centroid.
56. Add a heat detector, ordinary temperature, fast RTI 50, next to the sprinkler.
57. After the smoke detector, wait 30 s then activate an exhaust vent (Fire Protection Systems tutorial).
58. Deactivate the door obstruction 5 s after the smoke detector (occupant egress).
59. Add a two-node HVAC fan moving 1.0 m³/s from a ceiling inlet to an exterior outlet.
60. Add a leakage zone with 0.1 m² leak area (pressure-zone leakage how-to).
61. Add a leak-path surface between zone 1 and zone 0 on the door undercut.
62. Set a 5 m/s west wind (`DIRECTION=270`).
63. Add a circular propane burner, radius 0.05 m, at (0, 6, 0) like the Li/Ingason tunnel.
64. Mesh the fire region at about D\*/10 for a 2 kW scale-tunnel fire.
65. Add visibility and temperature slices at occupant height z = 1.8 m.
66. Add velocity isosurfaces at 1, 2, 5, 10, and 15 m/s (jet-fan tutorial).
67. Place an AREA INTEGRAL mass-flux-X device on the x = 4 m plane.
68. Freeze the idea of t² growth: ultra-fast to 2500 kW then hold (NFPA t² calculator tutorial).
69. Show me the PyroSim examples index mapped to MCP tools.
70. Validate, then summarize geometry, fires, sprinklers, and outputs for a report.

---

## Advanced (71–100)

Tunnels, jet fans, car parks, multi-system protection, and design checks.

71. Compute NFPA 502 critical velocity for 20 MW in a 5 m high × 12 m wide tunnel, −4% grade, 20 °C.
72. Build the Li/Ingason 0.25×0.25×12 m steel tunnel, 1 mm wall, propane 2 kW circular burner, inlet OPEN, outlet OPEN.
73. Add a ceiling thermocouple rake every 0.05 m from y = 4.5 to 7.0 m at z = 0.24 m to track backlayering.
74. Tighten the pressure solver for a long tunnel: MAX_PRESSURE_ITERATIONS=50.
75. Add a 0.25×0.25 m jet supply vent at 18 m/s (VEL negative) for a free-jet study.
76. Add a velocity patch 0.25 m square, P0 = −18 m/s in X, for a jet fan without HVAC.
77. Recommend HVAC+shroud vs velocity-patch+short-shroud for a 125 mm design mesh (Thunderhead jet-fan page).
78. Size a 73 N jet fan on a 0.375 m square (125 mm mesh): equivalent V and Q to keep thrust.
79. Model five 0.25 m jet fans in a 60×30×3 m car park pushing toward two 4×3 m exhaust openings.
80. Put a 3000 kW GM27 polyurethane fire on 6 m² (HRRPUA 500) in that car park, ramp 200–300–500–600 s.
81. Use 125 mm cells around the fans and 250 mm in the far field; tell me IJK for each mesh.
82. Add a downstream HVAC shroud so the fan outlet stays axial on the staggered grid.
83. Compare Baturin/Kümmel centerline decay for a 0.25 m, 18 m/s square jet — then place centerline velocity probes every 0.5 m.
84. Add VECTOR velocity slices at Y = 0 and X = 4 m for the free jet.
85. Import a Thunderhead jet-fan sample, inspect namelists, and clone the HVAC fan pattern into my model.
86. Model a 0.25 m square tunnel fire at 16.7 kW with inlet velocities 0.5, 0.6, and 0.7 m/s as three scenarios (critical velocity tutorial).
87. Add window sprinklers aimed at a glass curtain wall (`ORIENTATION` toward the glazing).
88. Lay out QR pendents at 4.6 m spacing (light hazard / 15 ft) in a 12×12 m office and list K, P, L/min.
89. In-rack sprinklers on two storage tiers plus ceiling ESFR — different PROP IDs, don’t collide.
90. Deluge system: heat detector trips a CTRL that opens a bank of nozzles (don’t use fusible links on the nozzles).
91. Wood-crib HRRPUA with burn-away on oak, then stop the run when the first sprinkler activates (t² freeze / stop tutorial).
92. Solar-panel cooling style: hot `TMP_FRONT` surfaces, OPEN sides, temperature slices in the air gap.
93. Pressure-relief vent: high-capacity OPEN or leak path that dumps when compartment pressure rises.
94. Multi-mesh MPI: three meshes along a 100 m tunnel and tell me how to pin them to MPI processes.
95. Add a velocity patch plus a short OBST shroud for a 2.5 m jet fan pointing −X (car-park redesign).
96. Visibility tenability: show_smoke, slices at 2 m, and devices for visibility at egress doors.
97. Combine smoke detector, QR pendent, 30 s delayed exhaust, and a GM27 sofa fire in one compartment.
98. Scale-up: 73 N fans, nine heads, 6×3 m supply opening, GM27 3 MW — HVAC+shroud, conservative entrainment note.
99. Audit this `.fds` against PyroSim rules: SLCF geometry, unique IDs per group, VEL sign, sprinkler FLOW_RATE units.
100. Write a model-check narrative: chemistry, HRR vs mass flux, mesh vs D\*, sprinkler K-factor and RTI class, NFPA 502 V_c if it is a tunnel.

---

## NIST FDS Validation (101–110)

[firemodels/fds Validation](https://github.com/firemodels/fds/tree/master/Validation) — 135 series. Prefer `list_fds_validation` / `open_fds_validation` over guessing paths.

101. List FDS Validation series about tunnels.
102. What is the McCaffrey plume series, and which local cases are available?
103. Open `McCaffrey_45_kW_21.fds` from the McCaffrey_Plume Validation folder as an editable copy.
104. Recreate a McCaffrey-style 45 kW natural-gas burner with a 30-point thermocouple line up the plume axis.
105. Open a Steckler compartment case and tell me how the door HOLE and burner VENT are set.
106. Add a CSIRO-style grassland vegetation bed over 0–20 m by 0–20 m, packing ratio 0.0026, with a 4.6 m/s west wind (Z_0=0.03, L=-500).
107. Which Validation series should I copy for sprinkler / ceiling-jet work?
108. Open a NIST pool-fire Validation case that uses a circular RADIUS vent.
109. Point me at Memorial Tunnel and Wu–Bakar Validation inputs for NFPA 502 critical velocity.
110. Summarize how FDS Validation maps to this MCP (`fds_validation_guidance`).

## Detectors (111–120)

111. What smoke, heat, and gas detectors can this MCP add?
112. Put an ionization smoke detector at the ceiling centroid (2.5, 2.5, 2.9).
113. Add a photoelectric smoke detector at (1, 1, 2.9) using the NIST Dunes 2000 photo preset.
114. Add an ordinary NFPA 72 heat detector (135 °F) next to the smoke detector.
115. Add a 70 ppm CO detector at 1.5 m height, and a propane 10 % LEL detector near the floor.
116. Stretch a projected-beam smoke detector from (0.5, 2.5, 2.7) to (4.5, 2.5, 2.7) with a 15 % trip.
117. Add a VESDA-style aspiration detector in the cabinet at (0.2, 0.2, 0.3) sampling (2,2,2.8) and (4,2,2.8).
118. Aim a flame detector at the burner from (0.5, 2.5, 2.0) looking +X, 5 kW/m².
119. Add a 10 m visibility tenability probe at (2.5, 2.5, 1.8) and an optical-density probe at the same point.
120. Open the NIST_Smoke_Alarms Validation series and tell me which ionization vs photoelectric PROPs it uses.

---

## How to use a prompt

- **One task per message** for beginner items; chain 3–5 tools for intermediate.
- Name numbers in SI (m, kW, °C). For sprinklers you may say “K-5.6 at 7 psi”; the MCP converts to L/min.
- If the model already exists, say “on the active model” instead of recreating it.
- For samples: `list_sample_library` then `open_sample` rather than guessing paths.

## Quick tool map

| You say | Tool |
|---|---|
| new room / mesh | `new_model`, `add_mesh` |
| couch / car / cigarette | `add_fire_preset` |
| specified kW fire | `add_hrr_fire`, `fire_stoichiometry` |
| burn-away solid | `add_hrrpua_fire` |
| Oak / gypsum wall | `list_materials`, `add_material`, `add_layered_surface` |
| pendent / sidewall / ESFR | `list_sprinklers`, `add_sprinkler` |
| smoke / heat / CO / beam | `list_detectors`, `add_smoke_detector`, `add_heat_detector`, `add_gas_detector` |
| tunnel V_c | `nfpa_502_critical_velocity` |
| jet fan | `add_velocity_patch`, `add_flow_vent`, `add_hvac_fan` |
| smoke / slices | `show_smoke`, `create_2d_slice` |
| what can this MCP do? | `pyrosim_examples_index`, `list_catalog`, `list_fds_validation` |
| NIST Validation case | `list_fds_validation`, `open_fds_validation` |
