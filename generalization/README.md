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
    ├── workbench/                     # 配套 Windows 工作台源码
    │   ├── DataPrepWorkbench.py       # 数据整理与特征转换工作台（前置自动化）
    │   ├── CoatingModelWorkbench.py   # 建模与预测工作台（含最优配置）
    │   ├── materials.py               # 跨体系原料描述符库（85 种）
    │   └── smi_desc.py                # SMILES 分子描述符（内嵌，无需 RDKit）
    └── scripts/                       # 可复现脚本
        ├── build_template3.py         # 终极版模板 v3 生成
        ├── build_merged_excel.py      # 合并版数据集生成
        ├── parse_unlabeled.py         # 无标签配方解析（配比方案/聚酯金黄）
        ├── mvp74_final_verify.py      # 最终验证（三目标最优配置，20 种子）
        ├── run_pipeline.py            # 通用型流水线 CLI（模板→描述符→建模CSV→标签补充）
        ├── materials.py / descriptors.py / smi_desc.py   # 描述符计算依赖
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
| 最终验证（合并版数据集，20 种子） | 见下方「最终验证」 |

### 最终验证（`scripts/mvp74_final_verify.py`）

在合并版数据集上按最优配置诚实评估（20 种子）：

| 目标 | 配置 | 结果 | 达标 |
| --- | --- | --- | --- |
| T弯（回归） | sqrt 变换 + 噪声过滤 + keep=60 k=8 w=0.85 | R²=0.791（n=251） | ✅ >0.7 |
| MEK 擦拭（回归） | 分类器代理目标（截尾≥300 校准，AUC=0.943）+ sqrt + keep=45 k=1 | R²=0.701（n=318） | ✅ >0.7 |
| 水煮等级（分类） | 每系列阈值 + keep=80 | acc=0.804（n=189） | ✅ >0.8 |

> 注：报告 §5.9 的 0.466 为「跨域模拟」场景（目标域仅少量标签）下的流水线对比值；本目录 `合并版数据集.xlsx` 为同域全量数据，最终验证在更充分的标签上达到 R²>0.7 / acc>0.8。

## 快速开始

1. **看报告**：浏览器直接打开 `coating-model-generalization.html`（字体/图表已本地化，离线可用）。
2. **用模板**：新配方按 `终极版数据集模板.xlsx` 录入（下拉选体系/角色/树脂类型，未登记原料自动标红）。
3. **整理数据**：Windows 上运行 `workbench/DataPrepWorkbench.py`，一键导入多源 Excel → 自动识别格式、清洗代码、去重 → 导出模板结构与特征矩阵。
4. **复现验证**：`python scripts/mvp74_final_verify.py`（需 `numpy/pandas/openpyxl/xgboost/lightgbm/scikit-learn`）。

## 复现环境

```bash
pip install numpy pandas openpyxl xgboost lightgbm scikit-learn
python scripts/mvp74_final_verify.py     # 最终验证（读取 ../合并版数据集.xlsx）
python scripts/build_template3.py        # 重新生成终极版模板
python scripts/build_merged_excel.py     # 重新生成合并版数据集（需 merged_data.pkl 中间产物）
python scripts/run_pipeline.py desc --input 通用型数据集模板.xlsx --output 特征.csv
```

## 与仓库根目录已有成果的关系

- 根目录 `report/coating-model-optimization.html`、`code/`、`models/`、`data/` 为**第一阶段**（优化与泛化验证，清洁同工艺池 200℃/10min）。
- 本目录为**第二阶段**（跨体系泛化方案 + 终极模板 + 自动化工作台 + 合并版数据集），面向更多涂料体系，二者互补不重复。
