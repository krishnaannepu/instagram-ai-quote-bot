# V3 Block 2 — Event Normalizer + Semantic Contract

Block 1 proved deterministic state transitions.

Block 2 proves that UI buttons and future Gemini interpretations cannot take
different business-logic paths.

## New files

- `semantic_contract.py`
  Defines the structured semantic output contract that Gemini must eventually
  satisfy.

- `event_normalizer.py`
  Converts button payloads or semantic interpretations into the same
  `ConversationEvent`.

- `test_event_normalizer_v3.py`
  Validates source-independent events and state-specific constraints.

## Important examples

Button:

```text
PACKAGE_BASIC
```

becomes:

```text
FIELD_VALUE
field=package
value=Basic
```

Future Gemini interpretation for:

```text
basic kardo
```

must become the exact same internal event.

Likewise:

```text
COVERAGE_BOTH
```

and a semantic interpretation of:

```text
both
```

while state is `QUOTE_COVERAGE` both become:

```text
FIELD_VALUE
field=coverage_type
value=Both
```

## Run

```powershell
python -m py_compile conversation_models.py conversation_events.py conversation_state_machine.py semantic_contract.py event_normalizer.py test_state_machine_v3.py test_event_normalizer_v3.py
python test_state_machine_v3.py
python test_event_normalizer_v3.py
```

Do not connect Gemini or deploy yet.

The next block is the state-specific Gemini adapter. Gemini will be required to
produce `SemanticInterpretation`; it will not be permitted to directly mutate
the conversation state.
