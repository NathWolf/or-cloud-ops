# or-cloud-ops

Reproducible experiments for **Coordinating Sustainability Decisions in Cloud Operations: A Planning Matrix Approach**, by Nathalia Wolf, Luce Brotcorne and Grégory Lebourg.

The framework was developed during doctoral research within the Inria–OVHcloud FrugalCloud partnership. This repository contains the strategic–operational optimization model, experiment scripts, public carbon inputs, saved results and publication figures. The software is available under the [MIT license](LICENSE).

The numerical study is a **constructed planning experiment**, not an operator case study. Eight Ember 2024 national electricity-generation lifecycle factors are loaded into the model. Demand, costs, capacity, water, seasonal variations, scenario probabilities and procurement discounts are explicit assumptions. The carbon metric is not certified Scope 2 accounting; portfolio water targets are not local permits.

## Install

Use Python 3.12 or newer. The pinned environment below was used for independent reproduction with Python 3.12.14 and Gurobi 12.0.3. The archived manuscript run used Python 3.13.12 and Gurobi 13.0.2.

```sh
git clone https://github.com/NathWolf/or-cloud-ops.git
cd or-cloud-ops
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-revision.txt
```

On Windows, activate with `.venv\Scripts\activate` instead. Run subsequent commands from the repository root.

Gurobi is a proprietary dependency and has its own [license requirements](https://www.gurobi.com/academics/). Installing this repository does not grant a Gurobi license. Checking saved solutions does not run the optimizer or require an active solver license. Solving requires a license suitable for the model and use; Gurobi's pip distribution includes a restricted license for small models. Never commit a solver license file or cloud-license credentials.

For publication figures, also install a working LaTeX distribution with Latin Modern fonts, `latex`, `dvipng` and Ghostscript. For example, on Ubuntu:

```sh
sudo apt-get install texlive-latex-base texlive-latex-extra texlive-fonts-recommended cm-super dvipng ghostscript
```

## Check the published numerical evidence

The exact saved results used in the manuscript are included under [`artifacts/revision_2026_09_21/`](artifacts/revision_2026_09_21/). They are separate from newly generated runs.

```sh
python scripts/check_release.py
python scripts/verify_revision.py artifacts/revision_2026_09_21
```

The first command checks archive integrity, required release files and the calibration input. The second recomputes feasibility, objectives and environmental impacts for 78 feasible saved solutions, checks the recorded infeasible statuses, and validates cap, handoff and accounting invariants. It does not re-solve the models or independently prove the saved infeasibility certificates.

To regenerate the three vector figures, tables and numerical LaTeX macros **without solving**:

```sh
MPLCONFIGDIR=results/.mplcache python scripts/export_revision.py \
  --results-dir artifacts/revision_2026_09_21 \
  --output-dir results/reproduced_figures
```

The reference figures are in [`latex/fig/`](latex/fig/), with filenames starting `fig_revision_`. Older tracked figures correspond to the earlier one-period illustration.

## Run the experiments

```sh
python scripts/run_all.py --quick
python scripts/run_all.py --figure-dir results/reproduced_figures
```

The quick command runs a smaller smoke instance under `results/revision_smoke/`; it does not export manuscript figures or replace the reference archive. The full command writes `results/revision_2026_09_21/` and runs:

- Cost-only, expected-target and internal-price regimes, including a 49-pair price grid.
- Carbon and water sweeps, common-cap accounting comparisons and interconnection sensitivity.
- Frozen-infrastructure acceptance and infeasibility diagnosis.
- Scenario-wise environmental constraints, demand stresses and ten demand-perturbation seeds.
- Independent residual checks, tables and consistent vector figures.

Use `--output-dir PATH` and `--figure-dir PATH` to choose output locations. Keep the reference archive unchanged. Exact solver runtimes and alternative optimal allocations can vary across systems; the scientific comparisons are based on objective values, impacts and feasibility. See [the experiment guide](docs/EXPERIMENTS.md) for scripts, outputs and expected results.

## Main findings and interpretation

Anticipating expected environmental targets increases normalized cost by 2.729% in the constructed instance. Freezing the cost-only infrastructure makes those targets infeasible through reallocation alone. Expected compliance still permits approximately 25% exceedance in the high scenario; scenario-wise targets increase cost by 26.428%. The sampled internal-price pair `(0, 5)` meets both expected targets, so a general failure of internal pricing is not claimed. Interval abatement costs are finite differences, while LP duals are conditional on fixed sites, links **and capacity**.

The main regime, carbon sweep, handoff and seed results were reproduced locally and on a Linux server to an absolute difference below 1e-10. This is a consistency check, not a solver-performance comparison. The study tests environmental decision interfaces; it does not measure organizational effectiveness or comprehensive sustainability.

## Repository contents

| Path | Purpose |
| --- | --- |
| `src/models/hierarchical.py` | Two-stage strategic–operational MILP and input construction |
| `src/contract_audit.py` | Frozen contracts, diagnostic excess and independent residuals |
| `src/analysis_hierarchical.py` | Numerical summaries and experiment comparisons |
| `scripts/run_all.py` | Complete reproduction entry point |
| `scripts/verify_revision.py` | Verification of saved solutions without solving |
| `scripts/export_revision.py` | Publication figures, tables and numerical macros |
| `data/public/` | Eight frozen public observations, attribution and provenance |
| `artifacts/revision_2026_09_21/` | Reference instance, solutions, tables and manifests |
| `.github/workflows/reproducibility.yml` | Archive verification, smoke solve and figure-export checks |

Earlier one-period CFLP scripts are retained for research history. They are not used to produce the current manuscript results. Private editorial correspondence and working manuscript files are excluded from this code release.

## Data, licensing and citation

The original code and accompanying software documentation are MIT-licensed. The included Ember data retain **CC BY 4.0**, with attribution and transformations described in [`data/public/README.md`](data/public/README.md). Gurobi and other installed dependencies retain their own licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Use [CITATION.cff](CITATION.cff) to cite the software and associated manuscript. The manuscript is under revision; no publication DOI or acceptance is implied. Scientific citation is requested, not an additional condition on the MIT license.
