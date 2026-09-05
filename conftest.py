# Empty on purpose: its presence at the repo root makes pytest add the root
# (where core.py lives) to sys.path before collecting tests/, regardless of
# how pytest is invoked (bare `pytest` vs `python -m pytest`) or the CWD.
