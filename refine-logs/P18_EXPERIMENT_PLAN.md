# P18 Experiment Plan

**Problem**: P17 已证明 T 弯“放行 / 判高 / 复测”的决策指标可行，但固定阈值、未校准概率、示例成本权重下 C1/C2 均未通过；当前无法回答“在训练折内选阈值、并对成本权重做敏感性后，是否存在稳定可部署的风险闸门”。

**Method Thesis**: 在冻结的 `full8` 特征与模型族上，用外层 10 seeds / 内层 4 折的严格嵌套流程，先做温度校准，再只用内层 OOF 选决策阈值；用成本-容量敏感性区分“真实风险控制”和“靠多判高/多复测换指标”。

**Date**: 2026-11-26

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| C1：`nested_three_way_temp_primary` 能在不增加高档过度预测的前提下，把 false release 控制在 5% 附近，且复测不超过 25% | P17 的固定 `three_way` 已把 false release 压到 3.66%，但 cost 只降 0.037、pred high 39.40% 超过 anti-claim；需要证明嵌套选择不是 post-hoc 调参 | 10 seeds 外层均值 false release ≤5%、test ≤25%、high recall 下降 ≤5 pp、`pred_high_rate` ≤38.59%、operational cost < argmax；至少 8/10 seeds 同时满足；paired false-release p<0.05、≥7 seeds 改善 | B1, B3 |
| C2：`nested_selective_temp_primary` 在 coverage ≥0.70 时，false release 相对下降 ≥30%，且不出现 >5 pp 的 high recall 或 QWK 下降 | P17 的 `selective τ=.60` 风险指标达标但全体 high recall 下降 7.89 pp；需要验证训练折内选 τ 是否能避免这个失败 | coverage ≥0.70；relative false-release reduction ≥30%；high recall 下降 ≤5 pp；QWK 下降 ≤5 pp；`pred_high_rate` ≤38.59%；8/10 seeds；paired false-release p<0.05、≥7 seeds 改善 | B1, B3 |

**Anti-claim to rule out**: 改善只来自“多判高”或“多复测”。检查 `pred_high_rate` ≤真实高档率 +0.15（≤38.59%）、`test_rate` ≤25%（C1）/≤35%（敏感性上界）、high precision 下降 ≤5 pp；并报告复测容量敏感性，不能只报最优点。

## Paper Storyline

- Main paper must prove: C1/C2 的嵌套决策策略在固定数据、固定特征/模型族下是否可部署；如果没有，明确记录“当前数据+业务口径下没有免费策略”。
- Appendix can support: 温度校准前后 NLL/ECE、阈值分布、成本-容量 Pareto、raw vs calibrated 消融。
- Experiments intentionally cut: 不做新特征搜索、不做新模型族、不做 p14_190 的第二系统、不做 post-hoc 外层阈值扫描。

## Experiment Blocks

### Block 1: Nested calibration + threshold selection

- Claim tested: C1 / C2
- Why this block exists: P17 的阈值是预先固定的，且概率未校准；本块只把阈值选择放进训练折内层，外层测试完全不参与选择。
- Dataset / split / task: `合并版数据集.xlsx`；T 301 条环氧酚醛；切点 `[15,20]`；`formula_id` 分组；外层 `StratifiedGroupKFold(5)`；内层 `StratifiedGroupKFold(4)`；10 seeds。
- Compared systems:
  - `argmax`（同一外层 OOF 的基线）
  - `p17_three_way_fixed`（HIGH_T=.35, LOW_T=.10）
  - `p17_selective_fixed`（τ=.60）
  - `nested_three_way_raw_primary`（无校准）
  - `nested_three_way_temp_primary`（温度校准；主系统）
  - `nested_selective_raw_primary`
  - `nested_selective_temp_primary`
- Metrics: false release、false reject、test rate、coverage、high recall（全体/接受样本）、high precision、pred high rate、QWK、operational cost、high test rate。
- Setup details: `full8` 191 维，C=2.0 固定，w=1；温度 T 只用内层 OOF 拟合（bounded 0.5–3.0）；阈值网格：three_way `h∈[0.20,0.80] step .05`、`l∈[0,0.30] step .05`、`l<h`；selective `τ∈[0.40,0.90] step .05`。
- Success criterion: 见 Claim Map；C1/C2 分开判定，不互相替代。
- Failure interpretation: 如果 nested 仍不能通过，说明在现有 301 条标签和当前业务口径下，固定 P17 阈值已是局部最优；下一轮应转向数据层（P19），而不是继续调阈值。
- Table / figure target: 主表为 7 个系统的决策指标；附图阈值分布和校准前后 NLL/ECE。
- Priority: MUST-RUN

### Block 2: Cost-capacity sensitivity

- Claim tested: C1 的稳健性，不是新 claim。
- Why this block exists: P17 的 `10/3/1` 是示例权重；不能用一个任意权重证明策略可部署。
- Dataset / split / task: 同 Block 1；只对 `three_way` 和 `selective` 的 temp 版本做敏感性。
- Compared systems: `c_false_release ∈ {5,10,20}` × `c_false_reject ∈ {2,3,5}` × `test_capacity ∈ {0.15,0.25,0.35}`；主设置 `10/3/0.25`。
- Metrics: false release、test rate、high recall、pred high、operational cost；每个组合都按内层选择、外层评估。
- Setup details: 约束 `false release ≤0.05`、`test ≤capacity`、`high recall ≥inner argmax −0.05`、`pred high ≤inner high rate +0.15`；无可行解时记录最不坏解并标 `feasible=false`。
- Success criterion: 报告 Pareto 前沿；不要求每个组合都过 C1，但不能只挑一个最优点。
- Failure interpretation: 若只有极端容量/权重才过，说明策略不可部署，不能包装成稳定。
- Table / figure target: Appendix 表 + Pareto 图。
- Priority: MUST-RUN

### Block 3: Ablations and simplicity check

- Claim tested: 改善是否来自校准/嵌套，而不是更复杂模型。
- Why this block exists: 需要排除“温度校准只是把阈值挪动”“nested 只是更多搜索”的解释。
- Dataset / split / task: 同 Block 1。
- Compared systems: `nested_*_raw` vs `nested_*_temp`；`p17_*_fixed` vs nested；`argmax`。
- Metrics: 同 Block 1，加校准 NLL/ECE。
- Setup details: 所有系统共用同一外层 OOF 生成过程；只改变阈值选择/校准，不改变特征、C、w。
- Success criterion: 如果 temp 版本相对 raw 没有稳定改善，报告“校准无效”，不能把 temp 写成贡献。
- Failure interpretation: 校准/嵌套的增益不成立时，回到 P17 固定策略或转数据层。
- Table / figure target: Appendix 消融表。
- Priority: MUST-RUN

### Block 4: Calibration diagnostics

- Claim tested: 支持 C1/C2 的解释，不单独作为 claim。
- Why this block exists: P17 没做概率校准；决策阈值依赖概率尺度。
- Dataset / split / task: 同 Block 1。
- Metrics: NLL、ECE（10 bins）、温度 T、每折 n。
- Setup details: T 只用内层 OOF 拟合；外层只应用；不以外层 NLL 选 T。
- Success criterion: 只报告诊断，不用“ECE 更低”替代决策指标。
- Failure interpretation: 校准变差时如实报告，不调参救。
- Table / figure target: Appendix 表。
- Priority: NICE-TO-HAVE

## Run Order and Milestones

| Milestone | Goal | Runs | Decision Gate | Cost | Risk |
|---|---|---|---|---|---|
| M0 | sanity：1 seed，检查外层/内层分组不重叠、阈值只由内层选择、概率和=1、301 条全覆盖 | 1 run | 任一分组泄漏或阈值引用外层即 STOP | <2 min | 小 |
| M1 | full：10 seeds，主系统 + 敏感性 + 消融 | 1 run | 输出 3010 条 OOF、470 条逐 seed、2200 条阈值日志、claim check | 8–20 min（2 vCPU） | 中 |
| M2 | audit：结果存在性、阈值来源、无外层调参、scope | 1 audit | `WARN` 可继续；`FAIL` 不写成功 claim | <2 min | 小 |
| M3 | report + GitHub archive | 1 report | C1/C2 明确 pass/fail；不把失败包装成成功 | <5 min | 小 |

## Compute and Data Budget

- Total estimated GPU-hours: 0（CPU only；约 2 vCPU / 3.9 GiB）。
- Data preparation needs: 无新数据；只读 `合并版数据集.xlsx`、P13/P16 特征矩阵。
- Human evaluation needs: 无；业务成本权重仍需用户确认，当前只做敏感性。
- Biggest bottleneck: 内层 OOF 只有约 240 条，低档约 26 条，阈值选择方差大；用 10 seeds 和外层聚合控制，不把单 seed 当结论。

## Risks and Mitigations

- **Inner OOF 小，阈值不稳定**: 报告每折阈值分布；要求 8/10 seeds，而不是单 seed。
- **温度校准与最终模型不匹配**: T 只在内层 OOF 拟合，外层只应用；同时保留 raw 消融，若 temp 不稳就退回 raw。
- **成本权重仍非业务确认值**: 主设置只作示例；Block 2 给敏感性，不声称金额最优。
- **选择性预测压低 high recall**: 把 high recall 下降 ≤5 pp 写进 C1/C2，不允许用接受样本口径替代全体口径。
- **外部 reviewer 不可用**: 审计只能 `PROVISIONAL_LOCAL_AUDIT`，不得声称跨模型 acquit。

## Final Checklist

- [ ] 主表覆盖 7 个系统
- [ ] 阈值来源可追溯到内层 OOF
- [ ] 外层测试未参与阈值选择
- [ ] 成本-容量敏感性完整
- [ ] raw/temp 与 fixed/nested 消融完整
- [ ] C1/C2 分别判定，失败不包装
- [ ] 外部 reviewer 不可用已记录
