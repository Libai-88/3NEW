# 3NEW · 三新项目研发

**涂料配方性能预测与跨体系泛化。** 本仓库以「原料描述符 + 配方级机理特征 + SMILES 分子描述符」替代原料编码，让环氧酚醛、环氧-配比方案、聚酯金黄三个体系共用同一套特征空间，并对 T弯、MEK 擦拭、水煮等级三项目标做建模、验证与预测。

> 2026-11-23 完成仓库重构：原 `generalization/` 提升为根目录，Phase 1 旧结构、旧 Web 整理界面和桌面 GUI 均已移出主树。当前主树只保留跨体系泛化这一条开发主线，以及无界面的数据/建模核心。

## 当前数据快照

以 `合并版数据集.xlsx` 为准（10 个工作表）：

| 维度 | 当前值 |
| --- | --- |
| 配方样本 | **456** 条 |
| 原料主数据 | **73** 种 |
| 配方系列 | **110** 个 |
| 组分记录 | **5,515** 行 |
| 性能记录 | **1,002** 条 |
| 实测标签 | **421** 条（无标签 35 条） |
| 三体系样本 | 环氧酚醛 345 / 环氧配比方案 92 / 聚酯金黄 19 |
| 目标覆盖（样本口径） | T弯 373 / MEK 352 / 水煮 277 |
| 烘烤条件 | 205℃·17min 294 条；200℃·10min 162 条 |

`建模输入` 为 456 × 66：4 列元数据 + 3 列目标 + 59 列描述符；另有 `配方级描述符` 63 列、`配方级机理特征` 44 列（4 列元数据 + 40 列机理）。

## 目录结构

```text
3NEW/
├── README.md                          # 本文件：总览、结构、快速开始、开发约定
├── 合并版数据集.xlsx                   # 当前主数据集（10 工作表，456 样本）
├── 终极版数据集模板.xlsx               # v3 模板：体系配置驱动 + 数据验证
├── 通用型数据集模板.xlsx               # 通用模板（8 工作表，供 run_pipeline 使用）
├── 模板工作原理与泛化原理.md            # 面向非化学人员的模板/泛化说明
├── 达标分类验证实验V.md                 # 实验 V：由“预测数值”转“预测是否达标”
├── coating-model-generalization.html   # 主方案报告
├── composition-completion.html         # 原料信息利用与数据集补全
├── experiment-rerun-report.html        # 实验复跑与修复验证
├── mechanism-optimization-report.html  # 机理特征工程与评估口径修正
├── generalization-hardening-report.html # 泛化压力测试与协议加固（实验 T）
├── assets/                             # 报告图表（9 张实验图 + 1 张流程图）
├── _shared/                            # 报告依赖的字体与 JS 库（离线可用）
├── raw/                                # 5 份原始实验记录（重录数据源）
├── data/
│   └── merged_data.pkl                 # 中间产物：456 样本配方 + 描述符
├── experiments/                        # P10 以后专题实验，一批一目录，P14 为当前最优
│   ├── README.md                       # 实验索引、目录约定、复现入口
│   ├── P10_ftir_v3/                    # 原料 FTIR 特征与基准
│   ├── P11_feature_search/             # 219 公式搜索
│   ├── P12_optimization/               # 模型/决策层优化
│   ├── P13_feature_opt/                # 特征层优化（初筛）
│   └── P14_evidence_chain/             # 最优实验：T 190 维证据链
├── tooling/                            # 依赖锁 + 统一启动器，不放进实验目录
├── TDS-SDS/                            # 供应商 TDS/SDS 档案 291 份（描述符实测出处）
├── core/                               # 无 GUI 的数据/建模核心
│   ├── modeling.py                     # 特征构建 + 三目标训练/预测（含当前最优配置）
│   ├── data_prep.py                    # 数据整理与特征转换
│   ├── materials.py                    # 原料描述符库（85 条登记 / 在用 73 种）
│   ├── tds_sds.py                      # TDS/SDS 实测层（最高优先级，带 prov 出处）
│   ├── compo_rules.py                  # 送检组成补全规则
│   ├── handbook_fixes.py               # 占位描述符修正
│   ├── mech_desc.py                    # 40 维配方级机理特征
│   └── smi_desc.py                     # SMILES 分子描述符（内嵌，无需 RDKit）
├── scripts/                            # 可复现脚本（数据重录、实验、CLI）
│   ├── reingest_template.py            # 原始 5 份 xlsx → 终极模板 + merged_data.pkl
│   ├── build_merged_excel.py           # merged_data.pkl → 合并版数据集.xlsx
│   ├── run_pipeline.py                 # 通用 CLI：模板 → 描述符 → 建模 CSV
│   ├── mvp74...mvp90                   # 实验 J~V 脚本（详见“实验索引”）
│   └── tds_coverage_audit.py           # TDS/SDS 覆盖度审计
└── data_dilemma/                       # 数据困境专项实验（E/S/A）
    ├── README.md
    ├── report/data-dilemma-solution.html
    └── scripts/
```

## 快速开始

### 环境

依赖已锁在 `tooling/requirements.txt`：

```bash
python3 -m pip install -r tooling/requirements.txt
```

Python 建议 3.10+。实验统一用 `tooling/run.sh` 启动，它会把仓库根目录、`core/` 和 `scripts/` 加入 `PYTHONPATH`：

```bash
tooling/run.sh python3 experiments/P14_evidence_chain/scripts/p14_t_models.py
```

本仓库不提供 GUI 入口，所有功能都通过 Python 脚本或 CLI 调用，可在 Windows、Linux 和云主机上运行。

### 看报告

直接用浏览器打开 `coating-model-generalization.html`，字体和图表已本地化，可离线查看。其余四份根目录 HTML 是专题报告。

### 重建数据集

```bash
python scripts/reingest_template.py --report   # 先只打印解析审计，不写文件
python scripts/reingest_template.py            # 重写 终极版数据集模板.xlsx 与 data/merged_data.pkl
python scripts/build_merged_excel.py           # 由 pkl 生成 合并版数据集.xlsx
```

> 重录会覆盖现有模板和数据集，建议先提交或备份。`merged_data.pkl` 由较早版本的 pandas 生成，当前环境（pandas 2.2.3）直接读取会报兼容性错误；重录脚本会自动回退到 `合并版数据集.xlsx` 读取 R8/R9/R10 的既有登记，并生成新的 pkl，不需要手工改 pickle。

### 通用 CLI

```bash
python scripts/run_pipeline.py desc \
  --input 通用型数据集模板.xlsx \
  --output 建模特征.csv
```

`desc` 完成“模板 → 配方级描述符 → 建模 CSV”；另有 `label`（半监督伪标签 + 主动学习）和 `all`（全流程）。

### 直接调用核心库

```python
import sys
sys.path.insert(0, 'core')

from modeling import load_dataset, build_feature_matrix

mat_lib, samples, perf, proc = load_dataset('合并版数据集.xlsx')
X, ids, series = build_feature_matrix(samples, mat_lib, perf, proc)
print(X.shape)  # (456, 313)
```

`core/` 只提供函数，不启动窗口、不写 GUI 状态；训练与评估通过 `scripts/mvp*.py` 运行。

## 特征与模型

### 313 维特征契约

`modeling.build_feature_matrix()` 固定输出 313 维，顺序由 `feature_names` 固化：

| 组成 | 维度 |
| --- | --- |
| 73 种原料的配方占比 | 73 |
| 烘烤温度、时间 | 2 |
| 增强配方特征 | 100 |
| 显式比例特征 | 22 |
| SMILES 分子描述符 | 76 |
| 配方级机理特征 | 40 |
| **合计** | **313** |

特征空间不包含原料代码或体系 one-hot，因此新原料只要补登记描述符就能进入同一空间；新体系通过 `体系配置` 表扩展，不改模板结构。

### 当前主模型与指标

| 目标 | 配置 | 当前指标 |
| --- | --- | --- |
| T弯（回归） | sqrt 目标 + 公共噪声掩码 + 折叠内选择 keep=96、k=8、w=0.85 + 机理单调先验 | 掩码内 **R²=0.749±0.003**；全样本 R²=0.159 |
| MEK 擦拭（两阶段） | AFT 边界判别 + 未截尾回归（p_hi 特征注入，keep=45，cap=300） | 未截尾 **R²=0.458±0.004**；边界 acc=0.915 / AUC=0.922 |
| 水煮等级（分类） | 折叠内选择 keep=80 + 固定阈值 0.5 | acc=**0.758** / AUC=**0.824** |

指标口径是“折叠内选择 + 公共掩码”的 20 种子终验，不是在全量数据上选完特征再交叉验证的旧口径。T弯掩码内与全样本的差距来自标签重尾：掩码外约 19% 的样本贡献了约 96% 的平方误差，说明瓶颈在测量噪声与标签口径，不在特征数量。

### 重要口径提醒

- **水煮主模型标签是 `≥4` 为不合格**；实验 V 验证的是 `≥3` 为不合格的二值口径。两者方向一致但阈值不同，实验 V 的脚本尚未并入主模型，不能把 V 的 AUC 直接当主模型指标。
- **MEK 右截尾**：仅“恰为 300”视为右截尾（真实值 ≥300 未知）；350/400/550 是真实观测值。主模型用“未截尾 R² + 边界 acc/AUC”双指标，不报含截尾代理值的全样本 R²。
- **新系列外推不可直接用**：留一系列外推加权 R²≈−0.30；新系列先测 1~2 个配方回入系列编码，再依赖数值预测。`domain_check` 会对未登记系列和越界特征给出警告。

### P0 数据层基线（2026-11-23）

`scripts/p0_clean_baseline.py` 对“原始克数 vs 质量分数 + 删除质量乘积 + top-K 选择”做了同模型、同配方分组的 A/B。结论是 **clean 269 维没有稳定优于 current 313 维**：T 弯环氧酚醛 301 条 GroupKFold 为 current R²=0.1293 / clean R²=0.0023；按目标分位分箱的平衡 StratifiedGroupKFold 为 0.3656 / 0.3121；10 次 80/20 重复划分两臂均值都接近 0，top-K 选择也不稳定。因此当前主特征集暂不替换，clean 只保留为可解释性与化学闭合审计分支；完整结果见 `scripts/p0_clean_baseline_results.json`，报告见 [P0 清洁基线实验结果](https://my.feishu.cn/docx/NQecdC9coo4Z5jxpwEKcobHsnlf)。

### P0.5 无烘烤工艺特征基线（2026-11-23）

针对烘烤条件 provenance 不确定的问题，`scripts/p05_no_process_baseline.py` 在 P0 协议上彻底移除工艺信息：删除 `烘烤温度`、`烘烤时间`，以及 6 个依赖烘烤时间的机理特征 `t_eff_min`、`ne_effective`、`cure_drive`、`cure_margin`、`cure_margin_eff`、`cure_margin_neg`。current 从 313 维降到 305 维，clean 从 269 维降到 262 维；其余特征、目标、配方分组和模型参数不变。

结论是 **去工艺后模型仍可用，但没有变好**：T 弯环氧酚醛 GroupKFold R² 从 0.1293 降到 0.1001（MAE 2.1862→2.2332）；平衡 SGKF 从 0.3656 到 0.3607；10 次 80/20 重复划分从 −0.0133±0.5168 到 −0.0671±0.5502。水煮 W4 的 acc/AUC 从 0.7401/0.8153 到 0.7365/0.8018，MEK 边界 acc/AUC 从 0.9034/0.9157 到 0.8977/0.9139；MEK 未截尾回归 R² 从 0.2645 到 0.2090。工艺特征不是当前性能的主要来源，但也说明当前配方特征本身不足以把 T 弯和 MEK 未截尾回归做稳。

因此现阶段把 **no-process 作为默认安全基线**：不把不确定的烘烤条件喂给模型，不再用工艺标签解释性能；`full_process` 只保留为批次敏感性对照。完整结果见 `scripts/p05_no_process_results.json`，报告见 [P0.5 无烘烤工艺特征基线](https://my.feishu.cn/docx/UjPJdWSYioP1O1xsEuicOusdnie)。

### P0.6 三目标分级基线（2026-11-24）

按用户确认口径，把 T 弯、MEK、水煮改为有序等级，并与“连续回归后按同一切点分级”和普通多分类做同配方分组 A/B：T 弯 `≤15 / 15–20 / >20`，MEK `≤50 / 50–100 / 100–200 / ≥200`（≥200 为停擦上限），水煮 `1–2 / 3 / 4–5`（原始 2.5 按 3 计）。结果为：T 弯主口径 310 条仍是“回归后分级”最好（QWK 0.4881，多分类 0.4307、序数 0.4289）；MEK 352 条则以序数累积最好（QWK 0.6165，回归后分级 0.5826、多分类 0.5876）；水煮 277 条仍是“回归后分级”最好（QWK 0.5187，多分类 0.4872、序数 0.4575）。结论是分级是更接近实际决策的输出层，但不是精度放大器；三个目标应按任务分别选型，不能统一替换。完整结果见 `scripts/p06_grade_results.json`，分级定义见 `scripts/grade_schema_v1.json`，报告见 [P0.6 三目标分级基线](https://my.feishu.cn/docx/QsJYdWchvoirEax3Gr6cPYn2nBh)。

### P0.8 Feature v2 特征治理与复跑（2026-11-24）

`scripts/build_feature_v2.py` 在 P0 clean 上做特征治理，不改主数据、不用目标：删除烘烤工艺与依赖烘烤时间的机理列；删除 `smi_coverage` / `smi_low_coverage` 两个覆盖度元信息；删除 `ratio_01` / `ratio_02` 两个会因特定原料缺失而放大到 1e10 的不稳定显式比例；出现次数 <5 的稀有原料从连续质量分数改为 presence 标志 + `frac_rare_total`；用 `frac_closure_residual` 补回 P0 删除重复 fraction 列后留下的闭合缺口。输出 `data/feature_matrix_v2.csv`（255 维）与 `data/feature_matrix_v2_reduced.csv`（181 维，按 block 内 |r|≥0.98 做结构性去重，不看目标）。审计改用 z-score 后的 SVD，避免原尺度被极端 ratio 主导。

治理后：v2 full 有效秩 165/255，PC1 45.7%，PC1 与总投料质量 r=0.866；v2 reduced 有效秩 178/181，PC1 39.8%，r=0.836。与 v1 clean 的 r≈0.867 基本持平，说明 **体系/批次混杂仍在，不能靠特征清洗消掉**；|r|>0.98 的高相关对从 v1 的 319 组降到 v2 full 309 组、v2 reduced 19 组。

同目标、同切点、同 `StratifiedGroupKFold(5)` 复跑：T 弯 310 条 v1/v2 full/v2 reduced 最优 QWK 为 0.4975 / 0.4560 / 0.4855，v2 没有改善；MEK 352 条为 0.5943 / 0.5903 / 0.6099，v2 reduced 的序数模型有小幅提升；水煮 277 条为 0.5025 / 0.5053 / 0.5203，v2 reduced 的多分类有小幅提升。结论是 **这轮修特征解决了数值稳定性和冗余，但没有带来三个目标的普遍提升，T 弯仍是硬骨头**；不能把 v2 当作“更好模型”交付，只能作为更干净的数据层候选。结果见 `scripts/feature_audit_v2.json`、`scripts/p08_feature_v2_bench_results.json`，报告见 [P0.8 Feature v2 特征治理与复跑](https://my.feishu.cn/docx/Xdpddia5zoGvjpxPmpAc2qG4nDe)。

### P0.9 分级性能探索与基准（2026-11-24）

`scripts/p09_grade_exhaustive.py` 把分级路线拆成切点层、模型层、决策层三层，跑了 11 个基础模型臂、4 个切点方案（T 3/2、MEK 4/5/3/2、水煮 3/两个二分类）、两套特征（v1 260 / v2r 181）和 3 seeds ×5 折，并对概率模型派生“过度预测多罚 2 倍”的代价敏感决策。结论是：**T 弯 3 级、MEK 4 级、水煮 3 级是当前数据支持的最细粒度**；更细的 MEK 5 级虽 QWK 略高（0.645 vs 0.641），但 macro F1 0.424 vs 0.483、MAE 0.861 vs 0.625，工程上不划算；T/水煮的 4/5 级受类别样本量限制。

3 seeds 基准：T 弯 `ord_logit`（v1，3 级）QWK 0.530±0.015、高档 recall 0.784、过度预测 0.173；保守 `reg_xgb`（v2r）QWK 0.488±0.002、MAE 0.290、过度预测 0.139。MEK `ord_logit_cost`（v2r，4 级）QWK 0.652±0.012、MAE 0.578、高档 recall 0.746、过度预测 0.122；`ord_logit` 高档 recall 0.849 但过度预测 0.252。水煮 `multi_xgb`（v2r，3 级）QWK 0.483±0.031、高档 recall 0.673、过度预测 0.188；代价版 QWK 0.464±0.032、过度预测 0.159。水煮单次 P0.6 的 0.5187 不应继续当基准，三次 seed 均值只有 0.483 左右。

类别权重不是万能：T/MEK 的 balanced 版本多数下降，水煮只在 v1 有小幅帮助；模型族上，T/MEK 的累积 logistic 优于树模型，水煮仍是 XGBoost 多分类最好。报告见 [P0.9 分级性能基线](https://my.feishu.cn/docx/CZs0dIOVdoS2ZtxJw12czwhpnbc)，基准表见 `data/p09_selected_stability.csv`，切点敏感性见 `data/p09_schema_sensitivity.csv`，全部臂见 `data/p09_primary_all_arms.csv`。

## 实验索引

| 批次 | 主题 | 入口 | 关键结论 |
| --- | --- | --- | --- |
| J | 噪声地板与 R²>0.9 可达性 | `mvp75_experiments.py` | T弯噪声地板约 0.789；换模型/加特征无法突破 |
| K/L | MEK 截尾诚实评估、AFT 边界 | `mvp76*`、`mvp77*` | 未截尾回归 + 边界判别优于代理目标 |
| M/N/O | 主动学习、降噪假设、LOSO | `mvp78`~`mvp80` | 系列分层随机优于纯不确定性采样；LOSO 是硬边界 |
| P~T | 机理特征、评估加固、预算复核 | `mvp81`~`mvp87` | 机理列对 MEK/水煮有增益，对 T弯持平；折叠内选择修复泄漏 |
| U | TDS/SDS 实测层增益 | `mvp88_tds_uplift.py`、`tds_coverage_audit.py` | 用量加权实测+族推 99.6%，域内 R² 中性偏平 |
| V | 达标分类验证 | `mvp90_qualify_classification.py` | 回归转阈值四任务全胜；LSO 从不可用转为 AUC 0.72~0.88 |
| E/S/A | 数据困境专项 | `data_dilemma/scripts/` | 外部数据 OOD 不兼容；伪标签回放有效；瓶颈在测量噪声 |
| P10 | 原料 FTIR v3 | `experiments/P10_ftir_v3/` | FTIR8 T +0.0283，未过预注册 +0.03；主基准维持 v2-fix |
| P11 | 语义池 + 219 公式搜索 | `experiments/P11_feature_search/` | 无公式组块过门槛；P11-C5 仅诊断，不入模 |
| P12 | 模型/决策层优化 | `experiments/P12_optimization/` | 三目标平均 QWK 0.5327→0.5485；未改特征层 |
| P13 | 特征层优化（初筛） | `experiments/P13_feature_opt/` | 增广/全谱/样条多退化；FTIR8 3-seed 初筛 +0.0349 |
| **P14** | **T 190 维证据链（当前最优）** | `experiments/P14_evidence_chain/` | **10 seeds nested QWK 0.5707，+0.0256（p=0.0046）；三目标平均 0.5609** |

每个实验目录固定包含 `README.md`、`scripts/`、`data/`、`results/`、`logs/`；共享依赖只在 `tooling/`，不复制进实验目录。P14 的最优方案与证据链见 [`experiments/P14_evidence_chain/README.md`](experiments/P14_evidence_chain/README.md)。

每个脚本都固定随机种子；大多数实验支持 `--s1/--s2/--seeds/--arms` 等参数，具体以 `--help` 为准。P0~P9 的结果 JSON 在 `scripts/*_result.json`，P10 以后在 `experiments/<批次>/results/`。

## 已知限制

1. **没有持久化模型产物**：主模型配置在 `core/modeling.py` 内，训练通过脚本执行，仓库不附带可直接加载的模型文件。
2. **pkl 版本兼容**：`data/merged_data.pkl` 与当前 pandas 2.2.3 不兼容；重建链可以重新生成，但旧 pkl 不能直接读。
3. **历史 Web 整理链已移除**：旧整理链把测试列当原料列，与实际配料表 schema 脱节，且“175 条实测”实际没有性能记录；现在统一走 `scripts/reingest_template.py`，不再维护第二套整理逻辑。
4. **TDS/SDS 覆盖是“原料级高、字段级低”**：73 种原料中 69 种有实测或同族推断锚定，但全 32 字段的逐字段实测覆盖只有 13.7%（关键化学量 20.6%）；其余靠送检组成、公开手册和族推断，引用时要看出处。
5. **小样本体系不能池化解读**：聚酯金黄 19 条（实测 16）、环氧-配比方案 92 条（实测 63），水煮正类率很低；所有指标应按体系拆分报告，综合值只作参考。
6. **无标签样本的标签仍是补测候选**：伪标签/主动学习结果只用于排程，不是实测标签；补齐后跨体系泛化才能验证。
7. **仓库没有自动化测试**：依赖已锁在 `tooling/requirements.txt`，但当前验证仍以脚本可运行、指标可复现为准；后续开发应先补最小 smoke test。

## 重构说明

本次重构做了五件事：

1. **移除旧 Web 整理界面**：删除旧 Web 服务、启动脚本与相关引用。
2. **移除桌面 GUI 层**：删除两个桌面入口和所有界面代码；原目录更名为 `core/`，原建模模块改为 `core/modeling.py`，原数据整理模块改为 `core/data_prep.py`。仓库不再提供任何 GUI 入口，只保留无界面的数据/特征/模型函数。
3. **提升主开发目录**：把原 `generalization/` 下的 `TDS-SDS/`、`raw/`、`data/`、`core/`、`scripts/`、`data_dilemma/`、模板、报告和文档整体移到仓库根目录，删除空壳目录。
4. **清理 Phase 1 旧结构**：删除根目录 `code/`、`data/`、`models/`、`report/` 与旧根 README；Phase 1 内容仍保留在 git 历史（`ef9dc50` 及之前）中，需要时可按提交找回。
5. **修复路径与文档**：把 `generalization/...` 引用改成根目录相对路径；更新 `模板工作原理与泛化原理.md` 的旧数据（486/440/80/77 → 456/421/73/69）；重写本 README。

重构后，仓库只有一条主开发线：**数据重录 → 合并数据集 → 共享特征/机理核心 → 实验脚本/CLI**。新增代码按这个边界放：数据与特征内核进 `core/`，P0~P9 历史实验进 `scripts/`，P10 以后专题实验进 `experiments/<批次>/`（每批必须有 `README.md` 与 `scripts/`、`data/`、`results/`、`logs/`），共享依赖进 `tooling/`，专题报告放根目录，专项数据实验放 `data_dilemma/`。
