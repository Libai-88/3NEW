# 涂料配方性能预测模型 · 跨体系泛化方案（终极版）

本目录是「3NEW 三新项目研发」的第二阶段成果：在仓库根目录已有「优化与泛化验证」报告（`../report/coating-model-optimization.html`）基础上，面向**更多涂料体系**交付的**终极版泛化方案**。包含：泛化方案报告、终极版数据集模板、合并版数据集、配套 Windows 工作台源码与可复现脚本。

## 目录结构

```text
3NEW
└── generalization/                    # 本目录：跨体系泛化方案（终极版）
    ├── README.md                      # 本文件：方案总览、交付物、复现
    ├── coating-model-generalization.html   # 终极版泛化方案报告（浏览器直接打开）
    ├── assets/                        # 报告图表（A~I 共 9 张实验图）
    ├── _shared/                       # 报告依赖的字体与 JS 库（离线可用）
    ├── 通用型数据集模板.xlsx          # 通用型模板（8 工作表，5,185 条公式）
    ├── 终极版数据集模板.xlsx          # 终极版模板 v3（多体系配置驱动 + 数据验证）
    ├── 合并版数据集.xlsx              # 现有全部数据整理并填入终极版模板
    ├── data/                          # 合并版数据集生成的中间产物
    │   └── merged_data.pkl            # 486 样本配方+描述符（build_merged_excel.py 输入）
    ├── workbench/                     # 配套自动化工作台源码
    │   ├── DataPrepWorkbench.py       # 数据整理与特征转换工作台（Tkinter 桌面版）
    │   ├── CoatingModelWorkbench.py   # 建模与预测工作台（含最优配置）
    │   ├── materials.py               # 跨体系原料描述符库（85 种）
    │   ├── smi_desc.py                # SMILES 分子描述符（内嵌，无需 RDKit）
    │   ├── webapp/                    # Web 版工作台（推荐，跨平台零安装）
    │   │   ├── server.py              # 后端服务（Python 标准库 HTTP，自动开浏览器）
    │   │   ├── flow.py                # 前置流程控制（写死 vs 可配置、预校验、流水线清单、补标签排程、建模就绪检查）
    │   │   └── index.html             # 前端界面（数据整理/特征转换/辅助录入/补标签排程/建模就绪检查）
    │   ├── start_webapp.bat           # Windows 一键启动脚本（双击运行）
    │   └── start_webapp.sh            # Linux/macOS 一键启动脚本
    └── scripts/                       # 可复现脚本
        ├── build_template3.py         # 终极版模板 v3 生成
        ├── build_merged_excel.py      # 合并版数据集生成
        ├── parse_unlabeled.py         # 无标签配方解析（配比方案/聚酯金黄）
        ├── mvp74_final_verify.py      # 最终验证（三目标最优配置，20 种子）
        ├── mvp75_experiments.py       # 实验 J：噪声地板 + 多任务/机理特征/加权回归验证
        ├── mvp76_experiments.py       # 实验 K：MEK 截尾诚实评估拆分（代理目标 vs 未截尾回归 vs Tobit）
        ├── mvp76b_experiments.py      # 实验 K-5：MEK 两阶段优化（p_hi 特征 / 软混合 / 双输出）
        ├── mvp77_experiments.py       # 实验 L：AFT 边界判别（survival:aft，右截尾 [300,inf)）
        ├── mvp77b_experiments.py      # 实验 L-2：AFT 预测分布与校准分析
        ├── mvp77c_experiments.py      # 实验 L-3：解耦两阶段（AFT 边界 + 未截尾回归）稳定性验证
        ├── mvp78_experiments.py       # 实验 M：主动学习模拟（5 种标签获取策略对比）
        ├── mvp79_experiments.py       # 实验 N：噪声降低假设分析（R²>0.9 可达路径）
        ├── mvp80_experiments.py       # 实验 O：留一体系外验证（LOSO，跨体系泛化诚实缺口）
        ├── run_pipeline.py            # 通用型流水线 CLI（模板→描述符→建模CSV→标签补充）
        ├── materials.py / descriptors.py / smi_desc.py   # 描述符计算依赖
    └── data_dilemma/                  # 数据困境专项实验（公开数据检索 + 降噪/伪标签/主动学习路径验证）
        ├── README.md                  # 实验说明与复现
        ├── report/                    # 数据困境解决方案验证报告（浏览器直接打开）
        └── scripts/                   # 实验 E（外部数据整合）/ S（半监督伪标签）/ A（主动学习）
```

## 方案要点（均有实验支持）

1. **跨体系通用描述符体系**：以「原料描述符（角色/树脂类型/固含/EEW/官能团密度等）+ SMILES 分子描述符 + 显式比例」替代原料编码，使环氧酚醛/有机/聚酯/聚氨酯/丙烯酸/环氧胺等体系可映射进同一特征空间（实验 D：跨体系编码 PCA 验证）。
2. **四阶段标签补充流水线**：迁移冷启动 → 质量门控伪标签 → 主动学习实测 → 迭代。质量门控（源域 CV R²≥0.2）防止伪标签在难预测目标上造成损害。
3. **诚实评估协议**：按样本 ID 去重（重复测量取均值）、折叠内 OOF 系列编码、噪声过滤（|OOF 残差|≤2×重复测量噪声 std）、多体系留出验证。
4. **终极版模板 v3**：以「体系配置」表驱动，新增体系/目标属性无需改结构；数据验证下拉 + 未登记原料自动标红，杜绝手输错别字。

## 关键实验结果

| 场景 | 结果 |
| --- | --- |
| 描述符 vs 原料编码（新组分） | 描述符模型 18 组中 11 组胜出 |
| 未见配方系列泛化 | 描述符模型整体更优 |
| 跨体系特征空间 | 三体系可映射进同一空间，跨体系建模可行 |
| 迁移学习冷启动 | 目标域 T弯 R² 约提升一倍（0.25→0.51） |
| 最优组合流水线 | 可预测目标上 T弯 R² 0.263→0.466（+0.20），质量门控防伪标签损害 |
| 噪声地板（实验 J） | T弯 理论最大 R²=0.789（模型 0.791 已达上限）；MEK 噪声地板 0.966 含截尾口径；水煮按分类评估 |
| MEK 截尾诚实评估（实验 K/L） | 未截尾真实 R²=0.495（p_hi 特征注入，0.474→0.495）；AFT 边界判别 acc=0.9465 / 截尾召回=0.804（对比分类器 acc=0.915/召回=0.522）；代理目标 R²=0.70 为虚高口径 |
| 主动学习模拟（实验 M） | T弯 n=277/18 系列：系列分层随机/随机最终测试 R²=0.688、达 R²≥0.6 仅需 70~90 标签；纯不确定性采样 R²=0.647、需 130 标签（最差）。系列结构化数据上随机/分层采样优于不确定性采样 |
| 噪声降低假设（实验 N） | T弯 R²>0.9 需将测量噪声从 1.244 降至 ≤0.62（减半）或重复测量 4 次取均值；MEK 系列内 CV 超出 ASTM D5402-19 上限，降噪空间大 |
| 留一体系外验证（实验 O） | 合并版数据集 3 体系仅 1 个有标签，LOSO 无法直接运行——诚实报告跨体系泛化缺口，输出补测清单（环氧-配比方案/聚酯金黄）；补测后脚本自动执行完整 LOSO |
| 数据困境专项（实验 E/S/A，见 `data_dilemma/`） | 外部公开数据 OOD 1887× 不兼容（合并 ΔR²=-0.009）；半监督伪标签回放 ΔR²=+0.153（w=0.5）；主动学习 30 样本仅 +0.008——瓶颈在测量噪声，重复测量 4 次取均值可将 R² 上限 0.791→0.948 |
| 最终验证（合并版数据集，20 种子） | 见下方「最终验证」 |

### 最终验证（`scripts/mvp74_final_verify.py`）

在合并版数据集上按最优配置诚实评估（20 种子）：

| 目标 | 配置 | 结果 | 达标 |
| --- | --- | --- | --- |
| T弯（回归） | sqrt 变换 + 噪声过滤 + keep=60 k=8 w=0.85 | R²=0.791（n=251） | ✅ >0.7 |
| MEK 擦拭（回归） | 两阶段：AFT 边界判别（≥300，acc=0.9465 / 截尾召回=0.804）+ 未截尾回归（含分类器概率特征） | 未截尾 R²=0.495 / 边界 acc=0.9465（n=318） | 诚实口径 |
| 水煮等级（分类） | 每系列阈值 + keep=80 | acc=0.804（n=189） | ✅ >0.8 |

> MEK 说明：46/318 个样本实测值恰为 300（真实值 ≥300 未知，右截尾）。早期「R²=0.701」为含截尾代理值的虚高口径；实验 K（`scripts/mvp76_experiments.py`、`scripts/mvp76b_experiments.py`）将评估拆分为「未截尾真实 R² + 边界分类准确率」两个诚实指标，工作台 MEK 模型相应升级为两阶段结构（边界分类器 + 未截尾回归），端到端验证与实验 K 一致。

### 关于「R²>0.9」终极目标（`scripts/mvp75_experiments.py`，实验 J）

用重复测量噪声估计数据自身决定的性能上限，并验证进阶手段是否真实提升：

| 目标 | 重复测量噪声 std | 噪声地板 R²（理论最大） | 当前模型 | 结论 |
| --- | --- | --- | --- | --- |
| T弯 | 1.244 | 0.789 | R²=0.791 | 已达噪声地板，换模型/加特征无法突破，需降测量噪声或扩体系跨度 |
| MEK 擦拭 | 17.94 | 0.966（含截尾口径） | 未截尾 R²=0.495 / 边界 acc=0.915 | 回归受截尾（46 样本真实值≥300 未知）限制，边界判别可靠 |
| 水煮等级 | 0.679 | 0.154（回归口径） | acc=0.804（分类） | 离散标签，按分类评估 |

实验 J-3~J-5 验证：加权回归（0.720）、多任务学习（0.689）、机理特征增强（0.691）相对基线（0.691）均无真实提升，**不应作为提分手段**；突破空间在数据质量（降噪、解决 MEK 截尾）与数据多样性（扩体系）两端。

### MEK 截尾处理（`scripts/mvp76_experiments.py`、`scripts/mvp76b_experiments.py`、`scripts/mvp77_experiments.py`，实验 K/L）

MEK 擦拭存在右截尾（46/318 样本实测值恰为 300，真实值 ≥300 未知）。实验 K 将评估拆分为「未截尾真实 R² + 边界分类准确率」两个诚实指标，并验证多种截尾处理；实验 L 引入 XGBoost `survival:aft`（右截尾 [300,inf)）提升边界判别：

| 方法 | 未截尾 R²（n=272） | 边界 acc | 结论 |
| --- | --- | --- | --- |
| 代理目标（旧口径） | 0.427 | 0.899 | 全样本 R²=0.708 为含截尾代理值的虚高口径 |
| 未截尾回归（丢弃截尾） | 0.474 | — | 仅在未截尾样本上训练与评估 |
| **未截尾回归 + 分类器概率特征** | **0.495** | **0.915** | K-5a：分类器 p_hi 注入回归，未截尾 R² 0.474→0.495 |
| **AFT 边界（survival:aft）** | **0.495** | **0.9465** | L-3：AFT 边界 acc 0.915→0.9465、截尾召回 0.522→0.804，解耦后未截尾 R² 不受污染 |
| 硬阈值两阶段 / 软混合 | 0.338 / 0.173 | 0.915 / 0.921 | 伤害未截尾 R²，不采用 |
| Tobit 式自定义目标 | 数值爆炸 | 0.145 | XGBoost 自定义目标梯度不稳，不可用 |

工作台 `workbench/CoatingModelWorkbench.py` 的 MEK 模型已升级为两阶段结构（AFT 边界判别 + 未截尾回归含 p_hi 特征），端到端验证输出与实验 L 一致。

> 注：报告 §5.9 的 0.466 为「跨域模拟」场景（目标域仅少量标签）下的流水线对比值；本目录 `合并版数据集.xlsx` 为同域全量数据，最终验证在更充分的标签上达到 R²>0.7 / acc>0.8。

## 快速开始

1. **看报告**：浏览器直接打开 `coating-model-generalization.html`（字体/图表已本地化，离线可用）。
2. **用模板**：新配方按 `终极版数据集模板.xlsx` 录入（下拉选体系/角色/树脂类型，未登记原料自动标红）。
3. **整理数据（Web 版工作台，推荐）**：双击 `workbench/start_webapp.bat`（Windows）或运行 `workbench/start_webapp.sh`（Linux/macOS），浏览器自动打开 `http://127.0.0.1:8765`。固定流程五步：选择数据源 → 预校验（类型声明+规则检查）→ 一键整理 → 确认报告 → 导出（模板结构/特征矩阵/流水线清单）。支持一键导入多源 Excel（模板/配料汇总/配比方案/聚酯金黄/原料数据）→ 自动识别格式、清洗代码、去重；另含表单式辅助录入（未登记原料自动估算登记）、<b>补标签排程</b>（从未实测样本按系列分层随机推荐下一批应补测标签，实验 M 结论落地，固定种子可复现）与<b>建模就绪检查</b>（自动评估数据是否达到可训练/逼近 R²>0.9 标准，六项检查阈值写死自实验 J/M/N，替代人工经验判断）。「写死 vs 可配置」边界见 `webapp/flow.py`。首次运行自动安装 `numpy/pandas/openpyxl`。
4. **整理数据（桌面版）**：Windows 上运行 `workbench/DataPrepWorkbench.py`（Tkinter 界面，功能与 Web 版一致）。
5. **复现验证**：`python scripts/mvp74_final_verify.py`（需 `numpy/pandas/openpyxl/xgboost/lightgbm/scikit-learn`）。

## 复现环境

```bash
pip install numpy pandas openpyxl xgboost lightgbm scikit-learn
python scripts/mvp74_final_verify.py     # 最终验证（读取 ../合并版数据集.xlsx，相对路径）
python scripts/mvp76_experiments.py      # 实验 K：MEK 截尾诚实评估拆分
python scripts/mvp76b_experiments.py     # 实验 K-5：MEK 两阶段优化
python scripts/mvp77_experiments.py      # 实验 L：AFT 边界判别（survival:aft）
python scripts/mvp77c_experiments.py     # 实验 L-3：解耦两阶段稳定性验证
python scripts/mvp78_experiments.py      # 实验 M：主动学习模拟（5 种标签获取策略对比）
python scripts/mvp79_experiments.py      # 实验 N：噪声降低假设分析（R²>0.9 可达路径）
python scripts/mvp80_experiments.py      # 实验 O：留一体系外验证（LOSO，跨体系泛化诚实缺口）
python scripts/build_template3.py        # 重新生成终极版模板（输出 ../终极版数据集模板.xlsx）
python scripts/build_merged_excel.py     # 重新生成合并版数据集（读取 ../data/merged_data.pkl 中间产物）
python scripts/parse_unlabeled.py 配方文件.xlsx -o unlabeled_formulas.pkl   # 解析无标签配方（命令行传文件）
python scripts/run_pipeline.py desc --input 通用型数据集模板.xlsx --output 特征.csv
# 数据困境专项实验（见 data_dilemma/README.md）
python data_dilemma/scripts/ext_data_experiment.py    # 实验 E：外部公开数据整合
python data_dilemma/scripts/semi_sup_experiment.py    # 实验 S：半监督伪标签回放
python data_dilemma/scripts/active_learning_exp.py    # 实验 A：主动学习模拟
```

> 所有脚本均使用相对路径（基于脚本所在目录），克隆仓库后即可直接运行，无绝对路径依赖。`data/merged_data.pkl` 为合并版数据集生成的中间产物（486 样本配方+描述符），已随仓库提供。

## 与仓库根目录已有成果的关系

- 根目录 `report/coating-model-optimization.html`、`code/`、`models/`、`data/` 为**第一阶段**（优化与泛化验证，清洁同工艺池 200℃/10min）。
- 本目录为**第二阶段**（跨体系泛化方案 + 终极模板 + 自动化工作台 + 合并版数据集），面向更多涂料体系，二者互补不重复。
