# P22 Experiment Audit

**Status**: `PROVISIONAL_LOCAL_AUDIT`

**Checks**: 24/24 deterministic checks pass.

## Key checks

- 数据：301 条实测 T，标签 `33/197/71`，191 维 raw base。
- Sanity：`full8_base` seed 42 QWK `0.5761275403`，与 P20 `0.576128` 在 `1e-6` 内一致。
- 主运行：20 seeds × 5 folds × 6 arms；per-seed 120 行；OOF `36,120` 行；audit `600` 行。
- OOF：每个 arm/seed 301 行；概率有限且和为 1。
- 预处理：`test_transform_fitted=False` 全部成立；`target_used_in_prep=False` 全部成立；base `norm_scale=1.0`。
- 有效维度：`full8_base` 194、`cure_state` 196、`cure_state_shuffle` 196、`bake_control` 195、`cure_state_plus_bake` 197、`cure_state_tg` 197（191/193/193/192/194/194 raw + FTIR missing indicators）。
- `cure_205`：182/119；与 P19 `cure_meta` 同口径。
- CURE2：无缺失、非常量；301 条非重复组合。
- Placebo：CURE2 与 y 的平均绝对 Spearman `0.2822`；打乱后 `0.0558`，确认 shuffle 破坏关联。
- LOCO：4 arms ×20 seeds ×2 conditions；audit 160 行；条件计数 `200C/10min=119`、`205C/17min=182`。
- LOCO 的 per-seed QWK sd 为 0，因为两折固定且 lbfgs 确定性；因此 C2b 只做描述性压力测试，不做跨条件 p 值。

## Exclusions

- LOSO 未运行：预注册计划规定 C1 通过后才跑 LOSO；C1 失败，按 stop/go 跳过。
- 外部跨模型 reviewer 不可用：`REVIEW_UNAVAILABLE`；本审计不能替代独立 review。
