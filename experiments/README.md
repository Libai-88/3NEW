# Experiments

One folder per experiment. Every folder must contain:

- `README.md` — objective, protocol, inputs, outputs, status
- `scripts/` — experiment-local code
- `data/` and `results/` — generated artifacts
- `logs/` — run logs

Shared tooling and dependency pins live in `../tooling/`, never inside an
experiment folder.

## Experiment index

- `P10_ftir_v3/` — 原料 FTIR 特征构建与增量基准；结论：FTIR8 未过 +0.03，主基准维持 v2-fix。
- `P11_feature_search/` — 语义池 + 219 公式 + 嵌套搜索；结论：无公式组块过门槛，保留 P11-C5 诊断面板。
- `P12_optimization/` — 现有数据下的模型/决策层优化；结论：T C=1、MEK C=1 + cost-anchor、水煮 multi_extra，三目标 QWK 全为正。
- `P13_feature_opt/` — 特征层优化（增广、全谱 PCA、监督筛选、树筛选、样条、目标专属 FTIR8）；P13 为 3-seed 初筛，T 的 191/C1 估计已被 P14 修订。
- `P14_evidence_chain/` — **当前最优实验**；T 的 10-seed 证据链：190 维（183+FTIR7）、nested C、模型族、drop-one、置换与 bootstrap；最终 T QWK 0.5707（nested），三目标平均 0.5609。
