# Quick start

From the repository root, using Python 3.12+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-revision.txt
python scripts/check_release.py
python scripts/verify_revision.py artifacts/revision_2026_09_21
```

The last two commands validate the supplied archive without optimizing. To run a small instance, with a suitable Gurobi license:

```sh
python scripts/run_all.py --quick
```

To run the complete study and generate the figures, install LaTeX as described in [README.md](README.md), then run:

```sh
python scripts/run_all.py --figure-dir results/reproduced_figures
```

New results go under `results/`. The reference manuscript results stay in `artifacts/revision_2026_09_21/`. See [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) for expected outcomes and individual commands.
