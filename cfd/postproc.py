#!/usr/bin/env python3
"""Post-process an OpenFOAM v1912 case without function objects (the Ubuntu build crashes in functionObjectList: SHA1 stream bug).
Forces are integrated from the patch fields exported by foamToVTK:
   F_pressure = rho * sum( p * n * A )                     (n = outward normal of the fluid domain = into the body)
   F_viscous  = rho * sum( (nu + nut_w) * U_t / y * A )    (wall-function shear, same expression as OpenFOAM's nuEff*snGrad(U))
where y is the wall-normal distance of the owner-cell centre and U_t the tangential cell velocity.
"""
import sys, os, json, glob, subprocess, math
import numpy as np
import pyvista as pv

ENV = os.path.join(os.path.dirname(__file__), "env.sh")


def sh(cmd, cwd):
    return subprocess.run(f"source {ENV}; {cmd}", shell=True, cwd=cwd, executable="/bin/bash", capture_output=True, text=True)


def times(case):
    root = os.path.join(case, "processor0") if os.path.isdir(os.path.join(case, "processor0")) else case
    ts = []
    for d in os.listdir(root):
        try:
            t = float(d)
            if t > 0: ts.append(t)
        except ValueError: pass
    return sorted(ts)


def export_vtk(case, patches=("leader",), time=None):
    tsel = "-latestTime" if time is None else f"-time '{time:g}'"
    if os.path.isdir(os.path.join(case, "processor0")):
        sh(f"reconstructPar {tsel}", case)
    sh(f"rm -rf VTK; foamToVTK {tsel} -fields '(p U nut)' -patches '(" + " ".join(patches) + ")'", case)
    d = [x for x in glob.glob(os.path.join(case, "VTK", "*_*")) if os.path.isdir(x)]
    return sorted(d)[-1]


def patch_forces(vtkdir, patch, rho=1.225, nu=1.5e-5, cofr=(0, 0, 0), internal=None):
    P = pv.read(os.path.join(vtkdir, "boundary", f"{patch}.vtp"))
    I = internal if internal is not None else pv.read(os.path.join(vtkdir, "internal.vtu"))
    P = P.compute_normals(cell_normals=True, point_normals=False, auto_orient_normals=False, consistent_normals=False, split_vertices=False)
    n = np.asarray(P.cell_data["Normals"]); A = np.asarray(P.compute_cell_sizes(length=False, area=True, volume=False).cell_data["Area"])
    xf = np.asarray(P.cell_centers().points)
    p = np.asarray(P.cell_data["p"]); nut = np.asarray(P.cell_data["nut"])
    ids = np.array([I.find_containing_cell(x - nn * 2e-4) for x, nn in zip(xf, n)])
    ok = ids >= 0
    cc = np.asarray(I.cell_centers().points)[np.where(ok, ids, 0)]
    Uc = np.asarray(I.cell_data["U"])[np.where(ok, ids, 0)]
    y = np.abs(np.einsum("ij,ij->i", cc - xf, n))
    Ut = Uc - np.einsum("ij,ij->i", Uc, n)[:, None] * n
    tau = ((nu + nut) / np.maximum(y, 1e-9))[:, None] * Ut
    Fp = rho * (p[:, None] * n * A[:, None]); Fv = rho * (tau * A[:, None])
    Fp[~ok] = 0; Fv[~ok] = 0
    r = xf - np.asarray(cofr)
    Mp = np.cross(r, Fp).sum(0); Mv = np.cross(r, Fv).sum(0)
    utau = np.sqrt(np.linalg.norm(tau, axis=1)); yplus = utau * y / nu
    return dict(Fp=Fp.sum(0).tolist(), Fv=Fv.sum(0).tolist(), F=(Fp + Fv).sum(0).tolist(), M=(Mp + Mv).tolist(), area_wet=float(A.sum()),
                yplus_mean=float(np.average(yplus, weights=A)), yplus_p05=float(np.percentile(yplus, 5)), yplus_p95=float(np.percentile(yplus, 95)),
                n_faces=int(len(A)), frac_owner_found=float(ok.mean()))


def residual_history(case):
    f = os.path.join(case, "log.simpleFoam"); out = {"p": [], "Ux": [], "k": [], "omega": []}
    for line in open(f):
        for k in out:
            if line.startswith(f"smoothSolver:  Solving for {k},") or line.startswith(f"GAMG:  Solving for {k},"):
                try: out[k].append(float(line.split("Initial residual = ")[1].split(",")[0]))
                except Exception: pass
    return out


def sample_plane(vtkdir, x, ys, zs, internal=None):
    I = internal if internal is not None else pv.read(os.path.join(vtkdir, "internal.vtu"))
    I = I.cell_data_to_point_data()
    Y, Z = np.meshgrid(ys, zs, indexing="ij"); pts = np.stack([np.full(Y.size, x), Y.ravel(), Z.ravel()], 1)
    s = pv.PolyData(pts).sample(I)
    U = np.asarray(s.point_data["U"]).reshape(Y.shape + (3,)); valid = np.asarray(s.point_data["vtkValidPointMask"]).reshape(Y.shape)
    return Y, Z, U, valid


def summarize(case, U=18.0, rho=1.225, time=None, tag=""):
    meta = json.load(open(os.path.join(case, "case.json"))); S = meta["S"]; mac = meta["MAC"]; q = 0.5 * rho * U ** 2
    patches = ["leader"] + (["follower"] if meta["follower"] else [])
    vtk = export_vtk(case, patches, time); I = pv.read(os.path.join(vtk, "internal.vtu"))
    out = dict(case=os.path.basename(case.rstrip("/")), meta=meta, n_cells=int(I.n_cells), vtkdir=vtk)
    for pa in patches:
        half = (pa == "leader")
        f = patch_forces(vtk, pa, rho=rho, cofr=(0, 0, 0) if half else (meta["follower"][1] * meta["b"], meta["follower"][0] * meta["b"], 0), internal=I)
        k = 2.0 if half else 1.0                 # half model: double the leader loads
        F = np.array(f["F"]) * k; Fp = np.array(f["Fp"]) * k; Fv = np.array(f["Fv"]) * k; M = np.array(f["M"]) * k
        out[pa] = dict(CL=F[2] / (q * S), CD=F[0] / (q * S), CD_pressure=Fp[0] / (q * S), CD_viscous=Fv[0] / (q * S),
                       Cl_roll=(M[0] / (q * S * meta["b"])), Cm_pitch=M[1] / (q * S * mac), **{k_: f[k_] for k_ in ("yplus_mean", "yplus_p05", "yplus_p95", "n_faces", "frac_owner_found")})
    res = residual_history(case)
    out["residuals_last"] = {k: (v[-1] if v else None) for k, v in res.items()}; out["n_iter"] = len(res["p"])
    json.dump(out, open(os.path.join(case, f"summary{tag}.json"), "w"), indent=1)
    return out


def convergence(case, keep=8):
    """Force coefficients at every saved time (cases run with purge 0): returns list of (iteration, CL, CD) for leader & follower."""
    rows = []
    for t in times(case)[-keep:]:
        r = summarize(case, time=t, tag=f"_t{int(t)}")
        rows.append(dict(iter=int(t), **{f"{p}_{k}": r[p][k] for p in ("leader", "follower") if p in r for k in ("CL", "CD")}))
    json.dump(rows, open(os.path.join(case, "convergence.json"), "w"), indent=1)
    return rows


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "convergence":
        print(convergence(sys.argv[1]))
    else:
        r = summarize(sys.argv[1]); print(json.dumps({k: v for k, v in r.items() if k not in ("meta",)}, indent=1))
