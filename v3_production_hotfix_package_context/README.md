# V3 Production Hotfix 01

This is not a new architecture block.

It fixes the two defects reproduced from the first production Instagram
acceptance screenshot:

1. When `QUOTE_PACKAGE` expects Basic/Premium, a semantic value such as
   `Wedding` can no longer mutate `package` or advance the state. Python checks
   the value against the authoritative allowed catalogue.

2. When a service such as Wedding is already selected and the customer asks
   for the difference between Basic and Premium, the standard comparison is
   generated deterministically from the selected service's approved Pricing
   rows. It cannot fall back to a generic "which service?" answer.

## Install

Extract this folder under your project, then from the extracted folder run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_hotfix.ps1
```

The script backs up the four affected production modules, copies the patch,
runs the exact screenshot regression, compiles the files, and imports
`main.py`.

Do not deploy until the installer prints:

```text
V3 PRODUCTION HOTFIX 01 INSTALLATION PASSED
```
