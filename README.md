# 3NEW · 三新项目研发

**涂料配方性能预测与跨体系泛化。** 本仓库以「原料描述符 + 配方级机理特征 + SMILES 分子描述符」替代原料编码，让环氧酚醛、环氧-配比方案、聚酯金黄三个体系共用同一套特征空间，并对 T弯、MEK 擦拭、水煮等级三项目标做建模、验证与预测。

> 2026-11-23 完成仓库重构：原 `generalization/` 提升为根目录，Phase 1 旧结构和 Web 数据工作台已移出主树。当前主树只保留跨体系泛化这一条开发主线。

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
├── TDS-SDS/                            # 供应商 TDS/SDS 档案 291 份（描述符实测出处）
├── workbench/                          # 共享数据/建模内核 + 两个桌面工作台
│   ├── DataPrepWorkbench.py            # 数据整理与特征转换（Tkinter 桌面版）
│   ├── CoatingModelWorkbench.py        # 建模与预测（含当前最优配置）
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

仓库尚未提供 `requirements.txt`，按脚本实际依赖安装：

```bash
pip install numpy pandas openpyxl scipy scikit-learn xgboost lightgbm
```

Python 建议 3.10+。桌面工作台需要 Tkinter；无头 Linux/云主机只能跑脚本，不能开 GUI。

### 看报告

直接用浏览器打开 `coating-model-generalization.html`，字体和图表已本地化，可离线查看。其余四份根目录 HTML 是专题报告。

### 跑桌面工作台（Windows / 有图形界面的环境）

```bash
python workbench/DataPrepWorkbench.py      # 数据整理、特征转换
python workbench/CoatingModelWorkbench.py  # 训练三目标、预测新配方
```

`CoatingModelWorkbench.py` 内置当前最优配置（见下表），可以直接训练；训练结果不落盘为独立模型文件，下次启动需重新训练。

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

## 特征与模型

### 313 维特征契约

`CoatingModelWorkbench.build_feature_matrix()` 固定输出 313 维，顺序由 `feature_names` 固化：

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
- **新系列外推不可直接用**：留一系列外推加权 R²≈−0.30；新系列先测 1~2 个配方回入系列编码，再依赖数值预测。工作台会对未登记系列和越界特征给出警告。

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

每个脚本都固定随机种子；大多数实验支持 `--s1/--s2/--seeds/--arms` 等参数，具体以 `--help` 为准。完整结果 JSON 在 `scripts/*_result.json`。

## 已知限制

1. **没有持久化模型产物**：主模型配置在 `workbench/CoatingModelWorkbench.py` 内，训练在 GUI 中完成，仓库不附带可直接加载的模型文件。
2. **pkl 版本兼容**：`data/merged_data.pkl` 与当前 pandas 2.2.3 不兼容；重建链可以重新生成，但旧 pkl 不能直接读。
3. **Web 数据工作台已移除**：原 `workbench/webapp/` 的整理链把测试列当原料列，与实际配料表 schema 脱节，且“175 条实测”实际没有性能记录；现在统一走 `scripts/reingest_template.py`，不再维护第二套整理逻辑。
4. **TDS/SDS 覆盖是“原料级高、字段级低”**：73 种原料中 69 种有实测或同族推断锚定，但全 32 字段的逐字段实测覆盖只有 13.7%（关键化学量 20.6%）；其余靠送检组成、公开手册和族推断，引用时要看出处。
5. **小样本体系不能池化解读**：聚酯金黄 19 条（实测 16）、环氧-配比方案 92 条（实测 63），水煮正类率很低；所有指标应按体系拆分报告，综合值只作参考。
6. **无标签样本的标签仍是补测候选**：伪标签/主动学习结果只用于排程，不是实测标签；补齐后跨体系泛化才能验证。
7. **仓库没有测试与依赖锁文件**：当前验证以脚本可运行、指标可复现为准；后续开发应先补最小 smoke test 和依赖版本约束。

## 重构说明

本次重构做了四件事：

1. **移除 Web 工作台**：删除 `workbench/webapp/`（`server.py`、`flow.py`、`index.html`）与 `start_webapp.sh/.bat`，并清理 `.gitignore` 与 `mvp80_experiments.py` 中的 webapp 引用。
2. **提升主开发目录**：把原 `generalization/` 下的 `TDS-SDS/`、`raw/`、`data/`、`workbench/`、`scripts/`、`data_dilemma/`、模板、报告和文档整体移到仓库根目录，删除空壳目录。
3. **清理 Phase 1 旧结构**：删除根目录 `code/`、`data/`、`models/`、`report/` 与旧根 README；Phase 1 内容仍保留在 git 历史（`ef9dc50` 及之前）中，需要时可按提交找回。
4. **修复路径与文档**：把 `generalization/...` 引用改成根目录相对路径；更新 `模板工作原理与泛化原理.md` 的旧数据（486/440/80/77 → 456/421/73/69）；重写本 README。

重构后，仓库只有一条主开发线：**数据重录 → 合并数据集 → 共享特征/机理层 → 桌面工作台/实验脚本**。新增代码按这个边界放：数据与特征内核进 `workbench/`，可复现实验进 `scripts/`，专题报告放根目录，专项数据实验放 `data_dilemma/`。
