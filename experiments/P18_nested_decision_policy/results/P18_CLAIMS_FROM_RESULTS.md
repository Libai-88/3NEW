# P18 Claims from Results

**Status**：`REVIEW_UNAVAILABLE` — 外部跨模型 reviewer 不可用；以下是本地确定性 claim ledger，不是跨模型 acquit。  
**审计**：`P18_EXPERIMENT_AUDIT.md` / `.json`（`WARN`，`PROVISIONAL_LOCAL_AUDIT`）。

## Claim ledger

| ID | 预注册 claim | claim_supported | 支持证据 | 缺口 |
|---|---|---|---|---|
| C1 | `nested_three_way_temp_primary` 在 false release ≤5%、test ≤25%、high recall 下降 ≤5 pp、pred high ≤38.59%、cost 下降 ≥0.02 下稳定可部署，8/10 seeds | **no** | 10-seed 均值：FR `4.65%`、test `22.16%`、high recall `−0.42 pp`、pred high `34.58%`、cost `−0.0927`、QWK `0.6070`；FR 配对 p `7.05e-10` | seed gate **3/10**；4 seeds FR >5%（最高 `7.04%`）；4 seeds high precision 掉 >5 pp；39/50 折无可行阈值 |
| C2 | `nested_selective_temp_primary` coverage ≥0.70、FR 相对 −30%、high recall 下降 ≤5 pp、QWK 下降 ≤5 pp | **no** | coverage `87.01%`、QWK `+0.035` | FR 相对仅 `−22.52%`；high recall `−5.21 pp`；seed gate **1/10**；0/50 折可行 |
| S1（post-hoc，非预注册） | 均值层面的 C1 已接近达标 | **partial / exploratory** | 均值数值确实都过 C1 的数值门槛 | seed 级不稳定；不能改写 C1；不能把均值包装成部署结论 |
| S2（post-hoc） | 温度校准改善概率质量 | **partial** | NLL `1.464→0.961`；ECE `0.145→0.089` | T 46/50 落在上界 3.0；未转化为 C1/C2 成功 |
| S3（post-hoc） | 成本权重敏感性可找到更优策略 | **no** | cap 25% 下 cfr 5/10/20 选中同一组阈值；FR/test/recall 相同 | 权重只改变报告代价；cap 35% 的 FR 3.38% 但 test 26.81% 超 25% |

## What the results actually show

- P18 不是“P17 升级版”。P17 固定 `three_way` 的 FR 更低（3.66%），但 pred high 38.97% 超过 anti-claim；P18 的 pred high 和成本更好，但 FR 4.65%、high recall 更低。两者没有支配关系。
- 嵌套阈值选择在多数折内没有可行解：`three_way` 11/50 折可行，`selective` 0/50 折可行。主结果中的阈值是“最小违约 fallback”，不是约束最优解。
- 温度校准在 NLL/ECE 上有改善，但 50 个折中 46 个温度落在上界 3.0；这不是稳定的校准机制，不能作为决策成功的独立证据。
- 成本敏感性没有改变决策：在 25% 容量下，改变 false release 权重只改变报告的代价，FR/test/high recall 完全不变。当前约束下，成本权重不是主要自由度。

## Suggested claim revision

不要写“P18 嵌套决策策略通过”或“C1 均值达标所以可部署”。可写：

> 在 301 条 T 标签、冻结 `full8` 模型和 10 seeds 下，嵌套阈值 + 温度校准在均值层面接近 C1，但 seed 级只有 3/10 同时满足；内层约束在 39/50 个 `three_way` 折和 50/50 个 `selective` 折无可行解。结论是：当前数据与业务口径下没有稳定可部署的嵌套决策策略，需转向数据层。

## Next experiments needed

1. **P19 数据层**：44 条未测环氧酚醛 T 的主动补测；20–30 条分层重复 T 测试，估计 ICC/κ 和标签噪声。
2. **P18-B（可选，需重新预注册）**：硬风险 fallback 或 conformal risk control；不能在看到本结果后 post-hoc 改阈值再宣称成功。
3. 若业务确认成本权重，再做 MEK/水煮的独立决策指标，不能复用 T 的权重。
