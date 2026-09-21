# Contributing

Please use GitHub issues for reproducibility problems and pull requests for proposed changes. Include the command, Python and dependency versions, and a minimal example. Remove credentials and private operator data from logs before posting them.

Keep scientific changes separate from formatting changes. Document any changes to model assumptions, accounting boundaries, risk interpretation or expected outcomes. Preserve the frozen reference archive; write new experiments to a different output directory.

Before proposing a change, run `python scripts/check_release.py` and `python scripts/verify_revision.py artifacts/revision_2026_09_21`. For model changes, also run the smoke test and the full affected experiments, comparing numerical outcomes and independent residuals. Figure changes should retain the shared typography and palette in `scripts/export_revision.py`.

Original code contributions are made under the repository's MIT license. Third-party data retain their own terms. Please retain scientific attribution when adapting the study.
