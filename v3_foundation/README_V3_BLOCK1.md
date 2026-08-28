# V3 Block 1 — Deterministic Conversation Foundation

This block intentionally contains no Gemini, Instagram, Gmail, Google Sheets,
quote calculation, or deployment code.

Files:
- conversation_models.py
- conversation_events.py
- conversation_state_machine.py
- test_state_machine_v3.py

Run:

```powershell
python -m py_compile conversation_models.py conversation_events.py conversation_state_machine.py test_state_machine_v3.py
python test_state_machine_v3.py
```

Expected final result:

```text
V3 BLOCK 1 STATE MACHINE TEST SUITE PASSED
```

Do not connect this to the live Instagram bot yet.
