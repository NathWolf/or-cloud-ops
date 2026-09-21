#!/usr/bin/env python3
"""Verify release completeness, reference checksums and public input integrity."""
import csv
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'artifacts/revision_2026_09_21'


def main():
    required = [
        'LICENSE', 'CITATION.cff', 'THIRD_PARTY_NOTICES.md', 'README.md',
        'requirements-revision.txt', 'data/public/README.md',
        'data/public/carbon_2024.csv', 'data/public/provenance.json',
        'src/models/hierarchical.py', 'src/contract_audit.py',
        'scripts/run_all.py', 'scripts/verify_revision.py',
        'scripts/export_revision.py', 'scripts/run_commitment_review.py',
        'artifacts/commitment_review_2026_09_21/SHA256SUMS.json', '.github/workflows/reproducibility.yml',
    ]
    for name in required:
        if not (ROOT / name).is_file():
            raise SystemExit(f'Missing release file: {name}')
    expected = json.loads((ARCHIVE / 'SHA256SUMS.json').read_text())
    actual = {
        str(p.relative_to(ARCHIVE)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ARCHIVE.rglob('*')
        if p.is_file() and p.name != 'SHA256SUMS.json'
    }
    if actual != expected:
        changed = sorted(k for k in actual.keys() | expected.keys()
                         if actual.get(k) != expected.get(k))
        raise SystemExit(f'Reference archive differs from its manifest: {changed}')
    source = ROOT / 'data/public/carbon_2024.csv'
    audit = json.loads((ARCHIVE / 'audit_manifest.json').read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest() != audit['public_data_sha256']:
        raise SystemExit('Carbon input differs from the source used in the archived run')
    with source.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 8 or any(row['year'] != '2024' or row['unit'] != 'gCO2/kWh' for row in rows):
        raise SystemExit('Unexpected public input dimensions or units')
    if (ROOT / '.git').exists():
        tracked = subprocess.check_output(
            ['git', 'ls-files', '-z'], cwd=ROOT, text=True).split('\0')
        forbidden = {'editor_email.md', 'response_to_reviewers_draft.md',
                     'EJDP_revision_blueprint.md'}
        leaked = [p for p in tracked if Path(p).name in forbidden
                  or Path(p).suffix in {'.lic', '.pem', '.key'}
                  or Path(p).name.startswith('.env')]
        if leaked:
            raise SystemExit(f'Private/local files are tracked: {leaked}')
    print(f'PASS: {len(actual)} reference files, eight source observations, '
          'required release files and tracked-file exclusions')


if __name__ == '__main__':
    main()
