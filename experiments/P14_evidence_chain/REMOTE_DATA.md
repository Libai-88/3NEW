# P14 remote branch data policy

This branch stores the P14 experiment code, reports, final summary/model and
small audit artifacts. Large generated matrices are intentionally not committed
to Git:

- `experiments/P13_feature_opt/data/feature_matrix_p13_t_ftir7.csv` (561,697 bytes)
- `experiments/P10_ftir_v3/data/feature_matrix_v2_fix_reduced.csv` (705,353 bytes)
- `experiments/P10_ftir_v3/data/ftir_sample_features_v3.csv` (78,148 bytes)

They remain in the local workspace and are listed with SHA256 in
`data/local_artifact_manifest.json`. This keeps the branch small while preserving
the evidence chain, model configuration and final tables.
