# Phase 0 PoC (throwaway)

Same commands on Windows and macOS. From the repository root:

```
python3 -m venv .venv
.venv/bin/pip install -r poc/requirements.txt -e backend      # Windows: .venv\Scripts\pip ...
.venv/bin/python -m pytest backend poc/tests -q
.venv/bin/python poc/tools/run.py                              # https://localhost:8443
```

Needs Python 3.11 or newer, AutoFirma installed, and your own certificate in the OS certificate store
(Windows store / macOS Keychain). Real certificates and signed files stay in `poc/private/` (git-ignored).
Optional: `python poc/tools/make_defaults.py` pre-fills the form from your own signed test file.
