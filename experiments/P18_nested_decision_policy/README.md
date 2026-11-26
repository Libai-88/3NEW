# P18: Nested Calibrated Decision Policy

**Status**：`COMPLETED`（`WARN` / `PROVISIONAL_LOCAL_AUDIT`）  
**Date**：2026-11-26  
**Owner**：模型开发实验 / T 弯

## Objective

P17 的决策阈值是固定的、概率未校准、成本权重是示例值。P18 检验：把温度校准和阈值选择都放进训练折内层后，能否在 301 条 T 标签上得到稳定可部署的“放行 / 判高 / 复测”策略。

不做什么：不改特征、不改模型族、不新增数据、不做外层 post-hoc 阈值搜索、不做 p14_190 第二系统。

## Protocol

- **Data**：`合并版数据集.xlsx`；T 301 条环氧酚醛；切点 `[15,20]`；`formula_id` 分组。
- **Outer**：`StratifiedGroupKFold(5)`；10 seeds。
- **Inner**：每个外层训练折内 `StratifiedGroupKFold(4)`。
- **Model**：P16 `full8`（183 + 8 FTIR），C=2.0、w=1 固定。
- **Calibration**：温度缩放；T 只在 `inner_raw` + `ytr` 上拟合；外层只应用；bounded `[0.5,3.0]`。
- **Policies**：`argmax`、P17 固定 `three_way`/`selective`、P18 `nested_three_way_raw/temp`、`nested_selective_raw/temp`。
- **Thresholds**：`three_way` h `.20–.80` step `.05`、l `0–.30` step `.05`；`selective` τ `.40–.90` step `.05`；只在 inner OOF 上选。
- **Primary cost**：false release 10 / false reject 3 / retest 1；capacity 25%。
- **Feasibility**：FR ≤5%、test ≤cap、high recall ≥inner argmax −5 pp、pred high ≤inner high rate +15 pp、high precision ≥inner argmax −5 pp、coverage ≥70%。
- **Sensitivity**：cfr `{5,10,20}` × crej `{2,3,5}` × cap `{15%,25%,35%}`。

## Key result

| System | false release | test | high recall | pred high | cost | QWK |
|---|---:|---:|---:|---:|---:|---:|
| argmax | 21.27% | 0% | 78.73% | 32.09% | 0.9073 | 0.5740 |
| P17 three_way fixed | 3.66% | 20.23% | 84.93% | 38.97% | 0.8568 | 0.5935 |
| **P18 three_way temp** | **4.65%** | **22.16%** | **78.31%** | **34.58%** | **0.8146** | **0.6070** |
| P17 selective fixed | 15.35% | 17.48% | 70.85% | 26.61% | 0.8339 | 0.6277 |
| **P18 selective temp** | **16.48%** | **12.99%** | **73.52%** | **29.00%** | **0.8684** | **0.6093** |

- **C1 FAIL**：均值接近（FR `4.65%`、test `22.16%`、cost `−0.0927`），但 seed gate 只有 `3/10`；4 seeds FR >5%，4 seeds high precision 掉 >5 pp。
- **C2 FAIL**：FR 相对仅 `−22.52%`（<30%）、high recall `−5.21 pp`、seed gate `1/10`。
- **Feasibility**：`three_way` 主设置 11/50 折有可行阈值，`selective` 0/50；主结果是“最小违约 fallback”，不是约束最优。
- **Calibration**：T `2.964` mean，46/50 折在上界 3.0；NLL `1.464→0.961`、ECE `0.145→0.089`，但没有转化为决策成功。
- **Cost sensitivity**：cap 25% 下 cfr 5/10/20 选中同一组阈值，权重只改变报告代价；cap 35% FR 3.38% 但 test 26.81% 超 25%。

## Conclusion

**当前 301 条 T 标签、冻结 full8 模型和预注册约束下，没有稳定可部署的嵌套决策策略。** 继续在决策层调阈值/成本权重只会得到 seed 间摆动；下一步应做 P19 数据层（44 条未测环氧酚醛 T、20–30 条分层重复 T、ICC/κ 噪声估计）。

## Run

```bash
# sanity (1 seed)
tooling/run.sh python3 experiments/P18_nested_decision_policy/scripts/p18_nested_decision.py \
  --mode sanity --tag sanity

# full (10 seeds)
tooling/run.sh python3 experiments/P18_nested_decision_policy/scripts/p18_nested_decision.py \
  --mode full --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999 --tag full
```

## Files

- `results/P18_实验报告.md`
- `results/P18_EXPERIMENT_AUDIT.md` / `.json`
- `results/P18_CLAIMS_FROM_RESULTS.md`
- `results/p18_oof_proba_full.csv`
- `results/p18_policy_per_seed_full.csv`
- `results/p18_policy_summary_full.csv`
- `results/p18_policy_delta_full.csv`
- `results/p18_cost_sensitivity_full.csv`
- `results/p18_thresholds_full.csv`
- `results/p18_calibration_full.csv`
- `results/p18_claim_check_full.json`
- `results/p18_config_full.json`
- `logs/p18_sanity.log`, `logs/p18_full.log`
