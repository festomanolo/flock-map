# Full reproduction:  make reproduce   (~25 min on 4 cores)
PY=python3
.PHONY: extra cfd docx reproduce test audit control reconfig aero mission sensitivity analyse numbers figures paper clean
reproduce: audit freewake aero control reconfig mission sensitivity analyse extra cfd numbers figures figures3d paper docx
test:
	$(PY) -m pytest -q tests
audit:
	$(PY) audit/original_reproduction.py > /dev/null
freewake:
	$(PY) experiments/run_freewake.py && $(PY) experiments/run_freewake_core.py
aero:
	$(PY) experiments/run_aero.py
control:
	$(PY) experiments/run_control.py
reconfig:
	$(PY) experiments/run_reconfig.py
mission:
	N_MISSION=200 $(PY) experiments/run_mission.py
sensitivity:
	$(PY) experiments/run_sensitivity.py
analyse:
	$(PY) experiments/analyse.py
extra:
	$(PY) experiments/run_extra.py dz kmap ctl tor skerr cov power
cfd:
	cd cfd && $(PY) run_all.py && cd .. && $(PY) cfd/analyze_cfd.py && $(PY) figures/fig_cfd.py && xvfb-run -a $(PY) cfd/render_cfd.py
numbers:
	$(PY) experiments/make_numbers.py && $(PY) experiments/make_numbers_extra.py && $(PY) experiments/make_cfd_section.py
figures:
	$(PY) figures/fig_aero.py && $(PY) figures/fig_mission.py && $(PY) figures/fig_extra.py && cp figures/out/*.pdf figures/out/*.png manuscript/figures/
figures3d:
	$(PY) experiments/run_3d_cases.py && xvfb-run -a -s "-screen 0 2700x1700x24" $(PY) figures/fig3d.py wake rollup vorticity safety split camera coverage3d mission && xvfb-run -a $(PY) figures/anim3d.py && cp figures/out3d/*.png manuscript/figures/
docx:
	cd manuscript && $(PY) make_docx.py
paper:
	cd manuscript && latexmk -pdf -interaction=nonstopmode main.tex
clean:
	rm -rf figures/out manuscript/*.aux manuscript/*.log manuscript/*.bbl manuscript/*.blg manuscript/*.fls manuscript/*.fdb_latexmk
