# P16 实验计划：FTIR 块权重与安慰剂对照

**Problem**：P15 已证明“固定 190 维”不是稳定最优，FTIR 子集选择在外层折之间高度分散；但 FTIR 块整体仍有信号。下一步不应继续做大规模子集/公式搜索，而要回答两个更基础的问题：

1. FTIR 的增益是**样品特异的化学信息**，还是仅仅来自“多了 8 个参数 + L2 正则”？
2. 如果 FTIR 有用，能否用一个**连续块权重**代替不稳定的硬子集选择，让“给 FTIR 多少系数”成为可调参数？

**Method Thesis**：用**同维度的 row-shuffled placebo 对照**检验 FTIR 增益的真实性；用**训练折内选择的连续块权重 `w`**替代“选哪 7 个 FTIR”的离散搜索；用 `core4` 做简约性对照。

**Date**：2026-11-25

**Status**：计划完成，已执行；C1 PASS，C2 FAIL。

**Skills used**：`experiment-plan`（claim→evidence→run order）、`experiment-audit`（anti-claim / placebo 思路）、`exploratory-data-analysis`（数据/切分/缺失边界）。

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| C1：FTIR8 含样品特异信号，而非仅额外参数/正则 | 如果 placebo 与 full8 打平，P14/P15 的“FTIR 增益”就不能解释为化学信息 | `full8 − placebo8` 的 QWK ≥ **+0.010**，paired p<0.05（Holm 后），≥7/10 seeds 正；高档 recall 与 cost 不恶化超过 0.02 | B1 |
| C2：单一连续块权重能替代硬子集选择，并优于/不劣于固定 full8 | P15 的子集选择不稳定；若一个标量权重就能保留增益，就不需要 post-hoc 选 7 个 FTIR | `ftir8_w − full8` 的 QWK ≥ **+0.005**，p<0.05（Holm 后），≥7/10 seeds 正；且 `core4_w − ftir8_w` ≥ **−0.005**（非劣性） | B2, B3 |
| Anti-claim：增益只来自“更多特征/更大模型” | 同维度、同协方差的 placebo 可直接排除这一解释 | placebo 与 full8 同维度、同边际/协方差；若 C1 不成立，C2 不得被解释为化学增益 | B1 |

## Experiment Blocks

- **Block 1**：Placebo 对照；base183 / full8 / placebo8；301 T；5 outer grouped；C 0.5–2；10 seeds。
- **Block 2**：FTIR 连续块权重；ftir8_w / full8 / base；w 0.5–4.0；w 在 StandardScaler 之后。
- **Block 3**：core4_w 简约性；187 维，历史子集标记 post-hoc。
- **Block 4**：w/C 频率（nice-to-have，不改变判定）。
- **Block 5**：P14 190 参考（appendix，不重训）。

## Run Order

| Milestone | Goal | Runs | Gate |
|---|---|---|---|
| M0 sanity | 形状/placebo/权重掩码 | 1 seed | 无 NaN；full8 接近 P14 sanity |
| M1 baseline | base/full8/placebo 10 seeds | 3×10 | 量级一致；placebo 不崩 |
| M2 main | ftir8_w 10 seeds | 6 w × 4 C | w 不贴边；相对 full8 明确 |
| M3 parsimony | core4_w 10 seeds | 6 w × 4 C | 非劣性 |
| M4 analysis | paired/Holm/CI | 不重训 | C1/C2 |

## Pre-registered gates

- **C1**：`full8 − placebo8` QWK ≥ +0.010；Holm p<0.05；≥7/10 seeds 正；high drop ≤0.02、cost rise ≤0.02。
- **C2**：`ftir8_w − full8` QWK ≥ +0.005；Holm p<0.05；≥7/10 seeds 正；`core4_w − ftir8_w` ≥ −0.005。

## Risks

- Placebo 仍可能保留配方组结构；置换不按 target 选择。
- w 贴边 0.5 或 4.0 → 报“未定”，不 post-hoc 扩网格。
- w 改变标准化后 FTIR 的 L2 有效惩罚，不是纯化学机制解释。
- core4 是历史子集，不能写成全局最优。
- 301 条小样本；10 seeds 不是独立外部验证。

## Final Checklist

- [x] C1 有同维度 placebo 对照
- [x] C2 的 w/C 都在外层训练折内选择
- [x] core4 标注历史子集
- [x] w 作用在 StandardScaler 之后
- [x] 主表含 base / full8 / placebo / ftir8_w / core4_w / P14 参考
- [x] 失败解释已预注册
- [x] 不引入新标签、不伪造膜厚/烘烤曲线/差谱
