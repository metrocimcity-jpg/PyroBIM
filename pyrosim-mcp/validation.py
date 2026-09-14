"""NIST FDS Validation suite catalog (firemodels/fds Validation/).

Source: https://github.com/firemodels/fds/tree/master/Validation
Guide: NIST SP 1018-3, FDS Technical Reference Guide Vol. 3 (Experiment chapter).
Local copies are typically under PYROSIM_SAMPLES/fds-master/Validation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

GITHUB_VALIDATION = "https://github.com/firemodels/fds/tree/master/Validation"
GUIDE_URL = "https://github.com/firemodels/fds/blob/master/Manuals/FDS_Validation_Guide/Experiment_Chapter.tex"
GUIDE_PDF = "https://pages.nist.gov/fds-smv/"

CATEGORIES = [
    "plume",
    "compartment",
    "ceiling_jet",
    "velocity",
    "species",
    "pressure",
    "heat_flux",
    "suppression",
    "burning_rate",
    "pyrolysis",
    "wind",
    "vegetation",
    "tunnel",
    "jet_lng",
    "structure",
    "aerosol",
    "flow",
    "materials",
    "scaling",
    "other",
]

CATEGORY_TOOLS: dict[str, list[str]] = {
    "plume": ["add_hrr_fire", "add_line_device", "create_2d_slice", "add_reaction"],
    "compartment": ["add_hrr_fire", "add_hole", "add_device", "add_open_boundaries"],
    "ceiling_jet": ["add_hrr_fire", "add_sprinkler", "add_device", "create_2d_slice"],
    "velocity": ["add_flow_vent", "set_wind", "create_2d_slice", "add_device"],
    "species": ["add_reaction", "add_device", "show_smoke"],
    "pressure": ["add_pressure_zone", "add_hole", "add_vent", "set_pressure_solver"],
    "heat_flux": ["add_hrr_fire", "add_device", "add_layered_surface"],
    "suppression": ["add_sprinkler", "add_surface", "add_device"],
    "burning_rate": ["add_hrr_fire", "add_hrrpua_fire", "add_reaction", "fire_stoichiometry"],
    "pyrolysis": ["add_hrrpua_fire", "add_material", "add_layered_surface"],
    "wind": ["set_wind", "add_open_boundaries", "create_2d_slice"],
    "vegetation": ["add_vegetation_bed", "set_wind", "add_hrr_fire", "add_reaction"],
    "tunnel": [
        "nfpa_502_critical_velocity",
        "set_pressure_solver",
        "add_hrr_fire",
        "add_flow_vent",
        "add_velocity_patch",
    ],
    "jet_lng": ["add_hrr_fire", "set_wind", "add_reaction", "create_2d_slice"],
    "structure": ["add_material", "add_layered_surface", "add_device", "add_hrr_fire"],
    "aerosol": ["add_device", "add_surface", "show_smoke"],
    "flow": ["add_flow_vent", "add_hvac_fan", "set_wind", "create_2d_slice"],
    "materials": ["list_materials", "add_material", "add_layered_surface", "add_hrrpua_fire"],
    "scaling": ["add_mesh", "run_simulation"],
    "other": ["inspect_model", "import_fds", "validate_fds"],
}

# id | category | Validation Guide chapter | title | one-line summary
_ROWS = """\
ATF_Corridors|ceiling_jet|Ceiling Jet|ATF Corridors|ATF Fire Research Lab corridor ceiling-jet temperatures (Sheppard/Klein, 2008).
Aalto_Woods|pyrolysis|Burning Rate|Aalto Woods|Aalto University wood specimen pyrolysis / fire-resistance tests.
Arup_Tunnel|tunnel|Velocity|ArupFire Tunnel|ArupFire tunnel fire experiments (longitudinal ventilation / smoke control).
Askervein_Hill|wind|Wind|Askervein Hill|Neutral atmospheric boundary-layer flow over Askervein Hill.
Atmospheric_Dispersion|species|Species|Atmospheric Dispersion|Passive atmospheric dispersion correlations vs FDS WIND forcing.
BGC_GRI_LNG_Fires|jet_lng|Heat Flux|BGC/GRI LNG Fires|British Gas / GRI LNG pool-fire radiation.
BRE_Spray|suppression|Suppression|BRE Spray|BRE water-spray radiation attenuation.
BST_FRS_wood_cribs|burning_rate|Burning Rate|BST/FRS Wood Cribs|Building Research / FRS wood-crib fire spread (Aalto input files).
Backward_Facing_Step|flow|Velocity|Backward Facing Step|Separated/reattaching channel flow benchmark.
Beyler_Hood|compartment|Species|Beyler Hood|Beyler hood combustion-product yield experiments.
Bittern_Sprinkler_Experiments|suppression|Suppression|Bittern Sprinklers|University of Canterbury residential sprinkler / water-spray cases (Bittern).
Bluff_Body_Flows|flow|Velocity|Bluff Body Flows|Bluff-body aerodynamic validation (drag / wake).
Bouchair_Solar_Chimney|flow|Velocity|Bouchair Solar Chimney|Naturally ventilated solar chimney.
Bryant_Doorway|velocity|Velocity|Bryant Doorway|NIST doorway velocity profiles (PIV) for a compartment fire.
CAROLFIRE|structure|Surface Temperature|CAROLFIRE|NRC Cable Response to Live Fire (THIEF / cable heating).
CERTEC_Pool_Fires|burning_rate|Burning Rate|CERTEC Pool Fires|CERTEC liquid pool-fire burning rates.
CSIRO_Grassland_Fires|vegetation|Wind|CSIRO Grassland Fires|Australian grassland fire spread; WIND + static PART vegetation packing.
CSTB_Tunnel|tunnel|Velocity|CSTB Tunnel|CSTB tunnel fire / ventilation experiments.
Casara_Arts_Ribbed_Channel|flow|Velocity|Casara-Arts Ribbed Channel|Ribbed-channel heat-transfer / turbulence.
Convection|flow|Heat Flux|Convection|Natural/forced convection validation cases.
Crown_Fires|vegetation|Wind|Crown Fires|Crown-fire spread through tree canopies (PART vegetation).
Cup_Burner|species|Suppression|Cup Burner|Laminar cup-burner extinguishing concentration (VTT).
DelCo_Trainers|compartment|HGL|DelCo Trainers|Delaware County live-fire trainer compartments.
DoJ_HAI_Pool_Fires|burning_rate|Heat Flux|DoJ/HAI Pool Fires|DoJ / Hughes Associates pool-fire heat flux.
Droplet_Evaporation|suppression|Suppression|Droplet Evaporation|Single/cloud droplet evaporation.
Edinburgh_Vegetation_Drag|vegetation|Wind|Edinburgh Vegetation Drag|Vegetation aerodynamic drag (Edinburgh).
FAA_Cargo_Compartments|compartment|HGL|FAA Cargo Compartments|FAA aircraft cargo-compartment fires (Oztekin).
FAA_Polymers|pyrolysis|Burning Rate|FAA Polymers|FAA polymer pyrolysis (UMD properties: PMMA, HDPE, HIPS, PVC).
FHWA_Tunnel|tunnel|Velocity|FHWA Tunnel|FHWA road-tunnel fire / ventilation.
FM_Burner|plume|Plume|FM Burner|FM Global gas-burner flames.
FM_FPRF_Datacenter|flow|Velocity|FM/FPRF Datacenter|FM/FPRF data-center airflow and hot-aisle cases.
FM_Parallel_Panels|heat_flux|Heat Flux|FM Parallel Panels|FM parallel-panel upward flame spread / heat flux.
FM_SNL|compartment|HGL|FM/SNL|Factory Mutual / Sandia NRC-sponsored enclosure fires.
FM_Vertical_Wall_Flames|heat_flux|Heat Flux|FM Vertical Wall Flames|FM vertical wall-flame heat flux.
Fleury_Heat_Flux|heat_flux|Heat Flux|Fleury Heat Flux|Canterbury propane-burner heat-flux measurements (Fleury).
Frankman_Vegetation|vegetation|Heat Flux|Frankman Vegetation|Vegetation radiative heating / drying (Frankman).
Hamins_Gas_Burners|plume|Plume|Hamins Gas Burners|NIST Hamins methane/propane burner measurements.
Harrison_Spill_Plumes|plume|Plume|Harrison Spill Plumes|Balcony spill-plume mass-entrainment (Harrison/Spearpoint).
Hasemi_LocFire_Column|heat_flux|Heat Flux|Hasemi Localized Fire / Column|Hasemi localized fire heat flux to a steel column.
Heated_Channel_Flow|flow|Velocity|Heated Channel Flow|Heated channel mixed convection.
Heskestad_Flame_Height|plume|Plume|Heskestad Flame Height|Heskestad flame-height correlation vs specified HRR.
Insulation_Materials|pyrolysis|Surface Temperature|Insulation Materials|Fire-resistance / insulation pyrolysis (Aalto).
JH_FRA|tunnel|HGL|JH/FRA Rail Car|Jensen Hughes / FRA rail-car fire experiments.
JH_NIJ|materials|Burning Rate|JH/NIJ Materials|Jensen Hughes / NIJ furnished-material properties.
JIS_Facade|heat_flux|Heat Flux|JIS Facade|Japanese facade flame / heat-flux experiments.
Juelich_SETCOM|aerosol|Species|Juelich SETCOM|SETCOM wall condensation / steam experiments.
Kashiwagi_Gasification|pyrolysis|Burning Rate|Kashiwagi Gasification|Radiant gasification of solids (Kashiwagi).
LEMTA_Spray|suppression|Suppression|LEMTA Spray|LEMTA water-spray radiation attenuation and cooling.
LEMTA_UGent_Pool_Fires|burning_rate|Burning Rate|LEMTA/UGent Pool Fires|LEMTA / Ghent liquid pool fires.
LLNL_Enclosure|compartment|HGL|LLNL Enclosure|Lawrence Livermore enclosure fires.
LNG_Dispersion|jet_lng|Species|LNG Dispersion|PHMSA/Sandia LNG vapor-dispersion experiments.
Lattimer_Corridor_Ceiling|ceiling_jet|Ceiling Jet|Lattimer Corridor Ceiling|VT corridor ceiling heat flux (Lattimer).
Lattimer_Tilted_Wall|heat_flux|Heat Flux|Lattimer Tilted Wall|VT tilted-wall flame heat flux.
Loughborough_Jet_Fires|jet_lng|Heat Flux|Loughborough Jet Fires|High-pressure jet-fire radiation (Loughborough).
MPI_Scaling_Tests|scaling|Other|MPI Scaling Tests|Multi-mesh MPI performance (not a physics experiment).
McCaffrey_Plume|plume|Plume|McCaffrey Plume|NBSIR 79-1910 buoyant diffusion flames; centerline T and W vs height.
Memorial_Tunnel|tunnel|Velocity|Memorial Tunnel|Memorial Tunnel fire ventilation (full-scale road tunnel).
Missoula_Wood_Cribs|burning_rate|Burning Rate|Missoula Wood Cribs|USFS Missoula wood-crib burning rates.
Montoir_LNG_Fires|jet_lng|Heat Flux|Montoir LNG Fires|Montoir large LNG pool fires.
Moody_Chart|flow|Velocity|Moody Chart|Pipe/channel friction-factor (Moody) benchmark.
NBS_Multi-Room|compartment|HGL|NBS Multi-Room|1980s NBS three-room fire experiments (Peacock).
NIST_Backdraft|compartment|Species|NIST Backdraft|NIST backdraft compartment experiments.
NIST_Calibration_Burners|plume|Plume|NIST Calibration Burners|NIST standard calibration burners.
NIST_Composite_Beam|structure|Surface Temperature|NIST Composite Beam|Composite-beam heating under fire.
NIST_Deposition_Gauge|aerosol|Species|NIST Soot Deposition Gauge|Soot deposition gauge measurements.
NIST_Douglas_Firs|vegetation|Burning Rate|NIST Douglas Firs|Douglas-fir tree burning / WUI fuel.
NIST_E119_Compartment|structure|Surface Temperature|NIST E119 Compartment|ASTM E119 compartment furnace exposure.
NIST_FSE_2008|compartment|HGL|NIST Full-Scale Enclosure 2008|NIST FSE-2008 standard compartment.
NIST_He_2009|plume|Plume|NIST Helium 2009|NIST helium plume (non-reacting buoyancy).
NIST_NRC|compartment|HGL|NIST/NRC Compartment|NIST/NRC nuclear-plant enclosure fires (Hamins).
NIST_NRC_Corner_Effects|heat_flux|Heat Flux|NIST/NRC Corner Effects|Corner, wall, and cabinet fire heat flux.
NIST_NRC_OLIVE-Fire|compartment|HGL|NIST/NRC OLIVE-Fire|OLIVE-Fire electrical-cabinet experiments.
NIST_NRC_Parallel_Panels|heat_flux|Heat Flux|NIST/NRC Parallel Panels|NRC parallel-panel flame spread.
NIST_NRC_Transient_Combustibles|burning_rate|Burning Rate|NIST/NRC Transient Combustibles|Transient combustible packages in NPP rooms.
NIST_Polymers|pyrolysis|Burning Rate|NIST Polymers|NIST polymer pyrolysis / cone-scale burning.
NIST_Pool_Fires|burning_rate|Burning Rate|NIST Pool Fires|NIST liquid pool fires (circular RADIUS vents).
NIST_RSE_1994|compartment|HGL|NIST Reduced-Scale Enclosure 1994|NIST RSE-1994 reduced-scale enclosure.
NIST_RSE_2007|compartment|HGL|NIST Reduced-Scale Enclosure 2007|NIST RSE-2007 reduced-scale enclosure.
NIST_Smoke_Alarms|species|Species|NIST Smoke Alarms|Smoke-alarm activation / obscuration (CHAMBER OBSCURATION).
NIST_Structure_Separation|heat_flux|Heat Flux|NIST Structure Separation|WUI structure-separation heat flux.
NIST_USFS_Camp_Swift|vegetation|Wind|NIST/USFS Camp Swift|Camp Swift prescribed-fire / WUI field case.
NIST_Vent_Study|pressure|Pressure|NIST Vent Study|Compartment vent-flow / pressure.
NRCC_Facade|heat_flux|Heat Flux|NRCC Facade|NRCC facade heat-flux measurements.
NRCC_Smoke_Tower|compartment|HGL|NRCC Smoke Tower|NRCC smoke-tower (stair/shaft) experiments.
NRL_HAI|heat_flux|Heat Flux|NRL/HAI Wall Heat Flux|NRL / Hughes Associates confined-space wall heat flux.
OMP_Scaling_Tests|scaling|Other|OpenMP Scaling Tests|OpenMP performance (not a physics experiment).
PRISME|compartment|HGL|PRISME|OECD PRISME multi-room nuclear-facility fires (VTT/Lund inputs).
Phoenix_LNG_Fires|jet_lng|Heat Flux|Phoenix LNG Fires|Phoenix LNG pool-fire radiation.
Pool_Fires|burning_rate|Burning Rate|Pool Fires|Canonical liquid pool-fire set (circular burners, specified HRRPUA).
Purdue_Flames|plume|Plume|Purdue Flames|Purdue laboratory diffusion flames.
Ranz_Marshall|suppression|Suppression|Ranz-Marshall|Classic droplet evaporation (Ranz–Marshall).
Restivo_Experiment|flow|Velocity|Restivo Experiment|Isothermal compartment mixing / jet ventilation (Restivo).
SNL_Walls|heat_flux|Heat Flux|SNL Walls|Sandia wall-fire heat flux.
SP_AST|structure|Surface Temperature|SP Adiabatic Surface Temperature|SP plate-thermometer / AST steel-beam tests (Wickström).
SP_Wood_Cribs|burning_rate|Burning Rate|SP Wood Cribs|SP wood-crib burning rates.
SWJTU_Tunnels|tunnel|Velocity|SWJTU Tunnels|Southwest Jiaotong University tunnel fires.
Sandia_Crude_Oil|burning_rate|Burning Rate|Sandia Crude Oil|Sandia crude-oil pool fires.
Sandia_Fireballs|jet_lng|Heat Flux|Sandia Fireballs|Sandia fireball radiation.
Sandia_Jet_Fires|jet_lng|Heat Flux|Sandia Jet Fires|Sandia high-pressure jet fires.
Sandia_Methane_Burner|plume|Plume|Sandia Methane Burner|Sandia FLAME methane burner.
Sandia_Plumes|plume|Plume|Sandia Plumes|Sandia helium / fire plumes (FLAME facility).
Sandia_Pool_Fires|burning_rate|Burning Rate|Sandia Pool Fires|Sandia liquid pool fires.
Scaling_Pyrolysis|pyrolysis|Burning Rate|Scaling Pyrolysis|Pyrolysis scaling between cone and larger samples.
Schoenberg_Ekman_Layers|wind|Wind|Schoenberg Ekman Layers|Atmospheric Ekman-layer wind profiles.
Shell_LNG_Fireballs|jet_lng|Heat Flux|Shell LNG Fireballs|Shell LNG fireball experiments.
Sippola_Aerosol_Deposition|aerosol|Species|Sippola Aerosol Deposition|Indoor aerosol deposition.
Smyth_Slot_Burner|plume|Plume|Smyth Slot Burner|NIST Smyth slot-burner flame.
Steckler_Compartment|compartment|HGL|Steckler Compartment|Steckler 1979 doorway flow / HGL (classic 2.8×2.8×2.18 m room).
TAMU_Jet_Fires|jet_lng|Heat Flux|TAMU Jet Fires|Texas A&M jet-fire experiments.
TUS_Facade|heat_flux|Heat Flux|TUS Facade|Tokyo University of Science facade fires.
Theobald_Hose_Stream|suppression|Suppression|Theobald Hose Stream|Hose-stream water application.
Turbulent_Jet|flow|Velocity|Turbulent Jet|Free turbulent jet benchmark.
UL_NFPRF|suppression|Suppression|UL/NFPRF Sprinkler-Vent-Draft Curtain|UL/NFPRF sprinkler, vent, and draft-curtain study (Sheppard).
UL_NIJ_Houses|compartment|HGL|UL/NIJ Houses|UL/NIJ furnished-house fire experiments.
UL_NIST_Vents|pressure|Pressure|UL/NIST Vents|UL/NIST compartment vent flows.
UMD_Burning_Rate_Emulator|burning_rate|Burning Rate|UMD Burning Rate Emulator|UMD gas-burner emulator of condensed-fuel burning rate.
UMD_Line_Burner|species|Species|UMD Line Burner|UMD slot/line burner extinction / radiation.
UMD_Polymers|pyrolysis|Burning Rate|UMD Polymers|UMD polymer properties (Stoliarov).
UMD_SBI|heat_flux|Heat Flux|UMD SBI|UMD Single Burning Item heat flux.
USCG_HAI|suppression|Suppression|USCG/HAI Water Mist|USCG / Hughes Associates water-mist suppression.
USFS_Catchpole|vegetation|Wind|USFS/Catchpole|USFS Catchpole grassland/wildland spread.
USFS_Corsica|vegetation|Wind|USFS/Corsica|USFS Corsica vegetation-fire experiments.
USFS_Deep_Fuel_Beds|vegetation|Burning Rate|USFS Deep Fuel Beds|Deep fuel-bed smoldering / spread.
USN_Hangars|compartment|HGL|USN High Bay Hangars|US Navy high-bay hangar fires.
UWO_Wind_Tunnel|wind|Wind|UWO Wind Tunnel|University of Western Ontario building-wind tunnel.
Ulster_SBI|heat_flux|Heat Flux|Ulster SBI|University of Ulster SBI corner heat flux (Zhang).
Utiskul_Compartment|compartment|HGL|Utiskul Compartment|Under-ventilated compartment (Utiskul).
VTT|compartment|HGL|VTT Large Hall|VTT large-hall heptane fires (PyroSim Modeling Fire sample).
VTT_Sprays|suppression|Suppression|VTT Water Sprays|VTT water-spray characterization.
Vettori_Flat_Ceiling|ceiling_jet|Ceiling Jet|Vettori Flat Ceiling|NIST Vettori flat-ceiling sprinkler / ceiling-jet.
Vettori_Sloped_Ceiling|ceiling_jet|Ceiling Jet|Vettori Sloped Ceiling|NIST Vettori sloped-ceiling sprinkler / ceiling-jet.
WTC|compartment|Heat Flux|WTC Spray Burners|WTC investigation spray-burner compartment tests (Hamins).
Wasson_Impinging_Plumes|plume|Heat Flux|Wasson Impinging Plumes|Impinging plume heat flux (Wasson).
Waterloo_Methanol|burning_rate|Burning Rate|Waterloo Methanol|Waterloo methanol pool fire.
Wu_Bakar_Tunnels|tunnel|Velocity|Wu–Bakar Tunnels|Wu and Bakar critical-velocity scale tunnels (NFPA 502 lineage).
"""

# Older local trees may still use these folder names.
_LOCAL_ALIASES = {
    "Natural_Convection": "Convection",
    "Vegetation": "CSIRO_Grassland_Fires",
    "CHRISTIFIRE": "CAROLFIRE",
}


def _parse_rows() -> dict[str, dict[str, Any]]:
    series: dict[str, dict[str, Any]] = {}
    for raw in _ROWS.strip().splitlines():
        series_id, category, chapter, title, summary = raw.split("|", 4)
        series[series_id] = {
            "id": series_id,
            "category": category,
            "chapter": chapter,
            "title": title,
            "summary": summary,
            "github": f"{GITHUB_VALIDATION}/{series_id}",
            "tools": list(CATEGORY_TOOLS.get(category, CATEGORY_TOOLS["other"])),
        }
    return series


SERIES: dict[str, dict[str, Any]] = _parse_rows()


def validation_roots(samples_root: Path | None = None) -> list[Path]:
    """Folders that may contain firemodels/fds Validation/ on this machine."""
    roots: list[Path] = []
    env = os.environ.get("FDS_VALIDATION")
    if env:
        roots.append(Path(env))
    if samples_root is None:
        samples_root = Path(os.environ.get("PYROSIM_SAMPLES", r"D:\@LIB\PyroSim\Samples"))
    candidates = [
        samples_root / "fds-master" / "Validation",
        samples_root / "fds" / "Validation",
        samples_root / "Validation",
    ]
    fds_env = os.environ.get("FDS_ROOT")
    if fds_env:
        candidates.append(Path(fds_env) / "Validation")
    for path in candidates:
        if path not in roots:
            roots.append(path)
    return [path for path in roots if path.exists()]


def resolve_series(name: str) -> dict[str, Any]:
    key = name.strip()
    if key in _LOCAL_ALIASES and key not in SERIES:
        key = _LOCAL_ALIASES[key]
    compact = key.replace(" ", "_")
    if compact in SERIES:
        return dict(SERIES[compact])
    lower = compact.lower().replace("-", "_")
    for series_id, row in SERIES.items():
        hay = f"{series_id} {row['title']} {row['summary']} {row['category']}".lower()
        if lower == series_id.lower() or lower in hay.replace("-", "_"):
            return dict(row)
    raise ValueError(
        f"Unknown Validation series '{name}'. "
        f"Call list_fds_validation() — {len(SERIES)} series in firemodels/fds."
    )


def find_series_dir(series_id: str, samples_root: Path | None = None) -> Path | None:
    for root in validation_roots(samples_root):
        direct = root / series_id
        if direct.is_dir():
            return direct
        for alias, target in _LOCAL_ALIASES.items():
            if target == series_id and (root / alias).is_dir():
                return root / alias
    return None


def list_case_files(series_id: str, samples_root: Path | None = None) -> list[Path]:
    folder = find_series_dir(series_id, samples_root)
    if folder is None:
        return []
    preferred = folder / "FDS_Input_Files"
    search = preferred if preferred.is_dir() else folder
    files = [
        path
        for path in sorted(search.rglob("*.fds"))
        if "Current_Results" not in path.parts
    ]
    return files


def search_series(query: str = "", category: str = "") -> list[dict[str, Any]]:
    needle = query.lower().strip()
    cat = category.lower().strip().replace(" ", "_")
    rows: list[dict[str, Any]] = []
    for row in SERIES.values():
        if cat and row["category"] != cat and cat not in row["chapter"].lower().replace(" ", "_"):
            continue
        hay = " ".join(
            [row["id"], row["title"], row["summary"], row["category"], row["chapter"]]
        ).lower()
        if needle and needle not in hay:
            continue
        rows.append(row)
    return rows


def format_series(row: dict[str, Any], *, local: Path | None = None, n_cases: int | None = None) -> str:
    bits = [
        f"{row['id']}  [{row['category']} / {row['chapter']}]",
        f"  {row['title']}: {row['summary']}",
        f"  GitHub: {row['github']}",
        f"  Tools: {', '.join(row['tools'])}",
    ]
    if local is not None:
        extra = f" ({n_cases} .fds)" if n_cases is not None else ""
        bits.append(f"  Local: {local}{extra}")
    return "\n".join(bits)


VALIDATION_GUIDANCE = f"""\
NIST FDS Validation suite
{GITHUB_VALIDATION}
Guide (Experiment chapter): {GUIDE_URL}
PDF manuals: {GUIDE_PDF}

{len(SERIES)} test series. Each folder is FDS_Input_Files/*.fds + Run_All.sh.
Do not invent cases; open a local copy with open_fds_validation(series, case)
or import from GitHub. Experimental data lives in firemodels/exp; processed
output in firemodels/out.

Chapters (ASTM E1355 quantities of interest)
- Plume: McCaffrey, Heskestad, Hamins, Sandia_Plumes, FM_Burner
- HGL / compartment: Steckler, NBS_Multi-Room, NIST_NRC, PRISME, VTT, LLNL
- Ceiling jet: ATF_Corridors, Vettori_Flat_Ceiling, Vettori_Sloped_Ceiling
- Velocity / tunnels: Memorial_Tunnel, Arup_Tunnel, Wu_Bakar_Tunnels, Bryant_Doorway
- Heat flux: Fleury, NRCC_Facade, FM_Vertical_Wall_Flames, Lattimer_*
- Suppression: Vettori_*, Bittern, UL_NFPRF, USCG_HAI, BRE_Spray, VTT_Sprays
- Burning rate: Pool_Fires, NIST_Pool_Fires, Waterloo_Methanol, wood cribs
- Pyrolysis: FAA_Polymers, NIST_Polymers, UMD_Polymers, Aalto_Woods, Kashiwagi
- Vegetation / WUI: CSIRO_Grassland_Fires, Crown_Fires, USFS_*, NIST_Douglas_Firs
- Wind: Askervein_Hill, UWO_Wind_Tunnel
- LNG / jets: LNG_Dispersion, Montoir, Sandia_Jet_Fires, Loughborough_Jet_Fires

Namelist patterns to copy (already wired)
- Specified HRR: &SURF HRRPUA + TMP_FRONT (McCaffrey, Steckler) → add_hrr_fire
- Circular pools: &VENT RADIUS, XYZ → add_hrr_fire(radius=...)
- Line trees: &DEVC XB + POINTS (McCaffrey) → add_line_device
- TIME_SHRINK_FACTOR on &TIME (Steckler) → set_time_shrink
- Vegetation: &PART STATIC + &INIT N_PARTICLES_PER_CELL, PACKING_RATIO (CSIRO) → add_vegetation_bed
- Wind: &WIND SPEED, DIRECTION, L, Z_0 (CSIRO) → set_wind
- Door/window: &HOLE through a wall (Steckler) → add_hole
- Sprinklers: &PROP QUANTITY='SPRINKLER LINK TEMPERATURE' → add_sprinkler
- Smoke alarms: &PROP QUANTITY='CHAMBER OBSCURATION' → add_smoke_detector
"""
