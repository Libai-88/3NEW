# P22 — Cure-State Representation vs Bake-Identity Control

**Status**: RUN COMPLETE — **negative result**, local audit `PROVISIONAL_LOCAL_AUDIT`, external review `REVIEW_UNAVAILABLE`.

P21 已把“手工角色权重 + 现有 catalyst 特征”这条路线跑到负结果。P22 不继续调角色权重，检验一个更窄、可证伪的表示问题：

> 在冻结的 191 维 `full8` 之外，2 维后固化状态 `cure_drive + cure_margin_eff` 是否能提供独立于烘烤身份/系列身份的 T 弯信号？

**答案：不能。** 分布内 `cure_state − full8_base` QWK `+0.009007`（低于预注册 `+0.010`，12/20 seeds）；`cure_state_plus_bake − bake_control` 实际为 `−0.003612`；LOCO `cure_state` 从 `0.463109` 崩到 `0.327897`（`−0.135212`）。单独一个 `bake_control` 二元烘烤指示反而 `0.582640`，比 CURE2 高 `+0.003451`。C3 placebo 通过（`+0.014604`，14/20，p `0.01530`），但只是 supporting，不能救 C1/C2。

## 文件

- 预注册计划：`../../refine-logs/P22_EXPERIMENT_PLAN.md`
- 执行 tracker：`../../refine-logs/P22_EXPERIMENT_TRACKER.md`
- 主报告：`results/P22_实验报告.md`
- claim：`results/P22_CLAIMS_FROM_RESULTS.md`
- 审计：`results/P22_EXPERIMENT_AUDIT.md` / `results/P22_EXPERIMENT_AUDIT.json`
- 主汇总：`results/p22_main_summary.csv`
- per-seed：`results/p22_main_per_seed.csv`
- LOCO 汇总：`results/p22_loco_summary.csv`
- 机器 gate：`results/p22_claim_check.json`
- 配置：`results/p22_config.json`

## 远程归档

P22 的关键结果证据已归档到 `experiment/p14-best` 分支的
`experiments/P22_cure_state/`，清单见 `P22_REMOTE_ARCHIVE.md`。
OOF、per-seed、fold-level audit、脚本和日志按 P19/P20/P21 惯例保留在本地。

## 已完成

- `data/P22_FEATURE_TRIAGE.csv` / `.json` — 13 个未入模机理列的 Ridge 重建 R²、Spearman、常量/重复检查。
- `scripts/p22_feature_triage.py` — 可复现数据审计。
- `scripts/p22_cure_state.py` — sanity / main / LOCO；LOSO 按预注册 stop/go 跳过。
- `scripts/p22_audit.py` — 24 项确定性审计 + claim gate。
- sanity：`full8_base` seed 42 `0.5761275403`，精确复现 P20 `0.576128`。
- main：20 seeds ×5 folds ×6 arms；600 fits。
- LOCO：20 seeds ×2 conditions ×4 arms；160 fits。

## 结论

P22 关闭 cure-state 路线，不采纳任何新臂。当前可部署 T 基线仍是 `full8_base`（191 raw）+ ordinal logistic `C=2`。下一步不建议继续在 191 维上手工构造特征；应转向 P23 连续 T 监督或新测量/新系列。
