# -*- coding: utf-8 -*-
"""
MVP 全流程验证 v3 —— 实验I：最优组合标签补充流水线
====================================================
依据调研结论（active-DeepFA 2025 / ChemCopilot 2026 / 钢缺陷分类 2026 /
催化剂人机协同 2024 等），最优标签补充流水线为：

  阶段1 冷启动：迁移学习（源域预训练 + 目标域少量实测标签微调）
  阶段2 半监督扩充：高置信伪标签（软标签/置信度加权）回放
  阶段3 主动学习：不确定性采样选最该实测的样本，加入真实标签
  阶段4 迭代：重复阶段2-3，双重停止（性能平台期 + 标注预算）

本实验在"配方系列=域"的模拟跨域场景下，对比：
  A) 仅目标域少量标签（冷启动基线）
  B) 迁移冷启动（源域+目标标签加权）
  C) 迁移 + 伪标签扩充
  D) 迁移 + 伪标签 + 主动学习（完整最优流水线）
"""
import pickle, warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from descriptors import formulation_descriptors, DESC_FEATURES
warnings.filterwarnings('ignore')

SEED = 42
np.random.seed(SEED)

# 数据源路径可通过命令行参数覆盖：python mvp3_experiments.py f2=xxx.xlsx out=结果.pkl
import sys, os
_ARGS = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
def _p(key, default):
    return _ARGS.get(key, default)

# ============ 数据载入（环氧酚醛） ============
f2 = _p('f2', "/workspace/.uploads/54d2ddcf-cfaf-4714-9a8f-f96748dc0968_配料测试数据汇总V1.xlsx")
df = pd.read_excel(f2, sheet_name="配方与结果数据集V1")
comp_cols = [c for c in df.columns if c not in [
    '批次','追溯编号','配方ID','配方系列','配方类型','线棒号','烘烤条件',
    'T弯(mm)_原始','MEK擦拭(次)_原始','水煮（等级）_原始','检测指标数量','检测完整率',
    '检测完整性','复核状态','来源文件']]
df['T弯'] = pd.to_numeric(df['T弯(mm)_原始'], errors='coerce')
df['MEK'] = pd.to_numeric(df['MEK擦拭(次)_原始'].astype(str).str.replace('300+','300'), errors='coerce')
df['水煮'] = pd.to_numeric(df['水煮（等级）_原始'], errors='coerce')

desc_rows = []
for _, row in df.iterrows():
    comp = {c: row[c] for c in comp_cols}
    d = formulation_descriptors(comp)
    if d:
        desc_rows.append(d)
desc_df = pd.DataFrame(desc_rows)[DESC_FEATURES]
print("环氧酚醛: 配方", len(desc_df), "描述符", desc_df.shape[1])

TARGETS = {'T弯': 'T弯', 'MEK': 'MEK', '水煮': '水煮'}

def rf():
    return RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=-1)

def ensemble_uncertainty(m, X):
    """深度集成不确定性：RF 树间预测标准差（等价于集成方差）"""
    preds = np.array([t.predict(X) for t in m.estimators_])
    return preds.mean(0), preds.std(0)

results = {}
print("\n===== 实验I: 最优组合标签补充流水线 =====")
series_list = sorted(df['配方系列'].unique())
for tname, col in TARGETS.items():
    mask = df[col].notna()
    X = desc_df.loc[mask].values
    y = df.loc[mask, col].values
    ser = df.loc[mask, '配方系列'].values
    # 源域: 前70%系列, 目标域: 后30%系列
    n_ser = len(series_list)
    src_series = set(series_list[:int(n_ser*0.7)])
    src = np.array([s in src_series for s in ser])
    X_src, y_src = X[src], y[src]
    X_tgt, y_tgt = X[~src], y[~src]
    if len(X_tgt) < 20:
        continue
    # 目标域再拆: 少量实测标签(20%) + 测试(80%)
    rng = np.random.RandomState(SEED)
    n_tgt = len(y_tgt)
    idx = rng.permutation(n_tgt)
    n_lab = max(5, int(n_tgt*0.2))
    tgt_lab, tgt_test = idx[:n_lab], idx[n_lab:]
    X_tl, y_tl = X_tgt[tgt_lab], y_tgt[tgt_lab]
    X_tt, y_tt = X_tgt[tgt_test], y_tgt[tgt_test]
    # 目标域无标签池（用于伪标签/主动学习模拟，取测试集前一半）
    n_pool = min(len(tgt_test), 30)
    pool_idx = tgt_test[:n_pool]
    X_pool, y_pool = X_tgt[pool_idx], y_tgt[pool_idx]
    test_idx = tgt_test[n_pool:]
    X_te, y_te = X_tgt[test_idx], y_tgt[test_idx]

    def eval_r2(m):
        return r2_score(y_te, m.predict(X_te))

    # A) 仅目标域少量标签
    m_a = rf().fit(X_tl, y_tl)
    r2_a = eval_r2(m_a)

    # B) 迁移冷启动（源域 + 目标标签加权3x）
    X_b = np.vstack([X_src, X_tl])
    y_b = np.concatenate([y_src, y_tl])
    w_b = np.concatenate([np.ones(len(y_src)), np.full(len(y_tl), 3.0)])
    m_b = rf().fit(X_b, y_b, sample_weight=w_b)
    r2_b = eval_r2(m_b)

    # C) 迁移 + 伪标签扩充（高置信伪标签，权重0.5）
    mean_p, std_p = ensemble_uncertainty(m_b, X_pool)
    rel_std = std_p/(np.abs(mean_p)+1e-6)
    q = np.quantile(rel_std, 0.5)
    conf = rel_std < q
    n_conf = int(conf.sum())
    X_c = np.vstack([X_b, X_pool[conf]])
    y_c = np.concatenate([y_b, mean_p[conf]])
    w_c = np.concatenate([w_b, np.full(n_conf, 0.5)])
    m_c = rf().fit(X_c, y_c, sample_weight=w_c)
    r2_c = eval_r2(m_c)
    pseudo_corr = float(np.corrcoef(mean_p[conf], y_pool[conf])[0,1]) if n_conf > 1 else 0.0

    # D) 迁移 + 伪标签 + 主动学习（完整流水线）
    # 主动学习：从伪标签未覆盖的高不确定样本中选 top-K 实测（用真实标签）
    X_d = X_c.copy(); y_d = y_c.copy(); w_d = w_c.copy()
    remain = ~conf
    if remain.sum() > 0:
        n_al = min(8, int(remain.sum()))
        mean_r, std_r = ensemble_uncertainty(m_c, X_pool[remain])
        pick = np.argsort(std_r)[-n_al:]
        X_d = np.vstack([X_d, X_pool[remain][pick]])
        y_d = np.concatenate([y_d, y_pool[remain][pick]])
        w_d = np.concatenate([w_d, np.ones(n_al)])
    m_d = rf().fit(X_d, y_d, sample_weight=w_d)
    r2_d = eval_r2(m_d)

    # E) 质量门控自适应流水线：源域随机划分CV评估该目标内在可预测性，
    #    伪标签质量低（源域CV R2<0.2）时跳过伪标签扩充，仅用迁移+主动学习实测
    from sklearn.model_selection import train_test_split
    X_src_tr, X_src_va, y_src_tr, y_src_va = train_test_split(
        X_src, y_src, test_size=0.25, random_state=SEED)
    m_cv = rf().fit(X_src_tr, y_src_tr)
    src_cv_r2 = float(r2_score(y_src_va, m_cv.predict(X_src_va)))
    use_pseudo = src_cv_r2 >= 0.2  # 质量门控：源域可预测才用伪标签

    if use_pseudo:
        X_e = X_c.copy(); y_e = y_c.copy(); w_e = w_c.copy()
        base_model = m_c
    else:
        X_e = X_b.copy(); y_e = y_b.copy(); w_e = w_b.copy()
        base_model = m_b
    # 主动学习：从全部无标签池中选最高不确定样本实测（真实标签）
    mean_r, std_r = ensemble_uncertainty(base_model, X_pool)
    n_al = min(8, len(X_pool))
    pick = np.argsort(std_r)[-n_al:]
    X_e = np.vstack([X_e, X_pool[pick]])
    y_e = np.concatenate([y_e, y_pool[pick]])
    w_e = np.concatenate([w_e, np.ones(n_al)])
    m_e = rf().fit(X_e, y_e, sample_weight=w_e)
    r2_e = eval_r2(m_e)

    results[tname] = {
        'src_n': len(X_src), 'tgt_n': len(X_tgt), 'tgt_lab_n': len(y_tl),
        'n_pool': len(X_pool), 'n_conf': n_conf, 'n_active': int(remain.sum()>0 and min(8, int(remain.sum()))),
        'src_cv_r2': src_cv_r2, 'use_pseudo': bool(use_pseudo),
        'r2_only_target': r2_a, 'r2_transfer': r2_b,
        'r2_transfer_pseudo': r2_c, 'r2_full_pipeline': r2_d, 'r2_adaptive': r2_e,
        'pseudo_corr': pseudo_corr}
    print(f"{tname}: 仅目标R2={r2_a:.3f} | 迁移={r2_b:.3f} | 迁移+伪标签={r2_c:.3f} | 完整={r2_d:.3f} | 自适应={r2_e:.3f} | 源域CV={src_cv_r2:.2f}(门控{'开' if use_pseudo else '关'}) | 伪标签相关={pseudo_corr:.3f}")

out = _p('out', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mvp3_results.pkl'))
with open(out, 'wb') as fh:
    pickle.dump({'results': results}, fh)
print("\n实验I完成，结果已保存", out)
