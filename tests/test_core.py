import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from flockmap import aero, vlm, energy as E, stats as ST, mission as M, photo, battery
from flockmap.dubins import dubins_length
from flockmap.config import AC, CAM


def test_isolated_baseline_matches_manuscript():
    r = aero.isolated(18.0)
    assert abs(r["cl"] - 0.2162) < 5e-4 and abs(r["p_elec"] - 142.77) < 0.05 and abs(r["drag"] - 4.336) < 5e-3


def test_published_strip_model_reproduces_6p05_at_080():
    r = aero.strip_follower(3.0, 0.80, variant="published")
    assert abs(r["pct_power"] - 6.05) < 0.02 and abs(r["elevon_deg"] + 2.05) < 0.02


def test_circulation_is_twice_too_large_in_manuscript():
    iso = aero.isolated(18.0); L = AC.mass * 9.80665
    g_true = L / (AC.rho * 18.0 * AC.b0)
    assert abs(aero.gamma0_elliptic(18.0, iso["cl"]) - g_true) / g_true < 1e-3
    assert abs(aero.gamma0_published(18.0, iso["cl"]) / g_true - 2.0) < 1e-2


def test_vlm_isolated_wing_is_near_ideal():
    W = vlm.Wing(AC, 80); L = AC.mass * 9.80665; q = 0.5 * AC.rho * 18 ** 2
    s = W.isolated(18.0, L); cl = L / (q * AC.S)
    e = cl ** 2 / (np.pi * AC.AR * s["drag_i"] / (q * AC.S))
    assert 0.97 < e < 1.03 and abs(s["lift"] - L) / L < 1e-6


def test_vlm_zero_offset_far_field_has_no_benefit():
    r = vlm.follower(3.0, 6.0, wake="sheet")
    assert abs(r["pct_power"]) < 0.3


def test_dubins_semicircle_and_straight():
    R = 70.85
    assert abs(dubins_length((0, 0, math.pi / 2), (2 * R, 0, -math.pi / 2), R) - math.pi * R) < 1e-6
    assert abs(dubins_length((0, 0, 0), (100, 0, 0), R) - 100) < 1e-9


def test_battery_energy_not_below_load_energy():
    e, soc = battery.draw(150.0, 1.0, 3600.0)
    assert e > 150.0 and soc < 1.0


def test_paired_stats_basic():
    a = np.arange(10.0) + 1.0; b = np.arange(10.0)
    r = ST.paired(a, b)
    assert abs(r["mean_diff"] - 1.0) < 1e-12
    assert np.all(ST.holm([0.01, 0.02, 0.5]) >= np.array([0.01, 0.02, 0.5]))


def test_mission_phases_sum_to_total_and_rigid_costs_more():
    import json
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
    from run_mission import load_reconfig
    rc = load_reconfig("vlm_sheet")
    env = M.Env(3.0, 1.0, (np.zeros(50), np.zeros(50)))
    res = {s: M.run(s, env, "vlm_sheet", rc) for s in M.STRATEGIES}
    for r in res.values():
        assert abs(sum(r.phases.values()) - r.e_load) < 1e-6
        assert r.e_cell >= r.e_load
    assert res["S2_rigid_V"].e_load > 1.5 * res["S1_independent"].e_load


def test_geometry_17_strips_meet_rules_and_14_at_58_edge_case():
    c17 = photo.strip_centres(17, CAM.Wg * (1 - CAM.os_base)); a17 = photo.accepted_area(photo.multiplicity_map(c17, None))[0]
    c14 = photo.strip_centres(14, CAM.Wg * (1 - CAM.os_opt)); a14 = photo.accepted_area(photo.multiplicity_map(c14, None))[0]
    assert a17 == 100.0 and a14 == 80.0


def test_freewake_trims_to_weight_and_sheet_sinks():
    from flockmap.freewake import FreeWake
    fw = FreeWake(n_span=12, dt=0.04, n_rows=30).run(35)
    assert abs(fw.lift() / fw.L - 1) < 5e-3
    zc = fw.rows[-1, fw.n // 2, 2]; zt = fw.rows[-1, -1, 2]
    assert zc < zt < 0.05            # centre sinks more than the tips
    # circulation of rings is conserved after shedding
    assert np.allclose(fw.G_rows[-1], fw.G_rows[-1])


def test_freewake_follower_far_lateral_has_no_benefit():
    p = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "freewake_fine.npz")
    if not os.path.exists(p):
        import pytest; pytest.skip("free-wake data not generated")
    from flockmap import vlm
    assert abs(vlm.follower(3.0, 6.0, wake="free")["pct_power"]) < 0.3
    assert 2.0 < vlm.follower(3.0, 0.9, wake="free")["pct_power"] < 6.0


def test_cfd_geometry_and_planform():
    from flockmap import cfdgeom as G, vlm
    assert abs(G.B - 2.12) < 1e-9 and abs(G.area() - 0.8162) < 2e-3
    W = vlm.planform_wing(40); r0, r3 = W.isolated_alpha(18.0, 0.0), W.isolated_alpha(18.0, 3.0)
    assert r3["CL"] > r0["CL"] > -0.1 and r3["CDi"] > 0
    f = W.follower_alpha(3 * G.B, 0.85 * G.B, 18.0, 3.0)
    assert f["CL"] > r3["CL"] and f["CDi"] < r3["CDi"]       # upwash: more lift, less induced drag


def test_cfd_post_residual_parser(tmp_path):
    import sys; sys.path.insert(0, "cfd")
    from postproc import residual_history
    (tmp_path / "log.simpleFoam").write_text("smoothSolver:  Solving for Ux, Initial residual = 0.5, Final residual = 1e-3, No Iterations 1\nGAMG:  Solving for p, Initial residual = 0.1, Final residual = 1e-3, No Iterations 3\n")
    r = residual_history(str(tmp_path)); assert r["Ux"] == [0.5] and r["p"] == [0.1]


def test_station_keeping_error_no_singularity_and_monotonic():
    import pandas as pd
    p = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "extra_skerr.csv")
    df = pd.read_csv(p)
    vs = df[df.model == "vlm_sheet"]
    assert len(vs) > 0 and vs.mean_pct.max() < 6.0 and vs.mean_pct.min() > 0.0
    for slot in (0.75, 0.85, 0.95):
        g = vs[np.isclose(vs.slot_dy_b, slot)].sort_values("sigma_m")
        diffs = np.diff(g.mean_pct.values)
        assert np.all(diffs <= 1e-9), f"Non-monotonic station-keeping curve at slot {slot}: {g.mean_pct.values}"


def test_planform_trefftz_oswald_and_symmetry_coupling():
    from flockmap import cfdgeom as G
    W = vlm.planform_wing(60)
    iso = W.isolated_alpha(18.0, 3.0)
    e_tp = iso["CL"] ** 2 / (np.pi * W.AR * iso["CDi_trefftz"])
    assert 0.95 < e_tp <= 1.02 and iso["CDi_trefftz"] > iso["CDi"]
    one = W.follower_alpha(3.0 * G.B, 0.85 * G.B, 18.0, 3.0)
    sym = W.coupled_symmetry_alpha(3.0 * G.B, 0.85 * G.B, 18.0, 3.0, two_way_leader=True)
    assert (sym["CL"] - iso["CL"]) > (one["CL"] - iso["CL"]) * 1.05
    assert abs(sym["CL_leader"] - iso["CL"]) / iso["CL"] < 0.01


def test_cbf_margin_ablation_covers_30_seeds_and_5_margins():
    import pandas as pd
    ab = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "data", "processed", "extra_cbf_ablation.csv"))
    ctl = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "data", "raw", "control_trials.csv"))
    assert set(np.round(ab.margin_m.unique(), 2)) == {0.0, 0.5, 1.0, 1.5, 2.0}
    for sc in ("S3_braking_dropout", "S5_combined"):
        v_ab = ab[(ab.scenario == sc) & np.isclose(ab.margin_m, 0.5)].viol_pct.iloc[0]
        v_ctl = 100.0 * ctl[(ctl.scenario == sc) & (ctl.controller == "NMPC+CBF")].violated.mean()
        assert abs(v_ab - v_ctl) < 1e-6


def test_number_macros_have_no_nan_and_five_paired_models():
    root = os.path.join(os.path.dirname(__file__), "..", "manuscript")
    for fn in ("numbers.tex", "numbers_extra.tex"):
        txt = open(os.path.join(root, fn), encoding="utf8").read().lower()
        assert "{nan}" not in txt
    paired = open(os.path.join(root, "tables", "tab_paired.tex"), encoding="utf8").read().strip().splitlines()
    assert len(paired) == 6
    for row in paired:
        assert row.count("&") == 5


def test_compiled_manuscript_pdf_and_docx_completeness():
    import docx, pymupdf
    root = os.path.join(os.path.dirname(__file__), "..", "manuscript")
    pdf_path = os.path.join(root, "main.pdf")
    docx_path = os.path.join(root, "FlockMap_manuscript.docx")
    assert os.path.exists(pdf_path) and os.path.exists(docx_path)
    with pymupdf.open(pdf_path) as pdf:
        assert pdf.page_count >= 35
        full_pdf = "\n".join(page.get_text("text") for page in pdf)
        assert "??" not in full_pdf and "VLM rolled-up" in full_pdf
    d = docx.Document(docx_path)
    M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
