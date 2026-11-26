# P17 Claims from Results

**Status**：`REVIEW_UNAVAILABLE` — 外部跨模型 reviewer 不可用；以下为本地确定性 claim ledger，不是跨模型 acquit。  
**审计**：`P17_EXPERIMENT_AUDIT.md` / `P17_EXPERIMENT_AUDIT.json`（`WARN`）。

## Claim ledger

| ID | 预注册 claim | claim_supported | 支持证据 | 缺口 |
|---|---|---|---|---|
| C1 | `three_way` 相对 argmax 的 operational cost 下降 ≥0.10 | **no** | false release `−82.9%`、test `21.4%`、cost `−0.0372`（p `0.0319`，7/10） | cost 幅度不足；pred high `39.40%` 超 anti-claim 上限；false reject/precision 变差 |
| C2 | `selective τ=.60` coverage ≥0.70、false release 相对 −30%、high recall 下降 ≤0.05、QWK 不降 | **no** | coverage `81.16%`、false release `−30.26%`、QWK `+0.0629` | 全体 high recall `−7.89 pp` 超限；`p14_190` false release 降幅仅 `26.85%` |
| S1（补充，非预注册） | selective 的接受样本 high recall 不降 | **partial / exploratory** | accepted high recall `+3.94 pp`；high test rate `14.37%` | 这是 post-hoc 口径；不能改写 C2 |
| S2（补充，非预注册） | 风险下降不是“多判高”造成 | **no（three_way）/ pass（selective）** | selective pred high `26.45%`、precision `+5.70 pp`；three_way pred high `39.40%`、precision `−6.60 pp` | three_way anti-claim FAIL |

## What the results actually show

- 决策层能显著改变风险分布：`three_way` 把 false release 从 `21.41%` 压到 `3.66%`，但需要 `21.40%` 复测，且 false reject 升到 `25.39%`。
- `selective τ=.60` 是更均衡的操作点：false release `14.93%`、QWK `0.6297`、false reject `12.78%`、high precision `63.11%`；代价是 `18.84%` 复测和全体 high recall `70.70%`。
- 现有 `cost` 策略与 false release 目标不一致：false release `37.32%`、cost `1.0738`、QWK `0.5393`。

## Suggested claim revision

不要写“风险闸门成功”或“选择性预测免费提升”。可写：

> 在当前 301 条 T 标签和冻结模型下，决策指标转型可行；风险闸门和选择性预测都能以明确的复测/误判高代价降低 false release，但按预注册门槛 C1/C2 均未通过。没有免费提升。

## Next experiments needed

1. 业务确认成本权重与复测容量后，做 P18：训练折内 nested 选阈值，预注册代价权重、false reject 上限、复测率上限。
2. 若要提升 QWK 到 0.65+，优先补 T 标签/重复测量/标签噪声估计，而不是继续搜 FTIR 子集。
3. 扩展到 MEK/水煮时，分别预注册切点、代价和风险口径，不能复用 T 的权重。
