#!/usr/bin/env python3
"""Generate an OpenFOAM v1912 case (simpleFoam, k-omega SST, snappyHexMesh) for the X8-class wing study.
   python3 make_case.py <case_dir> --alpha 3 --level 1 [--follower DY_OVER_B DX_OVER_B] [--leader-only]
   level 0/1/2 = coarse/medium/fine mesh.  Half-model: symmetry plane y = 0 through the leader centre line."""
import sys, os, argparse, math, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from flockmap import cfdgeom as G

ap = argparse.ArgumentParser()
ap.add_argument("case"); ap.add_argument("--alpha", type=float, default=3.0); ap.add_argument("--level", type=int, default=1)
ap.add_argument("--follower", nargs=2, type=float, default=None, help="dy/b dx/b of the follower (quarter-chord distance)")
ap.add_argument("--iters", type=int, default=700); ap.add_argument("--procs", type=int, default=3); ap.add_argument("--u", type=float, default=18.0)
ap.add_argument("--wake-box-len", type=float, default=None); ap.add_argument("--write-interval", type=int, default=None); ap.add_argument("--purge", type=int, default=2)
a = ap.parse_args()

case = a.case; os.makedirs(f"{case}/0", exist_ok=True); os.makedirs(f"{case}/constant/triSurface", exist_ok=True); os.makedirs(f"{case}/system", exist_ok=True)
U, NU = a.u, 1.5e-5
B, S, MAC = G.B, G.area(), G.mac()
xqc = float(G.quarter_chord_x(0.0))


def flowframe(tris, shift=(0.0, 0.0, 0.0)):
    t = tris.copy()
    t[..., 0] = -(t[..., 0] - xqc) + shift[0]            # nose toward -x, root quarter chord at x = shift
    t[..., 1] += shift[1]; t[..., 2] += shift[2]
    return t[:, [0, 2, 1], :]                            # flip winding after the reflection

# --- geometry -------------------------------------------------------------------------------------------------
# leader: half wing extended 0.15 m through the symmetry plane so that the plane cuts it cleanly
write_stl_path = f"{case}/constant/triSurface"
G.write_stl(f"{write_stl_path}/leader.stl", flowframe(G.wing_triangles(n_span=70, n_chord=50, half=True, alpha_deg=a.alpha, y_min=-0.15)), "leader")
if a.follower is not None:
    dyb, dxb = a.follower
    fol = G.wing_triangles(n_span=100, n_chord=50, half=False, alpha_deg=a.alpha)
    G.write_stl(f"{write_stl_path}/follower.stl", flowframe(fol, shift=(dxb * B, dyb * B, 0.0)), "follower")

# --- domain / mesh ---------------------------------------------------------------------------------------------
x0, x1 = -8.0, (a.follower[1] * B if a.follower else 0.0) + 22.0
ylo, yhi, zlo, zhi = 0.0, 9.0, -7.0, 7.0
base = 0.5
nx, ny, nz = int(round((x1 - x0) / base)), int(round((yhi - ylo) / base)), int(round((zhi - zlo) / base))
surf_lv = [(4, 5), (5, 6), (6, 7)][a.level]; wake_lv = [2, 3, 3][a.level]; tip = [3, 4, 5][a.level]
near = [((0.02, 5), (0.06, 4), (0.15, 3)), ((0.02, 6), (0.06, 5), (0.15, 4)), ((0.015, 7), (0.04, 6), (0.12, 5))][a.level]
near_s = " ".join(f"({d} {l})" for d, l in near)
wake_len = a.wake_box_len or ((a.follower[1] * B + 6.0) if a.follower else 12.0)

open(f"{case}/system/blockMeshDict", "w").write(f"""FoamFile {{ version 2.0; format ascii; class dictionary; object blockMeshDict; }}
convertToMeters 1;
vertices ( ({x0} {ylo} {zlo}) ({x1} {ylo} {zlo}) ({x1} {yhi} {zlo}) ({x0} {yhi} {zlo}) ({x0} {ylo} {zhi}) ({x1} {ylo} {zhi}) ({x1} {yhi} {zhi}) ({x0} {yhi} {zhi}) );
blocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1) );
edges ();
boundary (
  inlet {{ type patch; faces ((0 4 7 3)); }}
  outlet {{ type patch; faces ((1 2 6 5)); }}
  symmetry {{ type symmetryPlane; faces ((0 1 5 4)); }}
  farfield {{ type patch; faces ((2 3 7 6) (0 3 2 1) (4 5 6 7)); }}
);
mergePatchPairs ();
""")
geoms = "leader.stl"
fol_geo = f"""
    follower.stl {{ type triSurfaceMesh; name follower; }}""" if a.follower else ""
fol_ref = f"""
        follower {{ level ({surf_lv[0]} {surf_lv[1]}); patchInfo {{ type wall; }} }}""" if a.follower else ""
fol_feat = """
        { file "follower.eMesh"; level 6; }""" if a.follower else ""
fol_reg = f"""
        follower {{ mode distance; levels ({near_s}); }}""" if a.follower else ""
loc = f"({x0 + 1.13} 4.07 3.11)"   # off the background-mesh faces (a face-aligned point makes snappyHexMesh fail)
yb = (a.follower[0] * B + B / 2 + 0.9) if a.follower else (B / 2 + 0.9)
box_follow = f"""
    wakeBox {{ type searchableBox; min ({-0.5} 0 -0.45); max ({wake_len} {yb:.3f} 0.45); }}
    tipBox {{ type searchableBox; min ({-0.3} 0.55 -0.30); max ({(wake_len - 3.0) if a.level < 2 else 4.5:.2f} {B/2 + 0.5:.3f} 0.30); }}"""
fol_tip = ""
if a.follower:
    dyb, dxb = a.follower
    fol_tip = f"""
    folBox {{ type searchableBox; min ({dxb*B - 0.4:.3f} {max(0.0, dyb*B - B/2 - 0.35):.3f} -0.30); max ({dxb*B + 3.2:.3f} {dyb*B + B/2 + 0.35:.3f} 0.30); }}"""
open(f"{case}/system/snappyHexMeshDict", "w").write(f"""FoamFile {{ version 2.0; format ascii; class dictionary; object snappyHexMeshDict; }}
castellatedMesh true; snap true; addLayers false;
geometry {{
    leader.stl {{ type triSurfaceMesh; name leader; }}{fol_geo}{box_follow}{fol_tip}
}}
castellatedMeshControls {{
    maxLocalCells 4000000; maxGlobalCells 6000000; minRefinementCells 20; maxLoadUnbalance 0.2; nCellsBetweenLevels 3;
    features ();
    refinementSurfaces {{
        leader {{ level ({surf_lv[0]} {surf_lv[1]}); patchInfo {{ type wall; }} }}{fol_ref}
    }}
    resolveFeatureAngle 30;
    refinementRegions {{
        leader {{ mode distance; levels ({near_s}); }}{fol_reg}
        wakeBox {{ mode inside; levels ((1e15 {wake_lv})); }}
        tipBox {{ mode inside; levels ((1e15 {tip})); }}{"" if not a.follower else chr(10) + "        folBox { mode inside; levels ((1e15 " + str(tip) + ")); }"}
    }}
    locationInMesh {loc}; allowFreeStandingZoneFaces true;
}}
snapControls {{ nSmoothPatch 3; tolerance 2.0; nSolveIter 60; nRelaxIter 5; nFeatureSnapIter 10; implicitFeatureSnap false; explicitFeatureSnap false; multiRegionFeatureSnap false; }}
addLayersControls {{ layers {{}} relativeSizes true; expansionRatio 1.2; finalLayerThickness 0.3; minThickness 0.1; nGrow 0; featureAngle 60; nRelaxIter 3; nSmoothSurfaceNormals 1; nSmoothNormals 3; nSmoothThickness 10; maxFaceThicknessRatio 0.5; maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90; nBufferCellsNoExtrude 0; nLayerIter 50; }}
meshQualityControls {{ maxNonOrtho 70; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80; minVol 1e-15; minTetQuality 1e-15; minArea -1; minTwist 0.02; minDeterminant 0.001; minFaceWeight 0.02; minVolRatio 0.01; minTriangleTwist -1; nSmoothScale 4; errorReduction 0.75; }}
mergeTolerance 1e-6;
""")
# --- fields ----------------------------------------------------------------------------------------------------
I = 0.001; k0 = 1.5 * (U * I) ** 2; om0 = k0 ** 0.5 / (0.09 ** 0.25 * 0.01)
walls = "leader" + (" follower" if a.follower else "")
hdr = lambda c, o: f"FoamFile {{ version 2.0; format ascii; class {c}; object {o}; }}\n"
def wallpatches(body): return "\n".join(f"    {w} {{ {body} }}" for w in walls.split())
open(f"{case}/0/U", "w").write(hdr("volVectorField", "U") + f"""dimensions [0 1 -1 0 0 0 0]; internalField uniform ({U} 0 0);
boundaryField {{ inlet {{ type fixedValue; value uniform ({U} 0 0); }} outlet {{ type zeroGradient; }} symmetry {{ type symmetryPlane; }} farfield {{ type slip; }}
{wallpatches("type noSlip;")} }}
""")
open(f"{case}/0/p", "w").write(hdr("volScalarField", "p") + f"""dimensions [0 2 -2 0 0 0 0]; internalField uniform 0;
boundaryField {{ inlet {{ type zeroGradient; }} outlet {{ type fixedValue; value uniform 0; }} symmetry {{ type symmetryPlane; }} farfield {{ type slip; }}
{wallpatches("type zeroGradient;")} }}
""")
open(f"{case}/0/k", "w").write(hdr("volScalarField", "k") + f"""dimensions [0 2 -2 0 0 0 0]; internalField uniform {k0:.6e};
boundaryField {{ inlet {{ type fixedValue; value uniform {k0:.6e}; }} outlet {{ type zeroGradient; }} symmetry {{ type symmetryPlane; }} farfield {{ type slip; }}
{wallpatches("type kqRWallFunction; value uniform " + f"{k0:.6e};")} }}
""")
open(f"{case}/0/omega", "w").write(hdr("volScalarField", "omega") + f"""dimensions [0 0 -1 0 0 0 0]; internalField uniform {om0:.6e};
boundaryField {{ inlet {{ type fixedValue; value uniform {om0:.6e}; }} outlet {{ type zeroGradient; }} symmetry {{ type symmetryPlane; }} farfield {{ type slip; }}
{wallpatches("type omegaWallFunction; value uniform " + f"{om0:.6e};")} }}
""")
open(f"{case}/0/nut", "w").write(hdr("volScalarField", "nut") + f"""dimensions [0 2 -1 0 0 0 0]; internalField uniform 0;
boundaryField {{ inlet {{ type calculated; value uniform 0; }} outlet {{ type calculated; value uniform 0; }} symmetry {{ type symmetryPlane; }} farfield {{ type slip; }}
{wallpatches("type nutkWallFunction; value uniform 0;")} }}
""")
open(f"{case}/constant/transportProperties", "w").write(hdr("dictionary", "transportProperties") + f"transportModel Newtonian; nu [0 2 -1 0 0 0 0] {NU};\n")
open(f"{case}/constant/turbulenceProperties", "w").write(hdr("dictionary", "turbulenceProperties") + "simulationType RAS; RAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }\n")
open(f"{case}/system/fvSchemes", "w").write(hdr("dictionary", "fvSchemes") + """ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; grad(U) cellLimited Gauss linear 1; }
divSchemes { default none; div(phi,U) bounded Gauss linearUpwindV grad(U); div(phi,k) bounded Gauss upwind; div(phi,omega) bounded Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear; }
laplacianSchemes { default Gauss linear limited corrected 0.33; }
interpolationSchemes { default linear; }
snGradSchemes { default limited corrected 0.33; }
wallDist { method meshWave; }
""")
open(f"{case}/system/fvSolution", "w").write(hdr("dictionary", "fvSolution") + """solvers {
  p { solver GAMG; smoother GaussSeidel; tolerance 1e-8; relTol 0.05; }
  "(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0.1; }
}
SIMPLE { nNonOrthogonalCorrectors 1; consistent yes; residualControl { p 1e-5; U 1e-6; "(k|omega)" 1e-6; } }
relaxationFactors { equations { U 0.9; ".*" 0.9; } }
""")
# NOTE: no function objects -- the Ubuntu v1912 build aborts in functionObjectList (SHA1 stream bug); forces are post-processed in Python
open(f"{case}/system/controlDict", "w").write(hdr("dictionary", "controlDict") + f"""application simpleFoam; startFrom startTime; startTime 0; stopAt endTime; endTime {a.iters}; deltaT 1;
writeControl timeStep; writeInterval {a.write_interval or a.iters}; purgeWrite {a.purge}; writeFormat binary; writePrecision 8; timeFormat general; timePrecision 6; runTimeModifiable false;
""")
open(f"{case}/system/decomposeParDict", "w").write(hdr("dictionary", "decomposeParDict") + f"numberOfSubdomains {a.procs}; method simple; simpleCoeffs {{ n ({a.procs} 1 1); delta 0.001; }}\n")
open(f"{case}/system/meshQualityDict", "w").write("#includeEtc \"caseDicts/meshQualityDict\"\n")
open(f"{case}/case.json", "w").write(__import__("json").dumps(dict(alpha=a.alpha, level=a.level, follower=a.follower, iters=a.iters, U=U, S=S, MAC=MAC, b=B, xqc=xqc), indent=1))
print("case written:", case, "base cells", nx * ny * nz, "domain x", x0, x1)
