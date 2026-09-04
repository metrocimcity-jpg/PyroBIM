# FDS Namelist Reference (for tool output)

FDS input is plain text groups: `&GROUP PARAM=value / `. One `.fds` file = many groups.

## Mesh
```
&MESH IJK=50,50,50, XB=0.0,5.0,0.0,5.0,0.0,5.0, ID='MESH1' /
```

## Fire surface (t-squared growth via RAMP)
```
&RAMP ID='fire_ramp', T=0.0,   F=0.0 /
&RAMP ID='fire_ramp', T=75.0,  F=0.25 /
&RAMP ID='fire_ramp', T=150.0, F=1.0 /
&RAMP ID='fire_ramp', T=600.0, F=1.0 /
&SURF ID='couch_fire', HRRPUA=1800.0, RAMP_Q='fire_ramp', COLOR='RED' /
```

## Placing the fire (obstruction acting as burner)
```
&OBST XB=1.0,2.5,1.0,1.8,0.0,0.5, SURF_IDS='couch_fire','INERT','INERT', ID='couch_1' /
```

## Reaction (fuel chemistry + soot yield — needed once per model)
```
&REAC ID='POLYURETHANE', FUEL='POLYURETHANE', SOOT_YIELD=0.10, CO_YIELD=0.05 /
```

## 2D slice (result plane)
```
&SLCF PBZ=1.5, QUANTITY='TEMPERATURE' /
&SLCF PBX=2.5, QUANTITY='VELOCITY' /
```

## Volumetric output (full-domain, cell-centered)
```
&SLCF QUANTITY='TEMPERATURE', CELL_CENTERED=.TRUE. /
```

## Isosurface (3D surface at a value — good for smoke/temp boundary)
```
&ISOF QUANTITY='TEMPERATURE', VALUE=60.0 /
```

## Smoke visualization
```
&SLCF PBZ=2.0, QUANTITY='EXTINCTION COEFFICIENT' /
```
Smoke rendering in Smokeview also depends on `SOOT_YIELD` in `&REAC` — no soot yield = no visible smoke.

## Device (sensor)
```
&DEVC XYZ=2.5,2.5,2.0, QUANTITY='THERMOCOUPLE', ID='TC_1' /
```

## Vent (open boundary / doorway)
```
&VENT XB=0.0,0.0,0.0,5.0,0.0,3.0, SURF_ID='OPEN' /
```

## Time
```
&TIME T_END=600.0 /
```

## Minimal file skeleton
```
&HEAD CHID='model1', TITLE='Couch fire test' /
&MESH IJK=50,50,50, XB=0,5,0,5,0,5 /
&TIME T_END=600.0 /
&REAC FUEL='POLYURETHANE', SOOT_YIELD=0.10 /
... surfaces, obst, vents, slcf, devc ...
&TAIL /
```
