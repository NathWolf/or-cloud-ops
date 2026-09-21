# Experiment guide

Run commands from the repository root. The frozen reference archive is `artifacts/revision_2026_09_21/`; new runs belong in `results/`.

## Workflow

| Step | Command | Main output |
| --- | --- | --- |
| Main experiment grid | `python scripts/run_hierarchical_experiments.py --require-public-data --output-dir results/revision_2026_09_21` | Regimes, price/cap sweeps, accounting comparisons and saved solutions |
| Contract and uncertainty audit | `python scripts/run_revision_audit.py --results-dir results/revision_2026_09_21` | Frozen-plan, scenario-wise, stress and seed tests |
| Independent checks | `python scripts/verify_revision.py results/revision_2026_09_21` | Fail-fast residual, objective and comparison assertions |
| Commitment revisions | `python scripts/run_commitment_review.py --reference-dir results/revision_2026_09_21 --output-dir results/commitment_review` | Five revision scopes across ten demand variants |
| Target-excess diagnostics | `python scripts/run_handoff_diagnostics.py --reference-dir results/revision_2026_09_21 --output-dir results/handoff_diagnostics` | Joint minimum-excess allocations for five reference scopes |
| Figure/table export | `python scripts/export_revision.py --results-dir results/revision_2026_09_21 --commitment-dir results/commitment_review --diagnostic-dir results/handoff_diagnostics --output-dir results/reproduced_figures` | Two main figures and one supplementary figure with plotted-value CSVs, five tables and numerical LaTeX macros |

`python scripts/run_all.py --figure-dir results/reproduced_figures` runs the complete pipeline. `--quick` uses a smaller instance and does not run the full audit or export figures. Its results do not support the manuscript's numerical claims.

## Reference results

| Quantity | Reference value |
| --- | ---: |
| Expected-target cost premium over cost-only | 2.729% |
| Frozen cost-only plan under expected targets | Infeasible |
| Expected-plan worst carbon / target | 1.248 |
| Expected-plan worst seasonal water / target | 1.259 |
| Scenario-wise cost premium | 26.428% |
| Frozen scenario-wise plan after 5% demand increase | Infeasible |
| Expected-target premium over seeds 11–20 | 2.495–2.729% |

These are rounded summaries of the archived CSV files. Costs are normalized planning units, not operator expenditures. The scenario-wise plan is certified only for the modeled scenarios. The saved internal-price pair `(0, 5)` meets the expected targets; finite price sampling is not a global equivalence or impossibility proof.

## Archive contents and verification

- `instance.json` stores all input values and scenario probabilities.
- `solutions/` stores decisions, impacts, objectives, solver statuses and bound/gap metadata. There are 78 feasible saved solutions and two recorded infeasible solutions.
- `planning_regime_comparison.csv`, `cap_sweep.csv` and `supplement/` contain the primary comparisons.
- `handoff_audit.csv`, `stress_tests.csv` and `seed_sensitivity.csv` contain contract and uncertainty tests.
- `audit_manifest.json` records the reference environment, solver settings and source/data checksums. In the public copy, the machine hostname is omitted and the audit-script path is repository-relative. The original manifest's checksum records this publication transformation. No numerical values were changed.
- `SHA256SUMS.json` checks the integrity of every other file in the reference archive.

The original audit source hashes identify the files used for the September 2026 run. Release tooling and documentation can evolve without changing those original hashes. To compare a new run, prioritize objectives, feasibility and impacts rather than timestamps, runtime or a particular alternative optimum. Verification of saved infeasible statuses is not an independent proof of infeasibility; rerun the solver to reproduce that result.

## Scope

The experiment contains eight site zones, six demand regions, four equal-duration seasonal periods, three scenarios and two workload classes. First-stage sites, capacity and link activation are shared across scenarios. Recourse has perfect information within each scenario. Links use distance-based eligibility, and no interperiod workload deferral or endogenous network topology is modeled.

Carbon factors come from Ember; operational inputs are constructed. Water is assumed direct water use. Procurement discounts are hypothetical. The experiment tests how infrastructure choices constrain workload allocation. It does not reconstruct OVHcloud operations or measure organizational effectiveness.

## Reading the figures

1. **Supplementary Figure S1, infrastructure and allocation:** paired points compare cost-only and expected-target capacity commitments and training allocations by city. Capacity is per period; training allocation is the expected total across four periods. The selected sites and inference allocations are unchanged.
2. **Main Figure 1, cost and target interpretation:** four rows compare cost-only, expected-target, internal-price and scenario-wise plans. Cost excludes internal impact charges. Target-use points show expected and worst-scenario ratios; water additionally takes the maximum over seasons. Connecting lines are comparisons, not statistical uncertainty intervals.
3. **Main Figure 2, carbon and water trade-offs:** the carbon-only sweep and joint expected-target plan are plotted against achieved carbon reduction. Water use can rise under a carbon-only limit. Lines between solved plans do not establish feasibility at intermediate values.

The exporter writes `figure_commitments.csv`, `figure_target_use.csv` and `figure_tradeoffs.csv` with the plotted values. It recomputes scenario-water ratios from saved flows and checks the target ratios against the archived audit. Figures retain the same filenames so manuscript builds remain reproducible.

## Which commitments need revision?

`python scripts/run_commitment_review.py --output-dir results/commitment_review` solves five cases for each of seeds 11–20: allocation only; capacity plus allocation; links plus allocation; capacity and links plus allocation with sites fixed; and unrestricted planning. Every case retains the same service obligations and expected carbon/seasonal-water targets. The cost-only solution supplies all fixed values. Costs are pre-approval planning costs, not retrofit costs; sunk and conversion costs are excluded.

The reference is `artifacts/commitment_review_2026_09_21/`. Local Gurobi 12.0.3 and OVH Gurobi 13.0.2 agree on all 50 statuses and on feasible objective values within 1e-8. Neither capacity nor links alone restores feasibility in any seed. Reopening both reaches the unrestricted optimum without changing sites. In the reference solution, four links are added and three removed; the net link count masks this revision.

Verify saved cases with `python scripts/run_commitment_review.py --verify-only --output-dir artifacts/commitment_review_2026_09_21`. This recomputes residuals and targets, checks fixed decisions and the objective ordering under nested revision scopes, and verifies checksums. Infeasible statuses still require solving to reproduce. The full `run_all.py` pipeline includes these tests; `export_revision.py --commitment-dir PATH` selects their outputs for the main table. The original September experiment archive is unchanged.

## Interpreting the commitment table

“Runs meeting targets” counts feasible planning problems, not successful software executions. A seed selects a reproducible demand perturbation of at most 1.5%; it is not a separate observed network. For each seed, the cost-only solution supplies the fixed commitments and the reference impacts. Every revision case must serve the same demand while reducing expected carbon by 15% and expected water by 10% in each season. These reductions are illustrative stress-test levels, not policy or operator targets.

- **Allocation only:** sites, capacity and links remain fixed. No compliant allocation exists in any of the ten runs.
- **Capacity and allocation:** links remain fixed, so more capacity cannot create access to another site. All ten cases are infeasible.
- **Links and allocation:** site capacities remain fixed, so additional links cannot increase the receiving site's capacity. All ten cases are infeasible.
- **Capacity, links and allocation:** sites remain fixed. All ten cases meet the targets and attain the unrestricted planning cost.
- **All decisions:** all infrastructure choices can change. All ten cases meet the targets; allowing site changes brings no further cost reduction.

The saved infeasible cases have solver status 3 (`INFEASIBLE`), not a time-limit status. The result identifies a restricted revision scope that cannot meet the chosen targets. It does not establish that both types of revision are necessary for every network or target.

## Minimum-excess feedback

The diagnostic keeps service and physical constraints hard, retains commitments outside the permitted revision scope, and minimizes the sum of carbon and four seasonal-water excesses divided by their respective targets. All five terms have equal weight. Cost is not the diagnostic objective. Reported components belong to one joint optimum; they are not separately minimized lower bounds.

With allocation alone or capacity plus allocation, carbon exceeds its target by 17.65% and each water target by 11.11%; the dimensionless sum is 0.620915. Revising links plus allocation lowers the sum to 0.281460: carbon excess is 11.85%, and seasonal water excesses are 3.00%, 4.34%, 6.88% and 2.07%. Reopening capacity and links, or all decisions, gives zero. These reference-instance results supply feedback for a rejected handoff; they do not relax the acceptance targets.

```sh
python scripts/run_handoff_diagnostics.py --verify-only --output-dir artifacts/handoff_diagnostics_2026_09_21
python scripts/run_handoff_diagnostics.py --output-dir results/handoff_diagnostics
```

The five saved solutions, CSV, source/input hashes and checksums are in `artifacts/handoff_diagnostics_2026_09_21/`. Local Gurobi 12.0.3 and Linux Gurobi 13.0.2 agree on the joint objective and each excess component to within 1.3e-15. Verification reconstructs impacts, checks service residuals and retained commitments, and compares the excess sum with the recorded objective. It does not independently prove optimality without rerunning the solver. Use `export_revision.py --diagnostic-dir PATH` to select diagnostic outputs for the manuscript table.

## Assumed accounting-factor reductions

The accounting sensitivity multiplies each original site carbon factor by the factor below, in every season and scenario. For example, Paris uses 0.74 times its original factor, a 26% reduction. The table names the sites explicitly; no positional ordering is needed.

| Site ID | Representative city | Multiplier | Assumed reduction |
| --- | --- | ---: | ---: |
| C1 | Paris | 0.74 | 26% |
| C2 | Frankfurt | 0.78 | 22% |
| C3 | Amsterdam | 0.76 | 24% |
| C4 | Dublin | 0.72 | 28% |
| S1 | Stockholm | 0.42 | 58% |
| S2 | Warsaw | 0.70 | 30% |
| S3 | Madrid | 0.55 | 45% |
| S4 | Helsinki | 0.40 | 60% |

These exact multipliers are hard-coded illustrative assumptions in `make_public_calibrated_hierarchical_instance`; they are not estimated from Ember data, procurement contracts or OVHcloud records. No empirical interpretation attaches to their ordering or differences. They must not be interpreted as measured renewable-electricity shares or verified market-based Scope 2 factors.

The comparison asks whether changing the accounting coefficients changes the plan's apparent compliance under the same numerical carbon cap. It holds demand and physical constraints fixed, reoptimizes under the chosen coefficients, and then evaluates each solution with the original seasonal coefficients. The reduced-factor cases recover the cost-only plan. This illustrates dependence on accounting definitions; it does not demonstrate procurement effectiveness or measured emissions reductions. Seasonal versus annual averaging is a separate comparison using the original coefficients.

## Input values and scenario construction

The manuscript keeps the setup brief; the complete instance is archived in `artifacts/revision_2026_09_21/instance.json`. The generator is `make_public_calibrated_hierarchical_instance` in `src/models/hierarchical.py`. It stores assumed costs, demand, capacity, water coefficients and eligible links alongside the public carbon inputs.

The eight 2024 Ember observations, retrieved on 21 September 2026, are:

| Country | Representative city | Electricity factor (gCO2/kWh) |
| --- | --- | ---: |
| France | Paris | 40.49 |
| Germany | Frankfurt | 337.12 |
| Netherlands | Amsterdam | 250.72 |
| Ireland | Dublin | 270.91 |
| Sweden | Stockholm | 34.91 |
| Poland | Warsaw | 608.36 |
| Spain | Madrid | 146.22 |
| Finland | Helsinki | 66.75 |

These are electricity-generation lifecycle factors, not site measurements or consumption-adjusted grid factors. Divide by 1000 to obtain kg per assumed 1 kWh service unit. The same assumed facility electricity per service unit applies to every site and workload, including overheads; it is not a measured compute efficiency.

| Representative period | Raw carbon multiplier | Demand multiplier | Water multiplier |
| --- | ---: | ---: | ---: |
| Winter | 1.10 | 1.00 | 0.84 |
| Spring | 0.91 | 1.04 | 0.96 |
| Summer | 1.16 | 1.12 | 1.34 |
| Autumn | 0.96 | 0.98 | 1.00 |

Divide the raw carbon multipliers by their equal-period mean (1.0325). This preserves the public annual factor in the base scenario. Periods have equal duration; costs and impacts are summed over these four blocks without extrapolating annual operator totals.

| Scenario | Assumed probability | Demand multiplier | Carbon multiplier | Water multiplier |
| --- | ---: | ---: | ---: | ---: |
| Low | 0.25 | 0.90 | 0.965 | 1.00 |
| Base | 0.50 | 1.00 | 1.000 | 1.00 |
| High | 0.25 | 1.16 | 1.056 | 1.10 |

The scenario carbon multiplier is `1 + 0.35 * (demand_multiplier - 1)`. Multiply each site's base coefficient by both its period and scenario multipliers. Demand receives an independent uniform multiplicative perturbation between 0.985 and 1.015 for each region, period and scenario; inference and training share that region-period-scenario draw. Seed 11 defines the reference instance; seeds 11–20 define the ten commitment tests. All seasonal/scenario multipliers and probabilities are assumed, not fitted observations.

Inference links are admissible up to 900 km and training links up to 2200 km in great-circle distance. Activation is optimized within that fixed admissible set. No routing, congestion, bandwidth or endogenous network topology is represented. Capacity is service volume per period. Allocation has perfect information about the scenario, and training cannot move between periods.

Base direct-water inputs range from 0.21 to 0.58 litres per service unit (0.1764–0.85492 after period/scenario adjustment); water-stress indices are not converted into water use or permits. Water limits apply to the portfolio in each season, not to individual basins. Prices and costs are arbitrary planning units. These inputs cannot support estimates of operator expenditure, real-world water savings or legal compliance.

## Supporting comparisons and verification

The main text introduces each comparison alongside its results. The archive also retains water-only sweeps, interconnection-cost multipliers of 0.5, 1, 2 and 4, and a diagnostic that minimizes the sum of normalized carbon and seasonal-water excesses under the frozen cost-only plan. Its reference value, 0.621, is a dimensionless sum across constraints, not a percentage of total emissions.

The price grid uses all 49 pairs from `{0, 2, 5, 10, 20, 40, 80}` in planning-cost units per respective impact unit. The representative pair minimizes absolute relative carbon deviation plus mean absolute relative seasonal-water deviation from the targets; compliance is checked separately. Finite sampling does not establish equivalence over the continuous price space.

Primary solves request zero relative MIP gap and one solver thread. Independent checks reconstruct demand satisfaction, site/link feasibility, capacity use, costs and impacts from saved decisions. Source hashes, software versions, solver bounds and times accompany the reference archives. These small instances do not test computational scalability.
