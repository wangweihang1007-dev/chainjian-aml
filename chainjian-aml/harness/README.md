# Verification harness

The harness is the single local entry point for repeatable verification. Run
commands from the `chainjian-aml` directory:

```powershell
python -m harness.run all
```

For CI, where the local SQLite warehouse is intentionally not checked in:

```powershell
python -m harness.run all --skip-eval
```

Individual suites are available with `unit`, `compile`, `frontend`, `smoke`, and
`eval`. Run `smoke` only after the API and frontend services are running; it
uses `SMOKE_API_URL`, `SMOKE_FRONTEND_URL`, and `SMOKE_ALERT_ID` when set.
The evaluation gate reads `harness/config.json`. Threshold changes should be
reviewed together with the benchmark result; the harness never modifies rules,
labels, or production data.
