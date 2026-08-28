from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

TESTS = [
    "test_state_machine_v3.py",
    "test_event_normalizer_v3.py",
    "test_gemini_semantic_adapter_v3.py",
    "test_semantic_pipeline_v3.py",
    "test_block4_offline_safety_v3.py",
    "test_block6_offline_business_v3.py",
    "test_block9_postquote_email_v3.py",
    "test_instagram_sender_compat_v3.py",
    "test_block10_handoff_semantic_contract_v3.py",
    "test_block10_handoff_callback_v3.py",
    "test_block11_greeting_contract_v3.py",
    "test_block11_welcome_v3.py",
    "test_block11_webhook_boundary_v3.py",
    "test_block11_main_cutover_contract_v3.py",
    "test_block11_fastapi_v3.py",
]


for test_name in TESTS:
    print()
    print("=" * 72)
    print(test_name)
    print("=" * 72)

    result = subprocess.run(
        [
            sys.executable,
            test_name,
        ],
        cwd=str(BASE_DIR),
    )

    if result.returncode != 0:
        raise SystemExit(
            result.returncode
        )


print()
print("=" * 72)
print("CURRENT V3 OFFLINE REGRESSION SUITE PASSED")
print("=" * 72)
