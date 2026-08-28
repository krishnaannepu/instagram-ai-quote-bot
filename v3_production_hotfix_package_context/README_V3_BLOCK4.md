# V3 Block 4 — Controlled Live Gemini Smoke Test

Blocks 1–3 are deterministic/offline.

Block 4 is the first time V3 is allowed to call the real Gemini API.

It still does NOT connect to:

- Instagram
- Google Sheets
- Gmail
- Cloud Run

## Why

We want to test actual Gemini variability before connecting the model to a
customer-facing channel.

## Files added

- `test_live_gemini_v3.py`
- `test_block4_offline_safety_v3.py`

## Environment

The live script looks for:

```text
../.env
```

because the expected layout is:

```text
instagram-ai-quote-bot/
    .env
    v3_foundation/
        test_live_gemini_v3.py
```

Do not copy your API key into the test script.

## Run offline safety first

```powershell
python test_block4_offline_safety_v3.py
```

Then run the real Gemini smoke test:

```powershell
python test_live_gemini_v3.py
```

The live test checks 14 important cases including:

- Wedding
- basic kardo
- premium kya hota hai?
- both
- package price comparison after Basic selection
- okay during package reconfirmation
- premium kardo during reconfirmation
- okay kardo for travel
- maybe for travel
- Birmingham must not imply travel
- rendu kavali
- nahi chahiye
- drone question
- okay kardo to begin deferred review

Do not connect V3 to Instagram unless the live test reports:

```text
V3 BLOCK 4 LIVE GEMINI SMOKE TEST PASSED
```

If a case fails, copy the complete output back into ChatGPT. Do not patch the
live Instagram bot.
