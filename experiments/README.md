# Experiments

One folder per experiment. Every folder must contain:

- `README.md` — objective, protocol, inputs, outputs, status
- `scripts/` — experiment-local code
- `data/` and `results/` — generated artifacts
- `logs/` — run logs

Shared tooling and dependency pins live in `../tooling/`, never inside an
experiment folder.

> **远程分支 `experiment/p14-best` 的归档边界**：完整保存 P14 的代码、证据汇总表、最终表、模型配置、数据审计和 190 特征名；同时保留 P13 的 `feature_dictionary_p13_ftir7.csv`/`data/README.md` 和 P10 的 P14 兼容子集 `p10c_bench.py`。P10/P11/P12 的完整目录、P13 大矩阵及 P14 运行日志留在本地完整归档，未进入该远程分支。缺失数据的 SHA256 与补齐路径见 `P14_evidence_chain/REMOTE_DATA.md`。

## Experiment index

- `P10_ftir_v3/` — 原料 FTIR 特征构建与增量基准；结论：FTIR8 未过 +0.03，主基准维持 v2-fix。
- `P11_feature_search/` — 语义池 + 219 公式 + 嵌套搜索；结论：无公式组块过门槛，保留 P11-C5 诊断面板。
- `P12_optimization/` — 现有数据下的模型/决策层优化；结论：T C=1、MEK C=1 + cost-anchor、水煮 multi_extra，三目标 QWK 全为正。
- `P13_feature_opt/` — 特征层优化（增广、全谱 PCA、监督筛选、树筛选、样条、目标专属 FTIR8）；P13 为 3-seed 初筛，T 的 191/C1 估计已被 P14 修订。
- `P14_evidence_chain/` — **固定集条件最优实验**；T 的 10-seed 证据链：190 维（183+FTIR7）、nested C、模型族、drop-one、置换与 bootstrap；最终 T QWK 0.5707（nested），三目标平均 0.5609。
- `P15_feature_robustness/` — FTIR 特征稳健性；把 FTIR 子集选择与 C 选择都放入外层训练折；10-seed nested QWK 0.5717±0.0231；P14 190 仅 14% 外层折被选中，说明 190 维不是稳定最优；P15-A 残差化仅 1-seed 探索。
- `P16_ftir_block_weight/` — FTIR 块权重 + row-shuffled placebo；C1 PASS（FTIR8 有真实样品信号，full8−placebo +0.0357，Holm p=0.0072）；C2 FAIL（整块权重不如 full8，p=0.1035）；core4_w 0.5715±0.0135 仅探索性。
- `P17_decision_metrics/` — T 弯决策指标转型；`three_way` false release 21.41%→3.66%，但 cost 仅 −0.0372、C1 FAIL；`selective` coverage 81.16%、QWK 0.6297，但全体 high recall −7.89 pp、C2 FAIL；无免费提升。
- `P18_nested_decision_policy/` — 嵌套阈值 + 温度校准 + 成本/容量敏感性；C1 FAIL（均值接近，但 seed gate 3/10）、C2 FAIL（FR 相对 −22.52%、high recall −5.21 pp）；主设置 39/50 折无可行阈值，结论是当前 301 条下无稳定可部署策略。
- `P15_P16_REMOTE_ARCHIVE.md` — 远程归档范围与缺失大矩阵清单。
