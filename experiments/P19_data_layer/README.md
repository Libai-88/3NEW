# P19 — Data Layer Audit + Training-Only Augmentation

## Objective

P18 found no deployable nested decision policy on 301 epoxy-phenolic T labels. P19 asks whether the **data layer** can be improved without new experimental T measurements, using literature context and training-only augmentation.

## Hard boundaries

- The 301 observed T labels are the only evaluation ground truth.
- Synthetic rows are generated **after** the outer split and only inside the training fold; every test fold has `n_synthetic_test = 0`.
- No literature T value, pseudo-label, or manually filled T value is used as a target.
- No external rows are merged into the 301-row modelling table.
- The cure-condition arm is exploratory only; condition is perfectly confounded with series.

## Status

**C1 (training-only augmentation): FAIL.** Best augmentation `jitter25` gives ΔQWK `+0.00703`, 6/10 seed wins, FR `+2.39 pp`, high recall `−2.25 pp`; below the pre-registered `+0.020`.

**C2 (boundary-aware weighting): FAIL.** `boundary_w50` gives ΔQWK `+0.00978`, 8/10 seed wins, FR `+0.42 pp`, high recall unchanged, paired p `0.063`; directional but below `+0.020`.

**C3 (data audit): PASS (descriptive).** 301 observed T, 44 missing T, 0 repeated T, 190/301 within ±1.8 mm of a cut.

**C4 (no external data): PASS.** No external T rows merged; literature used only as an ASTM precision reference.

`REVIEW_UNAVAILABLE`: external cross-model reviewer unavailable; the claim ledger is a local deterministic check, not an acquittal.

## Protocol

- Data: 301 observed epoxy-phenolic T, cuts `[15,20]`, `formula_id` groups.
- Outer split: `StratifiedGroupKFold(5)`; 10 seeds `[42,202,777,1234,2026,31415,2718,1618,5678,9999]`.
- Model: P16 `full8` (183 + 8 FTIR, 191 dims), `C=2.0`, `w=1.0`.
- Arms: `full8_base`, `jitter10`, `jitter25`, `smote_low`, `jitter10_smote_low`, `boundary_w50`, `boundary_w25`, `cure_meta` (exploratory).
- More details: `../../refine-logs/P19_EXPERIMENT_PLAN.md`.

## Files

- `scripts/p19_data_layer.py` — audit + experiment runner.
- `results/p19_data_audit_full.json` / `.csv` — data audit.
- `results/p19_summary_full.csv` — main 10-seed table.
- `results/p19_delta_full.csv` — paired deltas.
- `results/p19_per_seed_full.csv` — per-seed metrics.
- `results/p19_oof_proba_full.csv` — OOF probabilities.
- `results/p19_augmentation_audit_full.csv` — synthetic counts/weights.
- `results/p19_label_noise_simulation_full.csv` — noise diagnostic.
- `results/p19_claim_check_full.json` — machine-readable claim gate.
- `results/P19_CLAIMS_FROM_RESULTS.md` — claim ledger.
- `results/P19_EXPERIMENT_AUDIT.md` / `.json` — local audit.
- `results/P19_LITERATURE_NOTES.md` — literature scan.
- `results/P19_实验报告.md` — full report.
- `logs/p19_sanity.log`, `logs/p19_full.log` — run logs.

## Reproduce

```bash
cd /home/user/3new-refactor
python3 experiments/P19_data_layer/scripts/p19_data_layer.py --mode sanity --tag sanity
python3 experiments/P19_data_layer/scripts/p19_data_layer.py --mode full --tag full
```

Sanity uses seed 42; full uses 10 seeds. CPU-only; no GPU/SSH/Vast/Modal.
