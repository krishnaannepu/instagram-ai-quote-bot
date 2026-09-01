"""
Run every V3 regression suite. Green here means safe to deploy.

    python run_regressions.py
"""

import subprocess
import sys

SUITES = [
    "test_production_screenshot_regression_v3.py",
    "test_production_defect_hotfix_v3.py",
    "test_change_and_status_v3.py",
    "test_service_correction_v3.py",
    "test_idle_entry_v3.py",
    "test_change_request_v3.py",
    "test_contract_coverage_v3.py",
    "test_full_turn_matrix_v3.py",
    "test_finish_anywhere_v3.py",
]

failed = []

for suite in SUITES:
    print(f"\n{'=' * 72}\n{suite}\n{'=' * 72}")

    result = subprocess.run(
        [sys.executable, suite],
        capture_output=True,
        text=True,
    )

    print(result.stdout, end="")

    if result.returncode != 0:
        print(result.stderr, end="")
        failed.append(suite)

print(f"\n{'=' * 72}")

if failed:
    print(f"FAILED: {', '.join(failed)}")
    sys.exit(1)

print(f"ALL {len(SUITES)} V3 REGRESSION SUITES PASSED")
print("=" * 72)
