# P14 remote branch data policy

This branch stores the P14 experiment code, reports, all summary tables, final
summary/model, data audit, selected feature names and the derived target table.
Large generated matrices are intentionally not committed to Git:

- `experiments/P13_feature_opt/data/feature_matrix_p13_t_ftir7.csv` (561,697 bytes)
- `experiments/P10_ftir_v3/data/feature_matrix_v2_fix_reduced.csv` (705,353 bytes)
- `experiments/P10_ftir_v3/data/ftir_sample_features_v3.csv` (78,148 bytes)

They remain in the local workspace and are listed with SHA256 in
`data/local_artifact_manifest.json`. This keeps the branch small while preserving
the evidence chain, model configuration and final tables.

The P10/P11/P12 full experiment trees and the P13 full matrix are **not** on this
branch. P13 contributes `data/feature_dictionary_p13_ftir7.csv` and
`data/README.md`; P10 contributes the P14-compatible `scripts/p10c_bench.py`
subset (`FTIR_RAW8` and `subset_target`), not the full P10 benchmark.

P14 run logs are local-only; the summary CSV files in `results/` are the
committed evidence. To rerun, restore the two feature matrices to the relative
paths in the P14 README, then use `tooling/run.sh`.
