verdict: REVIEW_UNAVAILABLE

# P20 Claims from Results

**Status**: `REVIEW_UNAVAILABLE` — 外部跨模型 reviewer 不可用；下面的表是本地确定性 gate，不是跨模型 acquit。

| ID | 预注册 claim | 本地 gate | 支持证据 | 缺口 |
|---|---|---|---|---|
| C1 | `aux_mek4` 对 `full8_base` 均值 ΔQWK ≥ +0.020，≥7/10 seeds，FR 上升 ≤1.0 pp，high recall 下降 ≤2.0 pp | **no** | ΔQWK `−0.003824`；3/10 seeds；FR `+1.27 pp`；high recall `−1.55 pp` | 方向为负；效应量、seed wins 均不达标；`aux_mek4_shuffle` 也低于 base |
| C2 | `aux_both` 达到 C1 同款 base gate，且对 `aux_both_shuffle` 均值 ΔQWK ≥ +0.010、≥7/10 seeds、FR/HR 不恶化超过限值 | **no** | `aux_both` ΔQWK `−0.014573`；3/10 seeds；FR `+2.54 pp`；high recall `−3.38 pp`；specificity `+0.009348`、6/10、p `0.156` | base gate 失败；specificity 也未过 +0.010 / 7 seeds；不能把 specificity 差值当 C2 成功 |
| C3 | 辅助覆盖与臂级结果可复核（描述性） | **yes** | MEK 298/301（89/97/61/51）；水煮 239/301（86/55/98）；6 臂 × 10 seeds 结果落盘 | 水煮缺 62 条；只有 301 条 T，单模型族 |
| C4 | 50 个 outer folds 的 `n_aux_test_labels_used=0` | **yes** | 300 条折级审计记录（50 folds × 6 arms），`n_aux_test_labels_used` 最大值 0；代码检查未读取 `te` 辅助标签 | 字段是声明的 0，不是动态污点证明；审计强度为 WARN |

## What the results actually show

- **辅助表征没有超过 base。** `aux_mek4` `−0.003824`、`aux_water3` `−0.006728`、`aux_both` `−0.014573`；三个真实辅助臂都低于 `full8_base`。
- **联合臂最差。** `aux_both` 比单 MEK 更低，FR `+2.54 pp`、high recall `−3.38 pp`；在当前样本量下，多 7 个概率更像噪声/过拟合，而不是共享信息。
- **Specificity 方向为正但不够强。** `aux_both` − `aux_both_shuffle` = `+0.009348`，6/10 seeds，p `0.156`；低于 `+0.010` / 7 seeds，且 `aux_both` 本身低于 base，不能救 C2。
- **相关性不等于可迁移增益。** MEK 与 T raw 的 Spearman `0.584`、水煮 `0.187`；但辅助模型和 T 模型共享同一 `full8`，辅助概率没有引入 X 之外的新测量。

## Suggested claim revision

> 在 301 条 T、冻结 P16 `full8`、10 seeds 和训练期 stacked 辅助概率的预注册协议下，MEK、水煮及联合辅助表征均未提升真实 OOF QWK；三个真实辅助臂都低于 `full8_base`，联合臂下降最多（`−0.014573`），label-shuffled specificity 也未达到 `+0.010` / 7 seeds 门槛。该负结果关闭“在同一 `full8` 上继续叠加辅助概率”的路线，但不证明 MEK/水煮与 T 弯没有边际相关性，也不证明端到端多任务共享编码器一定无效。

## Next experiments needed

1. 不再在 301 条 T 上调辅助目标/概率温度/特征组合；这是同一信息上限内的选择。
2. 若要继续跨目标，需要新的 T 测量（尤其切点附近、44 条未测 T）或真正的端到端多任务共享编码器，并用外部/新系列验证。
3. 报告口径：写“P20 关闭当前 stacked 辅助表征路线”，不要写“MEK/水煮对 T 弯无用”。
